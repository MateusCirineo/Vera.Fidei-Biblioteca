from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from models.database import SessionLocal, BookFile

router = APIRouter()


@router.get("/{file_id}")
def serve_pdf(file_id: int) -> FileResponse:
    """
    Serve o arquivo PDF armazenado. O frontend deve abrir com
    o fragmento de página correto, ex.: /pdfs/3#page=256
    """
    with SessionLocal() as db:
        book_file = db.get(BookFile, file_id)
        if book_file is None:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    if not os.path.exists(book_file.stored_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no disco.")

    return FileResponse(
        path=book_file.stored_path,
        media_type="application/pdf",
        filename=book_file.original_filename,
    )
