"""
Index existing file_only BookFile records without creating duplicate uploads.

This is intended for books that were imported into the library with their PDF
already stored, but whose text was not yet extracted into chunks/search indexes.

Run inside the backend container from /app:
  python -m scripts.index_file_only_books --start-id 2105 --end-id 2135
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func

sys.path.insert(0, "/app")

from models.database import Book, BookFile, Chunk, SessionLocal, Translation
from services.ingestion_service import IngestionService


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


def _count_chunks(book_id: int) -> int:
    with SessionLocal() as db:
        return int(db.query(func.count(Chunk.id)).filter(Chunk.book_id == book_id).scalar() or 0)


def _book_status(book_id: int) -> tuple[str | None, str | None]:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            return None, "book not found"
        return book.ingest_status, book.ingest_error


def _get_files(book_id: int) -> list[BookFile]:
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
            if args.start_id:
                q = q.filter(Book.id >= args.start_id)
            if args.end_id:
                q = q.filter(Book.id <= args.end_id)
            if not args.include_done:
                q = q.filter(Book.ingest_status == "file_only")

        if not args.include_with_chunks:
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


def _clear_existing_chunks(service: IngestionService, book_id: int) -> int:
    with SessionLocal() as db:
        chunk_ids = [row[0] for row in db.query(Chunk.id).filter(Chunk.book_id == book_id).all()]

    for chunk_id in chunk_ids:
        service.text_search.delete_chunk(int(chunk_id))
        service.semantic_search.delete_chunk(int(chunk_id))

    if not chunk_ids:
        return 0

    with SessionLocal() as db:
        db.query(Translation).filter(Translation.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
        db.query(Chunk).filter(Chunk.book_id == book_id).delete(synchronize_session=False)
        book = db.get(Book, book_id)
        if book is not None:
            book.ingest_status = "file_only"
            book.ingest_error = None
        db.commit()

    return len(chunk_ids)


def _log(payload: dict) -> None:
    print(json.dumps({"at": _now(), **payload}, ensure_ascii=False), flush=True)


def index_book(service: IngestionService, target: Target, force_clear: bool) -> bool:
    _log(
        {
            "event": "book_start",
            "book_id": target.book_id,
            "author": target.author,
            "title": target.title,
            "status": target.status,
            "existing_chunks": target.chunk_count,
            "file_count": target.file_count,
        }
    )

    if force_clear:
        removed = _clear_existing_chunks(service, target.book_id)
        if removed:
            _log({"event": "chunks_cleared", "book_id": target.book_id, "removed": removed})

    files = _get_files(target.book_id)
    if not files:
        _log({"event": "book_skip", "book_id": target.book_id, "reason": "no_book_files"})
        return False

    for book_file in files:
        _log(
            {
                "event": "file_start",
                "book_id": target.book_id,
                "file_id": book_file.id,
                "original_filename": book_file.original_filename,
                "stored_path": book_file.stored_path,
            }
        )
        service._ingest_background(target.book_id, int(book_file.id), book_file.stored_path)
        status, error = _book_status(target.book_id)
        chunks = _count_chunks(target.book_id)
        _log(
            {
                "event": "file_done",
                "book_id": target.book_id,
                "file_id": book_file.id,
                "status": status,
                "chunks": chunks,
                "error": error,
            }
        )
        if status == "error":
            return False

    status, error = _book_status(target.book_id)
    chunks = _count_chunks(target.book_id)
    ok = bool(status == "done" and chunks > 0)
    _log(
        {
            "event": "book_done" if ok else "book_not_ready",
            "book_id": target.book_id,
            "status": status,
            "chunks": chunks,
            "error": error,
        }
    )
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id", type=int, action="append", help="Specific book id. Repeatable.")
    parser.add_argument("--start-id", type=int, default=None)
    parser.add_argument("--end-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--include-done", action="store_true", help="Do not filter by file_only status.")
    parser.add_argument("--include-with-chunks", action="store_true", help="Do not skip books that already have chunks.")
    parser.add_argument("--force-clear", action="store_true", help="Delete existing chunks/index docs before reindexing.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    targets = _targets(args)
    _log({"event": "targets", "count": len(targets), "dry_run": args.dry_run})
    for target in targets:
        _log(
            {
                "event": "target",
                "book_id": target.book_id,
                "author": target.author,
                "title": target.title,
                "status": target.status,
                "chunks": target.chunk_count,
                "files": target.file_count,
            }
        )

    if args.dry_run:
        return 0

    service = IngestionService()
    ok = 0
    failed = 0
    for target in targets:
        if index_book(service, target, force_clear=args.force_clear):
            ok += 1
        else:
            failed += 1

    _log({"event": "summary", "ok": ok, "failed": failed})
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
