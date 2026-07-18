"""
Fast text-only indexing for already uploaded file_only books.

This path intentionally skips semantic embeddings/ChromaDB. It extracts PDF
text, creates DB chunks, indexes Elasticsearch, and marks the book as done so
literal citation verification can use the works immediately.

Run inside the backend container from /app:
  python -m scripts.fast_text_index_file_only_books --start-id 2105 --end-id 2135
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func

sys.path.insert(0, "/app")

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import PDFExtractor
from models.database import Book, BookFile, Chunk, SessionLocal, Translation
from search.text_search import TextSearchClient
from storage.pdf_storage import get_pdf_storage


@dataclass(frozen=True)
class Target:
    book_id: int
    title: str
    author: str
    status: str | None
    chunk_count: int
    file_count: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(payload: dict) -> None:
    print(json.dumps({"at": _now(), **payload}, ensure_ascii=False), flush=True)


def _targets(args: argparse.Namespace) -> list[Target]:
    with SessionLocal() as db:
        chunk_counts = (
            db.query(Chunk.book_id, func.count(Chunk.id).label("chunk_count"))
            .group_by(Chunk.book_id)
            .subquery()
        )
        file_counts = (
            db.query(BookFile.book_id, func.count(BookFile.id).label("file_count"))
            .group_by(BookFile.book_id)
            .subquery()
        )
        q = (
            db.query(
                Book.id,
                Book.title,
                Book.author,
                Book.ingest_status,
                func.coalesce(chunk_counts.c.chunk_count, 0),
                func.coalesce(file_counts.c.file_count, 0),
            )
            .outerjoin(chunk_counts, chunk_counts.c.book_id == Book.id)
            .outerjoin(file_counts, file_counts.c.book_id == Book.id)
            .order_by(Book.id.asc())
        )

        if args.book_id:
            q = q.filter(Book.id.in_(args.book_id))
        else:
            if args.start_id is not None:
                q = q.filter(Book.id >= args.start_id)
            if args.end_id is not None:
                q = q.filter(Book.id <= args.end_id)
            if not args.include_done:
                q = q.filter(Book.ingest_status != "done")

        if args.only_empty_chunks:
            q = q.filter(func.coalesce(chunk_counts.c.chunk_count, 0) == 0)

        rows = q.limit(args.limit).all() if args.limit else q.all()

    return [
        Target(
            book_id=int(row[0]),
            title=row[1],
            author=row[2],
            status=row[3],
            chunk_count=int(row[4] or 0),
            file_count=int(row[5] or 0),
        )
        for row in rows
    ]


def _chunks_for_book(book_id: int) -> list[tuple[Chunk, Book]]:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            return []
        chunks = (
            db.query(Chunk)
            .filter(Chunk.book_id == book_id)
            .order_by(Chunk.sequence_index.asc().nulls_last(), Chunk.id.asc())
            .all()
        )
        return [
            (
                Chunk(
                    id=chunk.id,
                    book_id=chunk.book_id,
                    book_file_id=chunk.book_file_id,
                    text=chunk.text,
                    sequence_index=chunk.sequence_index,
                    volume=chunk.volume,
                    column_start=chunk.column_start,
                    column_end=chunk.column_end,
                    pdf_page=chunk.pdf_page,
                    char_offset_start=chunk.char_offset_start,
                    char_offset_end=chunk.char_offset_end,
                    visual_anchor=chunk.visual_anchor,
                    chapter_or_section=chunk.chapter_or_section,
                ),
                Book(
                    id=book.id,
                    collection=book.collection,
                    title=book.title,
                    author=book.author,
                    language=book.language,
                    edition_label=book.edition_label,
                    source_label=book.source_label,
                    is_primary_source=book.is_primary_source,
                ),
            )
            for chunk in chunks
        ]


def _es_doc(book: Book, chunk: Chunk) -> dict:
    return {
        "book_id": book.id,
        "book_file_id": chunk.book_file_id,
        "text": chunk.text,
        "author": book.author,
        "work_title": book.title,
        "collection": book.collection,
        "volume": chunk.volume,
        "column_start": chunk.column_start,
        "language": book.language,
        "pdf_page": chunk.pdf_page,
        "edition_label": book.edition_label,
        "chapter_or_section": chunk.chapter_or_section,
        "char_offset_start": chunk.char_offset_start,
        "char_offset_end": chunk.char_offset_end,
    }


def _set_status(book_id: int, status: str, error: str | None = None) -> None:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is not None:
            book.ingest_status = status
            book.ingest_error = error
            db.commit()


def _clear_book(text_search: TextSearchClient, book_id: int) -> int:
    with SessionLocal() as db:
        ids = [row[0] for row in db.query(Chunk.id).filter(Chunk.book_id == book_id).all()]

    for chunk_id in ids:
        text_search.delete_chunk(int(chunk_id))

    if not ids:
        return 0

    with SessionLocal() as db:
        db.query(Translation).filter(Translation.chunk_id.in_(ids)).delete(synchronize_session=False)
        db.query(Chunk).filter(Chunk.book_id == book_id).delete(synchronize_session=False)
        book = db.get(Book, book_id)
        if book is not None:
            book.ingest_status = "file_only"
            book.ingest_error = None
        db.commit()
    return len(ids)


def _index_existing_chunks(text_search: TextSearchClient, book_id: int) -> int:
    rows = _chunks_for_book(book_id)
    if not rows:
        return 0

    items = [(chunk.id, _es_doc(book, chunk)) for chunk, book in rows if chunk.id is not None]
    text_search.index_chunks(items)
    _set_status(book_id, "done", None)
    return len(items)


def _insert_chunks(book_id: int, book_file: BookFile, raw_chunks: list[dict]) -> list[tuple[int, dict]]:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            return []

        max_seq = db.query(func.max(Chunk.sequence_index)).filter(Chunk.book_id == book_id).scalar()
        next_seq = (max_seq + 1) if max_seq is not None else 0

        inserted: list[Chunk] = []
        for index, chunk_data in enumerate(raw_chunks):
            chunk = Chunk(
                book_id=book_id,
                book_file_id=book_file.id,
                text=chunk_data["text"],
                sequence_index=next_seq + index,
                volume=chunk_data.get("volume_number"),
                column_start=chunk_data.get("column_start"),
                column_end=chunk_data.get("column_end"),
                pdf_page=chunk_data.get("pdf_page"),
                char_offset_start=chunk_data.get("char_offset_start"),
                char_offset_end=chunk_data.get("char_offset_end"),
                visual_anchor=f"col{chunk_data.get('column_start', '')}",
                chapter_or_section=chunk_data.get("chapter_or_section", ""),
            )
            db.add(chunk)
            inserted.append(chunk)

        db.flush()

        items = [(chunk.id, _es_doc(book, chunk)) for chunk in inserted if chunk.id is not None]
        db.commit()
        return items


def _files_for_book(book_id: int) -> list[BookFile]:
    with SessionLocal() as db:
        rows = (
            db.query(BookFile)
            .filter(BookFile.book_id == book_id)
            .order_by(BookFile.id.asc())
            .all()
        )
        return [
            BookFile(
                id=row.id,
                book_id=row.book_id,
                original_filename=row.original_filename,
                stored_path=row.stored_path,
                volume_number=row.volume_number,
                editor=row.editor,
                translator=row.translator,
            )
            for row in rows
        ]


def index_book(
    text_search: TextSearchClient,
    extractor: PDFExtractor,
    chunker: Chunker,
    target: Target,
    force_clear: bool,
    force_ocr: bool,
) -> bool:
    _log({
        "event": "book_start",
        "book_id": target.book_id,
        "title": target.title,
        "author": target.author,
        "status": target.status,
        "chunks": target.chunk_count,
        "files": target.file_count,
    })

    if force_clear:
        removed = _clear_book(text_search, target.book_id)
        _log({"event": "chunks_cleared", "book_id": target.book_id, "removed": removed})
    elif target.chunk_count > 0:
        count = _index_existing_chunks(text_search, target.book_id)
        _log({"event": "existing_chunks_indexed", "book_id": target.book_id, "chunks": count})
        return count > 0

    total_indexed = 0
    for book_file in _files_for_book(target.book_id):
        local_pdf_path = get_pdf_storage().resolve_for_processing(book_file.stored_path)
        if not local_pdf_path:
            _set_status(target.book_id, "error", f"PDF file not found: {book_file.stored_path}")
            _log({"event": "file_missing", "book_id": target.book_id, "file_id": book_file.id})
            return False

        _log({
            "event": "file_extract_start",
            "book_id": target.book_id,
            "file_id": book_file.id,
            "filename": book_file.original_filename,
        })
        pages = extractor._extract_ocr(local_pdf_path) if force_ocr else extractor.extract(local_pdf_path)
        raw_chunks = chunker.chunk(pages, {})
        if not raw_chunks:
            _set_status(target.book_id, "error", "Fast text indexing generated 0 chunks.")
            _log({"event": "file_no_chunks", "book_id": target.book_id, "file_id": book_file.id})
            return False

        items = _insert_chunks(target.book_id, book_file, raw_chunks)
        text_search.index_chunks(items)
        total_indexed += len(items)
        _log({
            "event": "file_indexed",
            "book_id": target.book_id,
            "file_id": book_file.id,
            "chunks": len(items),
        })

    if total_indexed > 0:
        _set_status(target.book_id, "done", None)
        _log({"event": "book_done", "book_id": target.book_id, "chunks": total_indexed})
        return True

    _set_status(target.book_id, "error", "No files/chunks indexed.")
    _log({"event": "book_error", "book_id": target.book_id, "error": "No files/chunks indexed."})
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id", type=int, action="append")
    parser.add_argument("--start-id", type=int, default=None)
    parser.add_argument("--end-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--include-done", action="store_true")
    parser.add_argument("--only-empty-chunks", action="store_true")
    parser.add_argument("--force-clear", action="store_true")
    parser.add_argument("--force-ocr", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    targets = _targets(args)
    _log({"event": "targets", "count": len(targets), "dry_run": args.dry_run})
    for target in targets:
        _log({
            "event": "target",
            "book_id": target.book_id,
            "title": target.title,
            "author": target.author,
            "status": target.status,
            "chunks": target.chunk_count,
            "files": target.file_count,
        })

    if args.dry_run:
        return 0

    text_search = TextSearchClient()
    extractor = PDFExtractor()
    chunker = Chunker()

    ok = 0
    failed = 0
    for target in targets:
        try:
            if index_book(text_search, extractor, chunker, target, args.force_clear, args.force_ocr):
                ok += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            _set_status(target.book_id, "error", f"Fast text indexing failed: {exc}")
            _log({"event": "book_exception", "book_id": target.book_id, "error": str(exc)})

    _log({"event": "summary", "ok": ok, "failed": failed})
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
