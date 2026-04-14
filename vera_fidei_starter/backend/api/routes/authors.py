from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func
from pydantic import BaseModel

from models.database import SessionLocal, Book, Chunk
from schemas.book import BookResponse
from utils.author_detection import PATRISTIC_AUTHORS

router = APIRouter()


class AuthorCatalogEntry(BaseModel):
    name: str
    tradition: str    # "grega" | "latina" | "oriental"
    collection: str   # "PG" | "PL" | "PO"
    book_count: int
    chunk_count: int
    books: list[BookResponse]


def _chunk_count_for(db, book_id: int) -> int:
    return db.query(func.count(Chunk.id)).filter(Chunk.book_id == book_id).scalar() or 0


def _book_to_response(db, b: Book) -> BookResponse:
    return BookResponse(
        id=b.id,
        collection=b.collection,
        title=b.title,
        author=b.author,
        language=b.language,
        edition_label=b.edition_label,
        source_label=b.source_label,
        is_primary_source=b.is_primary_source,
        chunk_count=_chunk_count_for(db, b.id),
        library_section=b.library_section,
        patristic_tradition=b.patristic_tradition,
        document_type=b.document_type,
        canonical_author=b.canonical_author,
        canonical_title=b.canonical_title,
        pope=b.pope,
        document_year=b.document_year,
        is_ecumenical=b.is_ecumenical,
        document_status=b.document_status,
    )


@router.get("/catalog", response_model=list[AuthorCatalogEntry])
def get_authors_catalog() -> list[AuthorCatalogEntry]:
    """
    Retorna todos os Padres da Igreja conhecidos (PATRISTIC_AUTHORS),
    enriquecidos com os livros já catalogados no banco.
    Autores sem livros aparecem com book_count=0 e books=[].
    """
    with SessionLocal() as db:
        result: list[AuthorCatalogEntry] = []

        for author_name, data in PATRISTIC_AUTHORS.items():
            books = (
                db.query(Book)
                .filter(Book.canonical_author == author_name)
                .all()
            )
            total_chunks = sum(_chunk_count_for(db, b.id) for b in books)

            result.append(AuthorCatalogEntry(
                name=author_name,
                tradition=data["tradition"],
                collection=data["collection"],
                book_count=len(books),
                chunk_count=total_chunks,
                books=[_book_to_response(db, b) for b in books],
            ))

        # 1. autores com obras primeiro (book_count DESC), 2. sem obras (alfabético)
        result.sort(key=lambda e: (e.book_count == 0, -e.book_count, e.name.lower()))
        return result
