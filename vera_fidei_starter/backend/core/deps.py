from __future__ import annotations

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from core.security import decode_token
from models.database import SessionLocal, User


def _get_db() -> Session:
    return SessionLocal()


def _get_user_by_id(user_id: int) -> User:
    with _get_db() as db:
        user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado ou inativo.")
    return user


def get_current_user(authorization: str = Header(default="")) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente ou mal formatado.")
    token = authorization.removeprefix("Bearer ")
    payload = decode_token(token)
    user_id = int(payload["sub"])
    return _get_user_by_id(user_id)


def get_optional_user(authorization: str = Header(default="")) -> User | None:
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token mal formatado.")
    token = authorization.removeprefix("Bearer ")
    payload = decode_token(token)
    user_id = int(payload["sub"])
    return _get_user_by_id(user_id)


PLAN_ORDER = ["fiel", "catequista", "apologeta", "patristico", "magisterio"]


def require_min_plan(min_plan: str):
    from fastapi import Depends

    def _check(user: User = Depends(get_current_user)) -> User:
        if PLAN_ORDER.index(user.plan) < PLAN_ORDER.index(min_plan):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requer plano '{min_plan}' ou superior.",
            )
        return user

    return _check
