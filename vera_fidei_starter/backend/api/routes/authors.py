from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, or_
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


def _book_to_response_with_count(b: Book, chunk_count: int) -> BookResponse:
    return BookResponse(
        id=b.id,
        collection=b.collection,
        title=b.title,
        author=b.author,
        language=b.language,
        edition_label=b.edition_label,
        source_label=b.source_label,
        is_primary_source=b.is_primary_source,
        chunk_count=chunk_count,
        library_section=b.library_section,
        patristic_tradition=b.patristic_tradition,
        document_type=b.document_type,
        canonical_author=b.canonical_author,
        canonical_title=b.canonical_title,
        pope=b.pope,
        document_year=b.document_year,
        is_ecumenical=b.is_ecumenical,
        document_status=b.document_status,
        volume_number=b.volume_number,
    )


@router.get("/catalog", response_model=list[AuthorCatalogEntry])
def get_authors_catalog() -> list[AuthorCatalogEntry]:
    """
    Retorna todos os Padres da Igreja conhecidos (PATRISTIC_AUTHORS),
    enriquecidos com os livros já catalogados no banco.

    Inclui tanto livros com canonical_author direto quanto volumes coletânea
    que tenham chunks marcados com chunk_author para este autor.
    Autores sem livros aparecem com book_count=0 e books=[].
    """
    with SessionLocal() as db:
        # Batch: chunk counts por book_id (para livros diretos)
        all_direct_counts: dict[int, int] = dict(
            db.query(Chunk.book_id, func.count(Chunk.id))
            .group_by(Chunk.book_id)
            .all()
        )
        # Batch: chunk counts por (book_id, chunk_author) (para coletâneas)
        all_author_counts: dict[tuple, int] = {
            (book_id, author): count
            for book_id, author, count in
            db.query(Chunk.book_id, Chunk.chunk_author, func.count(Chunk.id))
            .filter(Chunk.chunk_author.isnot(None))
            .group_by(Chunk.book_id, Chunk.chunk_author)
            .all()
        }

        result: list[AuthorCatalogEntry] = []

        for author_name, data in PATRISTIC_AUTHORS.items():
            # 1. Livros com canonical_author direto
            direct_books = (
                db.query(Book)
                .filter(Book.canonical_author == author_name)
                .all()
            )
            direct_ids = {b.id for b in direct_books}

            # 2. Volumes coletânea onde o autor aparece como chunk_author
            collectanea_books = (
                db.query(Book)
                .join(Chunk, Chunk.book_id == Book.id)
                .filter(Chunk.chunk_author == author_name)
                .filter(Book.id.notin_(direct_ids))
                .distinct()
                .all()
            )

            books = direct_books + collectanea_books

            total_chunks = 0
            book_responses: list[BookResponse] = []
            for b in books:
                if b.id in direct_ids:
                    count = all_direct_counts.get(b.id, 0)
                else:
                    count = all_author_counts.get((b.id, author_name), 0)
                total_chunks += count
                book_responses.append(_book_to_response_with_count(b, count))

            result.append(AuthorCatalogEntry(
                name=author_name,
                tradition=data["tradition"],
                collection=data["collection"],
                book_count=len(books),
                chunk_count=total_chunks,
                books=book_responses,
            ))

        # 1. autores com obras primeiro (book_count DESC), 2. sem obras (alfabético)
        result.sort(key=lambda e: (e.book_count == 0, -e.book_count, e.name.lower()))
        return result
