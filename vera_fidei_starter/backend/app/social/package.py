from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from app.social.carousel import (
    _COVER_REFERENCE,
    _CTA_REFERENCE,
    _PAGE_TEMPLATE,
    CarouselContent,
    render_carousel,
)
from app.social.daily_card import build_caption
from app.social.instagram_publish import (
    ensure_publication_enabled,
    publish_carousel_to_instagram,
    upload_card,
)
from app.social.ledger import SocialLedger
from app.social.post_model import SocialPostCandidate
from app.social.saint_portrait import approve_portrait, fetch_saint_portrait
from core.config import settings


def _backend_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def current_style_digest() -> str:
    files = [
        _PAGE_TEMPLATE,
        _COVER_REFERENCE,
        _CTA_REFERENCE,
        Path(settings.social_body_font_path),
        Path(__file__).with_name("carousel.py"),
        Path(__file__).with_name("daily_card.py"),
    ]
    digest = hashlib.sha256()
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def create_preview_package(
    *,
    candidate: SocialPostCandidate,
    portrait_bytes: bytes,
    pdf_page_bytes: bytes,
    pdf_title_page_bytes: bytes | None,
    pdf_excerpt_bytes: list[bytes],
    caption: str | None,
    execution_id: str,
) -> Path:
    root = _backend_path(settings.social_output_dir)
    package = root / f"{dt.date.today().isoformat()}_{execution_id}"
    package.mkdir(parents=True, exist_ok=False)

    content = CarouselContent(
        candidate=candidate,
        portrait_bytes=portrait_bytes,
        pdf_page_bytes=pdf_page_bytes,
        pdf_title_page_bytes=pdf_title_page_bytes,
        pdf_excerpt_bytes=pdf_excerpt_bytes,
    )
    slides = render_carousel(content)
    artifacts: list[dict[str, Any]] = []
    for index, payload in enumerate(slides, 1):
        name = f"slide_{index}.png"
        path = package / name
        path.write_bytes(payload)
        artifacts.append({"file": name, "sha256": _sha256_bytes(payload)})

    caption = caption or build_caption(candidate)
    (package / "caption.txt").write_text(caption, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "status": "awaiting_style_approval",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "execution_id": execution_id,
        "style_digest": current_style_digest(),
        "source_fingerprint": candidate.source_fingerprint,
        "portrait_sha256": _sha256_bytes(portrait_bytes),
        "candidate": candidate.to_dict(),
        "artifacts": artifacts,
        "caption_sha256": _sha256_bytes(caption.encode("utf-8")),
        "published": False,
    }
    (package / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return package


def read_manifest(package: str | Path) -> dict[str, Any]:
    path = Path(package) / "manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifesto inválido")
    return value


def approve_current_style(package: str | Path) -> dict[str, Any]:
    """Aprova o template, não uma citação isolada.

    O comando só deve ser executado depois de o proprietário conferir os três
    slides exibidos. Qualquer alteração posterior em fonte ou assets invalida
    automaticamente esta aprovação.
    """
    manifest = read_manifest(package)
    digest = str(manifest.get("style_digest") or "")
    if not digest or digest != current_style_digest():
        raise ValueError("a prévia não corresponde ao estilo atual")
    approval = {
        "schema_version": 1,
        "style_digest": digest,
        "approved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "approved_from_package": str(Path(package).resolve()),
    }
    candidate = manifest.get("candidate") or {}
    author = str(candidate.get("author") or "")
    portrait_sha256 = str(manifest.get("portrait_sha256") or "")
    if not author or not portrait_sha256:
        raise ValueError("prévia não registra o retrato exibido")
    approve_portrait(author, expected_sha256=portrait_sha256)
    approval["approved_portrait_author"] = author
    target = _backend_path(settings.social_style_approval_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8")
    return approval


def style_is_approved() -> bool:
    path = _backend_path(settings.social_style_approval_path)
    if not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value.get("style_digest") == current_style_digest()
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _verify_package(package: Path, manifest: dict[str, Any]) -> list[Path]:
    if manifest.get("published") is True:
        raise ValueError("pacote já marcado como publicado")
    if manifest.get("style_digest") != current_style_digest() or not style_is_approved():
        raise ValueError("estilo não aprovado ou alterado depois da aprovação")
    author = str((manifest.get("candidate") or {}).get("author") or "")
    approved_portrait = fetch_saint_portrait(author)
    if approved_portrait is None:
        raise ValueError(f"retrato ainda não aprovado para {author}")
    if _sha256_bytes(approved_portrait) != manifest.get("portrait_sha256"):
        raise ValueError("retrato aprovado difere daquele exibido na prévia")
    paths: list[Path] = []
    for artifact in manifest.get("artifacts") or []:
        path = package / str(artifact.get("file") or "")
        if not path.is_file() or _sha256_file(path) != artifact.get("sha256"):
            raise ValueError(f"artefato ausente ou alterado: {path.name}")
        paths.append(path)
    caption = package / "caption.txt"
    if _sha256_file(caption) != manifest.get("caption_sha256"):
        raise ValueError("legenda alterada depois da geração")
    return paths


def publish_package(package: str | Path, ledger: SocialLedger) -> str:
    # A trava vem antes de SFTP ou de qualquer chamada externa. Credencial
    # antiga/desmarcada não pode nem enviar as imagens ao servidor público.
    ensure_publication_enabled()
    package_path = Path(package)
    manifest = read_manifest(package_path)
    paths = _verify_package(package_path, manifest)
    fingerprint = str(manifest.get("source_fingerprint") or "")
    if fingerprint in ledger.published_fingerprints():
        raise ValueError("essa fonte já consta como publicada")

    urls = [upload_card(path.read_bytes(), f"{package_path.name}_{path.name}") for path in paths]
    media_id = publish_carousel_to_instagram(
        urls,
        (package_path / "caption.txt").read_text(encoding="utf-8"),
    )
    manifest["published"] = True
    manifest["status"] = "published"
    manifest["remote_media_id"] = media_id
    manifest["published_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    (package_path / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    ledger.append(
        {
            "event": "published",
            "source_fingerprint": fingerprint,
            "chunk_id": (manifest.get("candidate") or {}).get("chunk_id"),
            "author": (manifest.get("candidate") or {}).get("author"),
            "work_title": (manifest.get("candidate") or {}).get("work_title"),
            "remote_media_id": media_id,
            "package": str(package_path.resolve()),
        }
    )
    return media_id
