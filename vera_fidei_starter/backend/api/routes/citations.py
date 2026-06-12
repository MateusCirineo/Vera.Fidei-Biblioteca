from __future__ import annotations

import json

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
import io

logger = logging.getLogger(__name__)

from core.deps import get_current_user, get_optional_user, require_min_plan
from models.database import SessionLocal, User, VerificationHistory
from schemas.citation import VerifyCitationRequest, VerifyCitationResponse
from services.verification_service import VerificationService

router = APIRouter()
service = VerificationService()


@router.post("/verify-citation", response_model=VerifyCitationResponse)
def verify_citation(
    payload: VerifyCitationRequest,
    current_user: User | None = Depends(get_optional_user),
) -> VerifyCitationResponse:
    result = service.verify(payload)

    if current_user is not None:
        try:
            ref_json = result.reference.model_dump_json() if result.reference else None
            entry = VerificationHistory(
                user_id=current_user.id,
                citation_text=payload.quote,
                attributed_to=payload.attributed_to,
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
                db.refresh(entry)
                result = result.model_copy(update={"history_id": entry.id})
        except Exception:
            logger.exception("Falha ao salvar histórico para user_id=%s", current_user.id)

    return result


@router.get("/historico")
def get_historico(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> dict:
    offset = (page - 1) * per_page
    with SessionLocal() as db:
        total = db.query(VerificationHistory).filter(
            VerificationHistory.user_id == current_user.id
        ).count()
        entries = (
            db.query(VerificationHistory)
            .filter(VerificationHistory.user_id == current_user.id)
            .order_by(VerificationHistory.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        items = [
            {
                "id": e.id,
                "citation_text": e.citation_text,
                "attributed_to": e.attributed_to,
                "status_code": e.status_code,
                "label": e.label,
                "confidence": e.confidence,
                "author": e.author,
                "work": e.work,
                "matched_excerpt": e.matched_excerpt,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]
    return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.delete("/historico/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_historico(
    entry_id: int,
    current_user: User = Depends(get_current_user),
):
    with SessionLocal() as db:
        entry = db.get(VerificationHistory, entry_id)
        if not entry or entry.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrada não encontrada.")
        db.delete(entry)
        db.commit()


@router.get("/historico/{entry_id}/laudo")
def get_laudo(
    entry_id: int,
    current_user: User = Depends(require_min_plan("catequista")),
) -> StreamingResponse:
    from services.laudo_service import generate_laudo_pdf

    with SessionLocal() as db:
        entry = db.get(VerificationHistory, entry_id)
        if not entry or entry.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrada não encontrada.")
        pdf_bytes = generate_laudo_pdf(entry)

    filename = f"laudo_verafidei_{entry_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
