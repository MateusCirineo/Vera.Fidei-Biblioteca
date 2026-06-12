from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from models.database import BookFile, SessionLocal
from storage.pdf_storage import get_pdf_storage

router = APIRouter()


@router.get("/{file_id}")
def serve_pdf(file_id: int, request: Request) -> Response:
    with SessionLocal() as db:
        book_file = db.get(BookFile, file_id)
        if book_file is None:
            raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")

    return get_pdf_storage().response_for_pdf(
        stored_path=book_file.stored_path,
        original_filename=book_file.original_filename,
        range_header=request.headers.get("range"),
    )
