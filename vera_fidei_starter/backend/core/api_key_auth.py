from __future__ import annotations

import hashlib
import datetime

from fastapi import Header, HTTPException, status

from models.database import SessionLocal, ApiKey, User
from core.deps import PLAN_ORDER


def require_vf_api_key(x_vf_api_key: str = Header(default="")) -> User:
    if not x_vf_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-VF-Api-Key ausente.",
        )
    key_hash = hashlib.sha256(x_vf_api_key.encode()).hexdigest()
    with SessionLocal() as db:
        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True)  # noqa: E712
            .first()
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key inválida ou revogada.",
            )
        user = db.get(User, api_key.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário inativo.",
            )
        if PLAN_ORDER.index(user.plan) < PLAN_ORDER.index("magisterio"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requer plano Magistério.",
            )
        api_key.usage_count += 1
        api_key.last_used_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(user)
        db.expunge(user)
    return user
