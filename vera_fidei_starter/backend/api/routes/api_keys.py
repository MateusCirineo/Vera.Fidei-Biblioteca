from __future__ import annotations

import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.deps import get_current_user, require_min_plan
from models.database import SessionLocal, ApiKey, User

router = APIRouter()


class CreateApiKeyRequest(BaseModel):
    label: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: CreateApiKeyRequest,
    current_user: User = Depends(require_min_plan("magisterio")),
) -> dict:
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    with SessionLocal() as db:
        api_key = ApiKey(
            user_id=current_user.id,
            key_hash=key_hash,
            label=payload.label,
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        return {
            "id": api_key.id,
            "key": raw_key,
            "label": api_key.label,
            "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
            "warning": "Guarde esta chave em segurança — ela não será exibida novamente.",
        }


@router.get("")
def list_api_keys(
    current_user: User = Depends(require_min_plan("magisterio")),
) -> dict:
    with SessionLocal() as db:
        keys = (
            db.query(ApiKey)
            .filter(ApiKey.user_id == current_user.id)
            .order_by(ApiKey.created_at.desc())
            .all()
        )
        items = [
            {
                "id": k.id,
                "label": k.label,
                "is_active": k.is_active,
                "usage_count": k.usage_count,
                "created_at": k.created_at.isoformat() if k.created_at else None,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            }
            for k in keys
        ]
    return {"items": items}


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def revoke_api_key(
    key_id: int,
    current_user: User = Depends(require_min_plan("magisterio")),
) -> None:
    with SessionLocal() as db:
        api_key = db.get(ApiKey, key_id)
        if not api_key or api_key.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chave não encontrada.",
            )
        api_key.is_active = False
        db.commit()
