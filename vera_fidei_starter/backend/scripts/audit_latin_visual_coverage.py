"""Audit candidate OCR, second readings and visual reviews for Latin works."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

sys.path.insert(0, "/app")

from models.database import Book, BookFile, Chunk, SessionLocal, VerifiedPageReview, VerifiedPassage
from storage.pdf_storage import get_pdf_storage


DEFAULT_CANDIDATE_ROOT = Path("/app/pdfs/.ocr_reindex_cache")
DEFAULT_VERIFICATION_ROOT = Path("/app/pdfs/.page_verification")


def is_latin_work(language: str | None) -> bool:
    tokens = set(re.findall(r"[a-z]+", (language or "").casefold()))
    return bool(tokens & {"la", "latim", "latin"})


def _existing_pdf(storage, book_file: BookFile) -> Path | None:
    candidates: list[Path] = []
    local = storage.resolve_local_path(book_file.stored_path)
    if local:
        candidates.append(Path(local))
    if book_file.stored_path.startswith("gdrive://"):
        mirror = storage._local_mirror_for_gdrive(book_file.stored_path)
        if mirror:
            candidates.append(Path(mirror))
        _bucket, key = storage._parse_remote_path(book_file.stored_path)
        if key:
            candidates.append(storage._cache_path_for_key(key))
    candidates.extend((
        Path("/app/pdfs") / book_file.original_filename,
        Path("/app/pdfs") / Path(book_file.stored_path).name,
    ))
    return next((path for path in candidates if path.is_file()), None)


def _latest_count(root: Path, book_id: int, pattern: str) -> int:
    base = root / f"book_{book_id}"
    directories = [path for path in base.glob("*") if path.is_dir()]
    if not directories:
        return 0
    latest = max(
        directories,
        key=lambda path: max((item.stat().st_mtime_ns for item in path.rglob("*") if item.is_file()), default=0),
    )
    return sum(1 for _ in latest.glob(pattern))


def build_audit(*, resolve_missing: bool = False) -> dict:
    storage = get_pdf_storage()
    with SessionLocal() as db:
        books = db.query(Book).order_by(Book.id).all()
        latin_books = [book for book in books if is_latin_work(book.language)]
        rows: list[dict] = []
        for book in latin_books:
            files = db.query(BookFile).filter(BookFile.book_id == book.id).order_by(BookFile.id).all()
            if not files:
                chunks = db.query(Chunk).filter(Chunk.book_id == book.id).all()
                passages = db.query(VerifiedPassage).filter(VerifiedPassage.book_id == book.id).count()
                alias_complete = bool(chunks) and passages > 0 and all(
                    chunk.source_fidelity == "verified" for chunk in chunks
                )
                rows.append({
                    "book_id": book.id,
                    "title": book.title,
                    "language": book.language,
                    "source_kind": "logical_alias",
                    "pdf_pages": 0,
                    "candidate_pages": 0,
                    "second_reading_pages": 0,
                    "visually_reviewed_pages": 0,
                    "alias_complete": alias_complete,
                    "missing_pdf": True,
                })
                continue

            for book_file in files:
                pdf_path = _existing_pdf(storage, book_file)
                if pdf_path is None and resolve_missing:
                    resolved = storage.resolve_for_processing(book_file.stored_path)
                    pdf_path = Path(resolved) if resolved else None
                page_total = None
                error = None
                if pdf_path is not None:
                    try:
                        with pdfplumber.open(str(pdf_path)) as pdf:
                            page_total = len(pdf.pages)
                    except Exception as exc:
                        error = str(exc)
                reviewed_pages = {
                    page
                    for (page,) in db.query(VerifiedPageReview.pdf_page)
                    .filter(
                        VerifiedPageReview.book_id == book.id,
                        VerifiedPageReview.book_file_id == book_file.id,
                    )
                    .distinct()
                    .all()
                }
                rows.append({
                    "book_id": book.id,
                    "title": book.title,
                    "language": book.language,
                    "source_kind": "pdf",
                    "book_file_id": book_file.id,
                    "pdf": book_file.original_filename,
                    "pdf_pages": page_total,
                    "candidate_pages": _latest_count(
                        DEFAULT_CANDIDATE_ROOT, book.id, "page_*.txt"
                    ),
                    "second_reading_pages": _latest_count(
                        DEFAULT_VERIFICATION_ROOT, book.id, "pages/page_*.json"
                    ),
                    "visually_reviewed_pages": len(reviewed_pages),
                    "alias_complete": False,
                    "missing_pdf": pdf_path is None,
                    "error": error,
                })

    known_rows = [row for row in rows if isinstance(row.get("pdf_pages"), int)]
    total_pages = sum(row["pdf_pages"] for row in known_rows)
    candidate_pages = sum(min(row["candidate_pages"], row["pdf_pages"]) for row in known_rows)
    second_pages = sum(min(row["second_reading_pages"], row["pdf_pages"]) for row in known_rows)
    reviewed_pages = sum(min(row["visually_reviewed_pages"], row["pdf_pages"]) for row in known_rows)
    logical_aliases = [row for row in rows if row["source_kind"] == "logical_alias"]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "all_catalog_works_whose_language_metadata_contains_latin",
        "books": len({row["book_id"] for row in rows}),
        "pdf_files": sum(row["source_kind"] == "pdf" for row in rows),
        "logical_aliases": len(logical_aliases),
        "complete_logical_aliases": sum(bool(row["alias_complete"]) for row in logical_aliases),
        "known_pdf_pages": total_pages,
        "unknown_pdf_files": sum(row["source_kind"] == "pdf" and row["pdf_pages"] is None for row in rows),
        "candidate_pages": candidate_pages,
        "candidate_percent": round(100 * candidate_pages / max(1, total_pages), 3),
        "second_reading_pages": second_pages,
        "second_reading_percent": round(100 * second_pages / max(1, total_pages), 3),
        "visually_reviewed_pages": reviewed_pages,
        "visual_review_percent": round(100 * reviewed_pages / max(1, total_pages), 3),
        "public_promotion_complete": (
            bool(known_rows)
            and not any(row["pdf_pages"] is None for row in rows if row["source_kind"] == "pdf")
            and reviewed_pages == total_pages
            and all(row["alias_complete"] for row in logical_aliases)
        ),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolve-missing", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_audit(resolve_missing=args.resolve_missing)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(args.output)
    print(rendered)
    return 0 if not any(row.get("error") for row in report["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
