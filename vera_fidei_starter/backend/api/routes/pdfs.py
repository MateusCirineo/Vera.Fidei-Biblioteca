from __future__ import annotations

import os
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from models.database import SessionLocal, BookFile

router = APIRouter()

# Em Docker: /app/pdfs (via volume). Em dev local: pasta pdfs/ relativa ao backend.
_PDFS_DIR = os.environ.get("PDF_DIR") or os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "pdfs")
)


def _resolve_filename(stored_path: str) -> str | None:
    normalized = stored_path.replace("\\", "/")
    basename = normalized.split("/")[-1]
    if not basename:
        return None

    # Path relativo direto (registros corrigidos pelo fix_stored_paths.py)
    if not os.path.isabs(normalized):
        direct = os.path.join(_PDFS_DIR, normalized)
        if os.path.isfile(direct):
            return normalized

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
    # Fallback para stored_path absolutos legados (Windows ou Linux)
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
    # URL-encode para suportar acentos e espaços em nomes de pasta/arquivo
    encoded_filename = quote(filename, safe="/")
    response.headers["X-Accel-Redirect"] = f"/protected_pdfs/{encoded_filename}"
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename="{safe_name}"'
    return response
