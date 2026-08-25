"""Busca de retrato histórico (domínio público / Wikimedia Commons) de um Padre
da Igreja ou santo, para o slide de capa do carrossel.

Nunca gera arte nova, e nunca "chuta" um resultado — só usa categorias do
Commons mapeadas manualmente pra cada Padre da Igreja conhecido, exatamente pra
evitar pegar a imagem da pessoa errada (ex: um clérigo qualquer que só tem
"de Santo Agostinho" no nome religioso, em vez do próprio Santo Agostinho).
Se o autor não estiver no mapa, devolve None — nunca inventa um substituto.
"""

from __future__ import annotations

import json
import hashlib
import logging
import urllib.parse
import urllib.request
from pathlib import Path

_log = logging.getLogger(__name__)

_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
_USER_AGENT = "VeraFidei-SocialBot/1.0 (contato: vera.fidei661@gmail.com)"

# Retratos curados manualmente (ex: por você, olhando a pintura certa e
# salvando aqui) têm prioridade ABSOLUTA sobre a busca automática — nome do
# arquivo = nome exato do autor como aparece em PATRISTIC_AUTHORS, com
# extensão .jpg/.jpeg/.png. Ex: "Santo Agostinho de Hipona.jpg".
_CURATED_PORTRAITS_DIR = Path(__file__).resolve().parent / "assets" / "portraits"
_CURATED_MANIFEST = _CURATED_PORTRAITS_DIR / "manifest.json"


