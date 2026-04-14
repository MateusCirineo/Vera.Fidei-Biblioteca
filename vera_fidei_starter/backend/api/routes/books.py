from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func

from models.database import SessionLocal, Book, Chunk, BookFile
from schemas.book import BookCreate, BookResponse, BookFileResponse, IngestPDFResponse, AutoIngestResponse, BookStatusResponse
from services.ingestion_service import get_processing_status
from services.ingestion_service import IngestionService
from utils.language import classify_book

router = APIRouter()
_ingestion_service: IngestionService | None = None


def _get_ingestion_service() -> IngestionService:
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service


def _chunk_count(db, book_id: int) -> int:
    return db.query(func.count(Chunk.id)).filter(Chunk.book_id == book_id).scalar() or 0


def _book_to_response(db, b: Book) -> BookResponse:
    files = db.query(BookFile).filter(BookFile.book_id == b.id).all()
    return BookResponse(
        id=b.id,
        collection=b.collection,
        title=b.title,
        author=b.author,
        language=b.language,
        edition_label=b.edition_label,
        source_label=b.source_label,
        is_primary_source=b.is_primary_source,
        chunk_count=_chunk_count(db, b.id),
        library_section=b.library_section,
        patristic_tradition=b.patristic_tradition,
        document_type=b.document_type,
        canonical_author=b.canonical_author,
        canonical_title=b.canonical_title,
        pope=b.pope,
        document_year=b.document_year,
        is_ecumenical=b.is_ecumenical,
        document_status=b.document_status,
        files=[BookFileResponse.model_validate(f) for f in files] if files else None,
    )


@router.get("", response_model=list[BookResponse])
def list_books() -> list[BookResponse]:
    with SessionLocal() as db:
        books = db.query(Book).all()

        # Backfill: classificar livros sem library_section (migração incremental)
        needs_commit = False
        for b in books:
            if b.library_section is None and b.collection is not None:
                section, tradition, doctype = classify_book(
                    b.collection, b.language, b.is_primary_source
                )
                b.library_section = section
                b.patristic_tradition = tradition
                b.document_type = doctype
                needs_commit = True
        if needs_commit:
            db.commit()

        return [_book_to_response(db, b) for b in books]


@router.post("", response_model=BookResponse, status_code=201)
def create_book(payload: BookCreate) -> BookResponse:
    with SessionLocal() as db:
        duplicate = (
            db.query(Book)
            .filter(
                Book.title == payload.title,
                Book.author == payload.author,
                Book.edition_label == payload.edition_label,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="Já existe um livro com mesmo título, autor e edição.",
            )

        book = Book(
            collection=payload.collection,
            title=payload.title,
            author=payload.author,
            language=payload.language,
            edition_label=payload.edition_label,
            source_label=payload.source_label,
            is_primary_source=payload.is_primary_source,
            library_section=payload.library_section,
            patristic_tradition=payload.patristic_tradition,
            document_type=payload.document_type,
            canonical_author=payload.canonical_author,
            canonical_title=payload.canonical_title,
            pope=payload.pope,
            document_year=payload.document_year,
            is_ecumenical=payload.is_ecumenical,
            document_status=payload.document_status,
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        return BookResponse(
            id=book.id,
            collection=book.collection,
            title=book.title,
            author=book.author,
            language=book.language,
            edition_label=book.edition_label,
            source_label=book.source_label,
            is_primary_source=book.is_primary_source,
            chunk_count=0,
            library_section=book.library_section,
            patristic_tradition=book.patristic_tradition,
            document_type=book.document_type,
            canonical_author=book.canonical_author,
            canonical_title=book.canonical_title,
            pope=book.pope,
            document_year=book.document_year,
            is_ecumenical=book.is_ecumenical,
            document_status=book.document_status,
        )


@router.post("/ingest-auto", response_model=AutoIngestResponse, status_code=201)
async def ingest_auto(
    file: UploadFile = File(...),
    title_override: str | None = Form(None),
    editor: str | None = Form(None),
    translator: str | None = Form(None),
) -> AutoIngestResponse:
    """
    Upload zero-input: extrai texto, detecta autor/título/coleção/idioma,
    cria o Book e indexa tudo automaticamente.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="O arquivo enviado deve ser um PDF.")

    pdf_bytes = await file.read()
    service = _get_ingestion_service()
    result = service.ingest_auto(
        pdf_bytes=pdf_bytes,
        original_filename=file.filename,
        title_override=title_override or None,
        editor=editor or None,
        translator=translator or None,
    )
    return AutoIngestResponse(**result)


@router.get("/{book_id}/status", response_model=BookStatusResponse)
def get_book_status(book_id: int) -> BookStatusResponse:
    """Retorna o status de processamento e quantidade de chunks indexados."""
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=404, detail="Livro não encontrado.")
        chunks = db.query(func.count(Chunk.id)).filter(Chunk.book_id == book_id).scalar() or 0
    return BookStatusResponse(
        book_id=book_id,
        status=get_processing_status(book_id),
        chunks_indexed=chunks,
    )


@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: int) -> BookResponse:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=404, detail="Livro não encontrado.")
        return _book_to_response(db, book)


@router.delete("/{book_id}")
def delete_book(book_id: int) -> Response:
    """Remove um livro e todos os seus chunks, arquivos e entradas de índice."""
    service = _get_ingestion_service()
    service.delete_book(book_id)
    return Response(status_code=204)


class BookFileMetaUpdate(BaseModel):
    editor: str | None = None
    translator: str | None = None


@router.patch("/{book_id}/files/{file_id}/metadata")
def update_book_file_metadata(
    book_id: int,
    file_id: int,
    payload: BookFileMetaUpdate,
) -> dict:
    """Atualiza editor e tradutor de um BookFile existente."""
    with SessionLocal() as db:
        book_file = db.get(BookFile, file_id)
        if book_file is None or book_file.book_id != book_id:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
        book_file.editor = payload.editor or None
        book_file.translator = payload.translator or None
        db.commit()
    return {"ok": True}


@router.post("/{book_id}/ingest-pdf", response_model=IngestPDFResponse, status_code=201)
async def ingest_pdf(
    book_id: int,
    file: UploadFile = File(...),
    volume_number: int | None = Form(None),
    editor: str | None = Form(None),
    translator: str | None = Form(None),
) -> IngestPDFResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="O arquivo enviado deve ser um PDF.")

    pdf_bytes = await file.read()
    service = _get_ingestion_service()
    book_file, chunks_indexed = service.ingest(
        book_id=book_id,
        pdf_bytes=pdf_bytes,
        original_filename=file.filename,
        volume_number=volume_number,
        editor=editor,
        translator=translator,
    )
    return IngestPDFResponse(
        book_id=book_id,
        file_id=book_file.id,
        chunks_indexed=chunks_indexed,
        volume_number=volume_number,
        editor=editor,
        translator=translator,
    )

