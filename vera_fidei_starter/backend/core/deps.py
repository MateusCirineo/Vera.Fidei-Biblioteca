from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from core.plans import ensure_owner_access, has_min_plan, is_owner_email
from core.security import decode_token
from models.database import SessionLocal, User


def _get_db() -> Session:
    return SessionLocal()


def _get_user_by_id(user_id: int) -> User:
    with _get_db() as db:
        user = db.get(User, user_id)
        if user and ensure_owner_access(user):
            db.commit()
            db.refresh(user)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado ou inativo.")
    return user


def _session_token(authorization: str, cookie_token: str | None) -> str:
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token mal formatado.")
        return authorization.removeprefix("Bearer ")
    return cookie_token or ""


def _user_from_session_token(token: str) -> User:
    payload = decode_token(token)
    try:
        user_id = int(payload["sub"])
        token_session_version = int(payload.get("sv", 0) or 0)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
        ) from exc

    user = _get_user_by_id(user_id)
    current_session_version = int(getattr(user, "session_version", 0) or 0)
    if token_session_version != current_session_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão revogada. Entre novamente.",
        )
    return user


def get_current_user(
    authorization: str = Header(default=""),
    vf_token: str | None = Cookie(default=None),
) -> User:
    token = _session_token(authorization, vf_token)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente ou mal formatado.")
    return _user_from_session_token(token)


def get_optional_user(
    authorization: str = Header(default=""),
    vf_token: str | None = Cookie(default=None),
) -> User | None:
    token = _session_token(authorization, vf_token)
    if not token:
        return None
    return _user_from_session_token(token)


def require_owner(user: User = Depends(get_current_user)) -> User:
    """Allow administrative operations only for the configured owner account."""
    if not is_owner_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito ao administrador do Vera.Fidei.",
        )
    return user


def require_min_plan(min_plan: str):
    def _check(user: User = Depends(get_current_user)) -> User:
        if not has_min_plan(user.plan, min_plan):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requer plano '{min_plan}' ou superior.",
            )
        return user

    return _check
