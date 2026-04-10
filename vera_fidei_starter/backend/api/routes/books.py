from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from sqlalchemy import func

from models.database import SessionLocal, Book, Chunk
from schemas.book import BookCreate, BookResponse, BookFileResponse, IngestPDFResponse
from services.ingestion_service import IngestionService

router = APIRouter()
_ingestion_service: IngestionService | None = None


def _get_ingestion_service() -> IngestionService:
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service


def _chunk_count(db, book_id: int) -> int:
    return db.query(func.count(Chunk.id)).filter(Chunk.book_id == book_id).scalar() or 0


@router.get("", response_model=list[BookResponse])
def list_books() -> list[BookResponse]:
    with SessionLocal() as db:
        books = db.query(Book).all()
        return [
            BookResponse(
                id=b.id,
                collection=b.collection,
                title=b.title,
                author=b.author,
                language=b.language,
                edition_label=b.edition_label,
                source_label=b.source_label,
                is_primary_source=b.is_primary_source,
                chunk_count=_chunk_count(db, b.id),
            )
            for b in books
        ]


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
        )


@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: int) -> BookResponse:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=404, detail="Livro não encontrado.")
        return BookResponse(
            id=book.id,
            collection=book.collection,
            title=book.title,
            author=book.author,
            language=book.language,
            edition_label=book.edition_label,
            source_label=book.source_label,
            is_primary_source=book.is_primary_source,
            chunk_count=_chunk_count(db, book.id),
        )


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
