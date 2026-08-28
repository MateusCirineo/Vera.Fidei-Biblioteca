from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from core.deps import get_current_user
from models.database import BookFile, SessionLocal, User
from storage.pdf_storage import get_pdf_storage

router = APIRouter()


@router.get("/{file_id}")
def serve_pdf(
    file_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    with SessionLocal() as db:
        book_file = db.get(BookFile, file_id)
        if book_file is None:
            raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")

    stream_pdf = request.query_params.get("stream") in {"1", "true", "sim"}
    return get_pdf_storage().response_for_pdf(
        stored_path=book_file.stored_path,
        original_filename=book_file.original_filename,
        range_header=request.headers.get("range"),
        stream_pdf=stream_pdf,
        as_attachment=request.query_params.get("download") in {"1", "true", "sim"},
    )
