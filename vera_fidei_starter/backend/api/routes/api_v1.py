from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from core.api_key_auth import require_vf_api_key
from models.database import SessionLocal, ApiKey, User, VerificationHistory
from schemas.citation import VerifyCitationRequest
from services.verification_service import VerificationService

router = APIRouter()
_service = VerificationService()


class VerifyPublicRequest(BaseModel):
    citacao: str = Field(..., min_length=3)
    autor: str | None = None


@router.post("/verificar")
def verificar_publica(
    payload: VerifyPublicRequest,
    current_user: User = Depends(require_vf_api_key),
) -> dict:
    request = VerifyCitationRequest(
        quote=payload.citacao,
        attributed_to=payload.autor or "Desconhecido",
    )
    result = _service.verify(request)

    try:
        ref_json = result.reference.model_dump_json() if result.reference else None
        entry = VerificationHistory(
            user_id=current_user.id,
            citation_text=payload.citacao,
            attributed_to=payload.autor,
            status_code=result.status_code,
            label=result.label,
            confidence=result.confidence,
            author=result.author,
            work=result.work,
            reference_json=ref_json,
            matched_excerpt=result.matched_excerpt,
            explanation=result.explanation,
            response_json=result.model_dump_json(),
        )
        with SessionLocal() as db:
            db.add(entry)
            db.commit()
    except Exception:
        pass

    return result.model_dump()


@router.get("/status")
def api_status(
    current_user: User = Depends(require_vf_api_key),
    x_vf_api_key: str = Header(default=""),
) -> dict:
    usage_count = 0
    if x_vf_api_key:
        key_hash = hashlib.sha256(x_vf_api_key.encode()).hexdigest()
        with SessionLocal() as db:
            api_key = (
                db.query(ApiKey)
                .filter(ApiKey.key_hash == key_hash, ApiKey.user_id == current_user.id)
                .first()
            )
            if api_key:
                usage_count = api_key.usage_count
    return {
        "status": "ok",
        "plan": current_user.plan,
        "usage_count": usage_count,
    }
