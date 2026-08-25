from __future__ import annotations

import datetime

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext

from core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(
    user_id: int,
    session_version: int = 0,
    *,
    expires_minutes: int | None = None,
) -> str:
    lifetime_minutes = settings.jwt_expire_minutes if expires_minutes is None else int(expires_minutes)
    if lifetime_minutes <= 0:
        raise ValueError("expires_minutes must be positive")
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=lifetime_minutes)
    payload = {"sub": str(user_id), "sv": int(session_version), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado.")
