from __future__ import annotations

import hmac

from fastapi import Cookie, Header, HTTPException, Query, status

from core.config import settings
from core.deps import get_current_user


def require_api_key(
    x_api_key: str = Header(default=""),
    api_key: str = Query(default=""),
    authorization: str = Header(default=""),
    vf_token: str | None = Cookie(default=None),
) -> None:
    configured = (settings.api_key or "").strip()
    provided_api_keys = (
        x_api_key.strip() if isinstance(x_api_key, str) else "",
        api_key.strip() if isinstance(api_key, str) else "",
    )
    if configured and any(
        provided and hmac.compare_digest(provided, configured)
        for provided in provided_api_keys
    ):
        return

    # Browser and native clients authenticate with their normal user session;
    # they must never need the server-wide API key embedded in the bundle.
    bearer = authorization.strip() if isinstance(authorization, str) else ""
    cookie_token = vf_token.strip() if isinstance(vf_token, str) else ""
    if bearer or cookie_token:
        get_current_user(authorization=bearer, vf_token=cookie_token or None)
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credencial inválida ou ausente.",
    )
