from fastapi import Header, HTTPException, Query, status
from core.config import settings


def require_api_key(
    x_api_key: str = Header(default=""),
    api_key: str = Query(default=""),
) -> None:
    configured = settings.api_key.strip()
    if not configured:
        return
    provided = x_api_key or api_key
    if provided != configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida ou ausente.",
        )