def _approved_manifest() -> dict[str, dict]:
    if not _CURATED_MANIFEST.is_file():
        return {}
    try:
        value = json.loads(_CURATED_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _curated_portrait_path(
    saint_name: str, *, require_approved: bool = True
) -> Path | None:
    entry = _approved_manifest().get(saint_name)
    if not isinstance(entry, dict):
        return None
    if require_approved and entry.get("approved") is not True:
        return None
    filename = str(entry.get("file") or "").strip()
    if not filename or Path(filename).name != filename:
        return None
    path = _CURATED_PORTRAITS_DIR / filename
    return path if path.is_file() else None


def portrait_is_approved(saint_name: str) -> bool:
    return _curated_portrait_path(saint_name, require_approved=True) is not None


def approve_portrait(saint_name: str, *, expected_sha256: str) -> dict:
    path = _curated_portrait_path(saint_name, require_approved=False)
    if path is None:
        raise ValueError(f"retrato local não encontrado para {saint_name}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError("o retrato local mudou depois da geração da prévia")
    manifest = _approved_manifest()
    entry = manifest.get(saint_name)
    if not isinstance(entry, dict):
        raise ValueError("entrada do retrato ausente no manifesto")
    entry["approved"] = True
    entry["approved_sha256"] = actual
    entry["approval_source"] = "prévia completa aprovada pelo proprietário"
    _CURATED_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return entry

# Licenças aceitas (domínio público ou permissivas o bastante pra reuso comercial com atribuição)
_ACCEPTABLE_LICENSES = {
    "public domain", "pd", "cc0",
    "cc by 2.0", "cc by 3.0", "cc by 4.0",
    "cc by-sa 2.0", "cc by-sa 3.0", "cc by-sa 4.0",
}

# Nome canônico em português (como usado em utils/author_detection.PATRISTIC_AUTHORS)
# -> categoria do Wikimedia Commons correspondente ao Padre da Igreja certo.
# Mantido pequeno e curado de propósito: é melhor não achar retrato nenhum
# do que arriscar pegar a pessoa errada. Adicione mais entradas conforme
# forem necessárias, sempre conferindo manualmente a categoria certa antes.
SAINT_COMMONS_CATEGORY: dict[str, str] = {
    "Santo Agostinho de Hipona": "Augustine of Hippo",
    "São João Crisóstomo": "John Chrysostom",
    "São Gregório Magno": "Pope Gregory I",
    "São Jerônimo": "Jerome",
    "Orígenes": "Origen",
    "Santo Ireneu de Lião": "Irenaeus",
    "Boécio": "Boethius",
    "São Gregório de Nissa": "Gregory of Nyssa",
    "Eusébio de Cesareia": "Eusebius of Caesarea",
    "São Justino Mártir": "Justin Martyr",
    "São Cipriano de Cartago": "Cyprian",
    "São Leão Magno": "Pope Leo I",
    "São Ambrósio de Milão": "Ambrose",
    "Santo Ambrósio de Milão": "Ambrose",
    "São Basílio Magno": "Basil of Caesarea",
    "São Tomás de Aquino": "Thomas Aquinas",
    "São Policarpo de Esmirna": "Polycarp",
    "Santo Inácio de Antioquia": "Ignatius of Antioch",
    "São Clemente de Roma": "Pope Clement I",
    "São Cirilo de Alexandria": "Cyril of Alexandria",
    "São Cirilo de Jerusalém": "Cyril of Jerusalem",
    "São Beda, o Venerável": "Bede",
    "São Hilário de Poitiers": "Hilary of Poitiers",
    "São Atanásio de Alexandria": "Athanasius of Alexandria",
    "São Gregório de Nazianzo": "Gregory of Nazianzus",
}


def _api_get(params: dict) -> dict:
    url = f"{_COMMONS_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    # The request target is the constant HTTPS Commons endpoint above.
    with urllib.request.urlopen(req, timeout=20) as resp:  # nosec B310
        final = urllib.parse.urlsplit(resp.geturl())
        if final.scheme != "https" or final.hostname != "commons.wikimedia.org":
            raise ValueError("redirecionamento inesperado da API do Wikimedia Commons")
        return json.loads(resp.read().decode())


def _category_files(category: str, limit: int = 20) -> list[str]:
    data = _api_get({
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "file",
        "cmlimit": limit,
        "format": "json",
    })
    return [m["title"] for m in data.get("query", {}).get("categorymembers", [])]


def _image_info(title: str) -> dict | None:
    data = _api_get({
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "format": "json",
    })
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        info = (page.get("imageinfo") or [None])[0]
        if info:
            return info
    return None


def _is_acceptable(info: dict) -> bool:
    if info.get("width", 0) < 500 or info.get("height", 0) < 500:
        return False
    meta = info.get("extmetadata", {})
    license_name = (meta.get("LicenseShortName", {}).get("value") or "").strip().lower()
    if license_name in _ACCEPTABLE_LICENSES:
        return True
    restrictions = meta.get("Restrictions", {}).get("value", "")
    return not restrictions


def find_saint_portrait_url(saint_name: str) -> str | None:
    """Procura uma pintura/ícone histórico do santo, usando SOMENTE a
    categoria do Wikimedia Commons mapeada manualmente pra esse nome exato.
    Devolve None (sem chutar) se o autor não estiver em SAINT_COMMONS_CATEGORY
    ou se nada de licença aberta for encontrado na categoria."""
    category = SAINT_COMMONS_CATEGORY.get(saint_name)
    if not category:
        _log.warning("'%s' não está mapeado em SAINT_COMMONS_CATEGORY — sem retrato.", saint_name)
        return None

    try:
        titles = _category_files(category)
    except Exception as exc:
        _log.warning("Falha ao consultar categoria '%s': %s", category, exc)
        return None

    for title in titles:
        if not title.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        try:
            info = _image_info(title)
        except Exception as exc:
            _log.warning("Falha ao consultar imageinfo de %s: %s", title, exc)
            continue
        if info and _is_acceptable(info):
            return info["url"]
    return None


def download_image(url: str) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "upload.wikimedia.org"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
    ):
        raise ValueError("URL de retrato fora do Wikimedia Commons")
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    # The complete URL and any redirect are restricted to the HTTPS host above.
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
        final = urllib.parse.urlsplit(resp.geturl())
        if final.scheme != "https" or final.hostname != "upload.wikimedia.org":
            raise ValueError("redirecionamento de retrato fora do Wikimedia Commons")
        return resp.read()


def fetch_saint_portrait(
    saint_name: str,
    *,
    allow_pending_local: bool = False,
    allow_unapproved_research: bool = False,
) -> bytes | None:
    """Encontra um retrato histórico do santo. Prioridade:
    1. Retrato curado manualmente em assets/portraits/{saint_name}.(jpg|png);
    2. Opcionalmente, somente em modo de pesquisa, categoria mapeada do
       Wikimedia Commons. Esse resultado NÃO é aprovado para publicação.

    Por padrão devolve ``None`` quando ainda não há retrato aprovado. Assim um
    resultado de busca nunca é publicado automaticamente como se fosse o santo
    correto."""
    curated = _curated_portrait_path(
        saint_name, require_approved=not allow_pending_local
    )
    if curated is not None:
        return curated.read_bytes()

    if not allow_unapproved_research:
        _log.warning("'%s' ainda não tem retrato aprovado no manifesto.", saint_name)
        return None

    url = find_saint_portrait_url(saint_name)
    if not url:
        return None
    try:
        return download_image(url)
    except Exception as exc:
        _log.warning("Falha ao baixar retrato de %s (%s): %s", saint_name, url, exc)
        return None
