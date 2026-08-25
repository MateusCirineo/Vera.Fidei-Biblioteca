"""Upload seguro e publicação pela API oficial do Instagram."""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from core.config import settings


_log = logging.getLogger(__name__)
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+$")


class PublicationBlocked(RuntimeError):
    pass


class InstagramApiError(RuntimeError):
    pass


def _publication_gate() -> None:
    if not settings.instagram_publish_enabled:
        raise PublicationBlocked(
            "INSTAGRAM_PUBLISH_ENABLED=false: somente prévias estão autorizadas"
        )
    if not settings.instagram_credentials_rotated_at.strip() and not settings.instagram_allow_exposed_credentials_once:
        raise PublicationBlocked(
            "credenciais ainda não foram marcadas como rotacionadas após a exposição"
        )


def ensure_publication_enabled() -> None:
    """Falha antes de qualquer upload quando a publicação não está liberada."""
    _publication_gate()
    _credentials()


def _credentials() -> tuple[str, str]:
    token = settings.instagram_access_token.strip()
    user_id = settings.instagram_business_account_id.strip()
    if not token or not user_id:
        raise PublicationBlocked("token/Instagram User ID não configurados")
    return token, user_id


def upload_card(image_bytes: bytes, filename: str) -> str:
    if not _SAFE_FILENAME.fullmatch(filename):
        raise ValueError(f"nome de arquivo inseguro: {filename!r}")
    if not settings.deploy_ssh_host:
        raise PublicationBlocked("DEPLOY_SSH_HOST não configurado")
    if not settings.deploy_ssh_key_path and not settings.deploy_ssh_password:
        raise PublicationBlocked("configure chave SSH ou senha de implantação")

    import paramiko

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    if settings.deploy_ssh_known_hosts:
        known_hosts = Path(settings.deploy_ssh_known_hosts)
        if not known_hosts.is_file():
            raise PublicationBlocked(f"arquivo known_hosts não encontrado: {known_hosts}")
        client.load_host_keys(str(known_hosts))
    # RejectPolicy impede aceitar silenciosamente um servidor falso.
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    connect_kwargs: dict = {
        "hostname": settings.deploy_ssh_host,
        "username": settings.deploy_ssh_user,
        "timeout": 20,
        "look_for_keys": True,
        "allow_agent": True,
    }
    if settings.deploy_ssh_key_path:
        connect_kwargs["key_filename"] = settings.deploy_ssh_key_path
    elif settings.deploy_ssh_password:
        connect_kwargs["password"] = settings.deploy_ssh_password

    client.connect(**connect_kwargs)
    try:
        sftp = client.open_sftp()
        try:
            remote_path = f"{settings.deploy_social_cards_dir.rstrip('/')}/{filename}"
            sftp.putfo(BytesIO(image_bytes), remote_path)
        finally:
            sftp.close()
    finally:
        client.close()

    return f"{settings.deploy_social_cards_public_base_url.rstrip('/')}/{urllib.parse.quote(filename)}"


def _redact(value: str) -> str:
    token = settings.instagram_access_token.strip()
    if token:
        value = value.replace(token, "[REDACTED_TOKEN]")
    return re.sub(r"(?i)(access_token[=:])[^&\s]+", r"\1[REDACTED_TOKEN]", value)


def _graph_request(
    url: str,
    *,
    method: str = "GET",
    params: dict[str, str] | None = None,
) -> dict:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "graph.instagram.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
    ):
        raise InstagramApiError("destino da Instagram API nÃ£o autorizado")
    params = params or {}
    if method == "GET":
        separator = "&" if "?" in url else "?"
        request_url = url + (separator + urllib.parse.urlencode(params) if params else "")
        request = urllib.request.Request(request_url, method="GET")
    else:
        payload = urllib.parse.urlencode(params).encode("utf-8")
        request = urllib.request.Request(url, data=payload, method=method)
    try:
        # The complete URL and any redirect are restricted to the HTTPS host above.
        with urllib.request.urlopen(request, timeout=40) as response:  # nosec B310
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != "graph.instagram.com":
                raise InstagramApiError("redirecionamento da Instagram API nÃ£o autorizado")
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = _redact(exc.read().decode(errors="replace"))
        raise InstagramApiError(f"Instagram API HTTP {exc.code}: {body[:700]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise InstagramApiError(f"falha de rede na Instagram API: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise InstagramApiError("resposta inesperada da Instagram API")
    return value


def _base(user_id: str) -> str:
    version = settings.instagram_graph_api_version.strip()
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise PublicationBlocked("INSTAGRAM_GRAPH_API_VERSION inválida")
    return f"https://graph.instagram.com/{version}/{user_id}"


def validate_instagram_connection() -> dict[str, str | bool]:
    """Consulta somente metadados seguros; não cria container nem publicação."""
    token, user_id = _credentials()
    try:
        value = _graph_request(
            _base(user_id),
            params={"fields": "id,username,account_type", "access_token": token},
        )
    except InstagramApiError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": bool(value.get("id")),
        "username": str(value.get("username") or ""),
        "account_type": str(value.get("account_type") or ""),
    }


def _wait_until_ready(container_id: str, token: str, *, timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    url = f"https://graph.instagram.com/{settings.instagram_graph_api_version}/{container_id}"
    while time.monotonic() < deadline:
        value = _graph_request(
            url,
            params={"fields": "status_code,status", "access_token": token},
        )
        status = str(value.get("status_code") or "").upper()
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED"}:
            raise InstagramApiError(f"container {container_id} terminou com status {status}")
        time.sleep(3)
    raise InstagramApiError(f"container {container_id} não ficou pronto em {timeout_seconds}s")


def publish_to_instagram(image_url: str, caption: str) -> str:
    _publication_gate()
    token, user_id = _credentials()
    base = _base(user_id)
    container = _graph_request(
        f"{base}/media",
        method="POST",
        params={"image_url": image_url, "caption": caption, "access_token": token},
    )
    creation_id = str(container.get("id") or "")
    if not creation_id:
        raise InstagramApiError("container de imagem sem id")
    _wait_until_ready(creation_id, token)
    result = _graph_request(
        f"{base}/media_publish",
        method="POST",
        params={"creation_id": creation_id, "access_token": token},
    )
    media_id = str(result.get("id") or "")
    if not media_id:
        raise InstagramApiError("media_publish sem id")
    return media_id


def publish_carousel_to_instagram(image_urls: list[str], caption: str) -> str:
    _publication_gate()
    if not 2 <= len(image_urls) <= 10:
        raise ValueError("carrossel precisa de 2 a 10 imagens")
    token, user_id = _credentials()
    base = _base(user_id)

    children: list[str] = []
    for image_url in image_urls:
        value = _graph_request(
            f"{base}/media",
            method="POST",
            params={
                "image_url": image_url,
                "is_carousel_item": "true",
                "access_token": token,
            },
        )
        child_id = str(value.get("id") or "")
        if not child_id:
            raise InstagramApiError("item do carrossel sem id")
        _wait_until_ready(child_id, token)
        children.append(child_id)

    parent = _graph_request(
        f"{base}/media",
        method="POST",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": token,
        },
    )
    creation_id = str(parent.get("id") or "")
    if not creation_id:
        raise InstagramApiError("container pai do carrossel sem id")
    _wait_until_ready(creation_id, token)
    result = _graph_request(
        f"{base}/media_publish",
        method="POST",
        params={"creation_id": creation_id, "access_token": token},
    )
    media_id = str(result.get("id") or "")
    if not media_id:
        raise InstagramApiError("publicação do carrossel sem id")
    return media_id
