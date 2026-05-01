from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from models.database import SessionLocal, BookFile

router = APIRouter()
_PDFS_DIR = "/app/pdfs"


def _resolve_filename(stored_path: str) -> str | None:
    basename = stored_path.replace("\\", "/").split("/")[-1]
    if not basename:
        return None

    # Direct match in root (happy path for numbered files)
    if os.path.isfile(os.path.join(_PDFS_DIR, basename)):
        return basename

    # Root-level suffix match (re-uploaded files with ID prefix)
    try:
        for fname in sorted(os.listdir(_PDFS_DIR)):
            if fname.endswith(basename):
                return fname
    except OSError:
        pass

    # Recursive search through subdirectories (documentos_pontificios etc.)
    try:
        for root, _dirs, files in os.walk(_PDFS_DIR):
            for f in files:
                if f == basename:
                    rel = os.path.relpath(os.path.join(root, f), _PDFS_DIR)
                    return rel.replace("\\", "/")
    except OSError:
        pass

    return None


@router.get("/{file_id}")
def serve_pdf(file_id: int) -> Response:
    with SessionLocal() as db:
        book_file = db.get(BookFile, file_id)
        if book_file is None:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    filename = _resolve_filename(book_file.stored_path)
    if not filename:
        raise HTTPException(status_code=404, detail="PDF não encontrado no disco.")

    safe_name = book_file.original_filename.replace('"', "'")
    response = Response()
    response.headers["X-Accel-Redirect"] = f"/protected_pdfs/{filename}"
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename="{safe_name}"'
    return response
