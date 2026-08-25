"""Métricas do Instagram (Graph API) — só leitura, nunca publica nem modifica nada.

Reaproveita a mesma autenticação de instagram_publish.py. Requer a permissão
`instagram_business_manage_insights` ativada no painel do app (Instagram >
Permissões e recursos, em developers.facebook.com) — as outras 4 permissões
já foram ativadas antes, essa ficou pendente por não ser necessária pra publicar.
"""

from __future__ import annotations

from app.social.instagram_publish import (
    InstagramApiError,
    _base,
    _credentials,
    _graph_request,
)
from core.config import settings

MEDIA_FIELDS = "id,caption,media_type,media_product_type,timestamp,permalink"
MEDIA_METRICS = "reach,likes,comments,saved,shares,total_interactions"
_FALLBACK_METRICS = "reach,likes,comments"


def account_summary() -> dict:
    """Seguidores, quantidade de posts etc. da conta conectada."""
    token, user_id = _credentials()
    return _graph_request(
        _base(user_id),
        params={"fields": "followers_count,media_count,username", "access_token": token},
    )


def list_recent_media(limit: int = 25) -> list[dict]:
    token, user_id = _credentials()
    value = _graph_request(
        f"{_base(user_id)}/media",
        params={"fields": MEDIA_FIELDS, "limit": str(limit), "access_token": token},
    )
    return list(value.get("data") or [])


def get_media_insights(media_id: str) -> dict[str, int | str]:
    token, _ = _credentials()
    version = settings.instagram_graph_api_version.strip()
    url = f"https://graph.instagram.com/{version}/{media_id}/insights"
    try:
        value = _graph_request(url, params={"metric": MEDIA_METRICS, "access_token": token})
    except InstagramApiError:
        # Álbuns/carrosséis nem sempre aceitam todas as métricas de uma vez;
        # tenta um conjunto mais restrito antes de desistir.
        try:
            value = _graph_request(url, params={"metric": _FALLBACK_METRICS, "access_token": token})
        except InstagramApiError as exc:
            return {"error": str(exc)}

    result: dict[str, int | str] = {}
    for item in value.get("data") or []:
        name = item.get("name")
        values = item.get("values") or []
        if name and values:
            result[str(name)] = values[0].get("value", 0)
    return result


def build_report(limit: int = 25) -> list[dict]:
    """Junta cada post recente com as métricas de engajamento dele."""
    report = []
    for media in list_recent_media(limit=limit):
        media_id = media.get("id")
        if not media_id:
            continue
        report.append({**media, "insights": get_media_insights(str(media_id))})
    return report
