"""Rebuild born-digital books as non-public transcription candidates.

This command is deliberately conservative:

* scanned PDFs and hidden OCR layers are rejected;
* chunks never cross a physical PDF page;
* every generated chunk must occur verbatim in that same page's text layer;
* the existing rows stay live until PostgreSQL and Elasticsearch have accepted
  the replacement set;
* a gzip backup is written before every swap.

Matching the text layer is not visual proof. A PDF may render a glyph that is
missing or mapped incorrectly in its hidden text (for example, ``Homem`` may
extract as ``Home``). Therefore this command never promotes generated chunks
to a public source fidelity. A separate page-by-page visual review must do so.

Run inside the backend container from /app::

    python -m scripts.reindex_digital_source_text --language la --language latim
    python -m scripts.reindex_digital_source_text --book-id 1863 --dry-run
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, "/app")

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import PDFExtractor
from models.database import Book, BookFile, Chunk, SessionLocal, Translation, init_db
from scripts.audit_source_fidelity import _exact_page_matches
from scripts.ocr_reindex_books import BookTarget, _chunk_payload, _es_doc
from search.text_search import TextSearchClient
from storage.pdf_storage import get_pdf_storage


DEFAULT_BACKUP_ROOT = Path("/app/pdfs/.source_text_reindex_backups")
DEFAULT_REPORT_ROOT = Path("/app/pdfs/.source_text_reindex_reports")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(payload: dict) -> None:
    print(json.dumps({"at": _now(), **payload}, ensure_ascii=False), flush=True)


def _targets(book_ids: list[int], languages: list[str]) -> list[BookTarget]:
    with SessionLocal() as db:
        query = db.query(Book, BookFile).join(BookFile, BookFile.book_id == Book.id)
        if book_ids:
            query = query.filter(Book.id.in_(book_ids))
        else:
            normalized = sorted({language.strip().casefold() for language in languages if language.strip()})
            query = query.filter(Book.language.in_(normalized + [value.capitalize() for value in normalized]))
        rows = query.order_by(Book.id, BookFile.id).all()

        file_counts = Counter(book.id for book, _file in rows)
        duplicates = sorted(book_id for book_id, count in file_counts.items() if count != 1)
        if duplicates:
            raise RuntimeError(
                "digital source reindex currently requires exactly one PDF per book; "
                f"multiple files found for book ids {duplicates}"
            )

        return [
            BookTarget(
                book_id=book.id,
                title=book.title,
                author=book.author,
                collection=book.collection or "",
                language=book.language,
                file_id=book_file.id,
                filename=book_file.original_filename,
                stored_path=book_file.stored_path,
            )
            for book, book_file in rows
        ]


def _validate_source_chunks(raw_chunks: list[dict], pages: list[dict]) -> dict:
    candidates = [
        SimpleNamespace(
            id=index,
            pdf_page=chunk.get("pdf_page"),
            text=chunk.get("text") or "",
        )
        for index, chunk in enumerate(raw_chunks, start=1)
    ]
    matched, reasons = _exact_page_matches(candidates, pages)
    if len(matched) != len(candidates):
        raise RuntimeError(
            "generated chunks are not exact same-page PDF text: "
            + json.dumps(dict(reasons), ensure_ascii=False, sort_keys=True)
        )

    replacement_chars = sum((page.get("text") or "").count("\ufffd") for page in pages)
    nonempty_pages = sum(bool((page.get("text") or "").strip()) for page in pages)
    if replacement_chars:
        raise RuntimeError(f"PDF text layer contains {replacement_chars} replacement characters")
    if not raw_chunks or not nonempty_pages:
        raise RuntimeError("PDF text layer produced no usable source text")

    return {
        "pages": len(pages),
        "nonempty_pages": nonempty_pages,
        "chunks": len(raw_chunks),
        "same_page_exact_chunks": len(matched),
        "replacement_chars": replacement_chars,
    }


def _backup_current_rows(target: BookTarget, backup_root: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_root / f"book_{target.book_id}_before_source_text_{stamp}.json.gz"
    with SessionLocal() as db:
        chunks = db.query(Chunk).filter(Chunk.book_id == target.book_id).order_by(Chunk.id).all()
        chunk_ids = [chunk.id for chunk in chunks]
        translations = (
            db.query(Translation).filter(Translation.chunk_id.in_(chunk_ids)).order_by(Translation.id).all()
            if chunk_ids else []
        )
        payload = {
            "created_at": _now(),
            "target": asdict(target),
            "chunks": [_chunk_payload(chunk) for chunk in chunks],
            "translations": [
                {
                    "id": row.id,
                    "chunk_id": row.chunk_id,
                    "language": row.language,
                    "text": row.text,
                    "translator": row.translator,
                    "edition_label": row.edition_label,
                }
                for row in translations
            ],
        }
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    return path


def _swap_chunks(
    target: BookTarget,
    raw_chunks: list[dict],
    text_search: TextSearchClient,
    backup_root: Path,
) -> tuple[int, int, Path]:
    backup_path = _backup_current_rows(target, backup_root)
    new_ids: list[int] = []
    old_ids: list[int] = []

    with SessionLocal() as db:
        book = db.get(Book, target.book_id)
        if book is None:
            raise RuntimeError(f"book {target.book_id} disappeared before swap")
        old_ids = [row[0] for row in db.query(Chunk.id).filter(Chunk.book_id == target.book_id).all()]
        inserted: list[Chunk] = []
        for sequence, data in enumerate(raw_chunks):
            chunk = Chunk(
                book_id=target.book_id,
                book_file_id=target.file_id,
                text=data["text"],
                sequence_index=sequence,
                volume=data.get("volume_number"),
                column_start=data.get("column_start"),
                column_end=data.get("column_end"),
                pdf_page=data.get("pdf_page"),
                char_offset_start=data.get("char_offset_start"),
                char_offset_end=data.get("char_offset_end"),
                visual_anchor=f"col{data.get('column_start', '')}",
                chapter_or_section=data.get("chapter_or_section", ""),
                extraction_method="digital_text_candidate",
                source_fidelity="unverified",
                fidelity_score=None,
                fidelity_reasons="native text layer candidate; complete visual PDF fidelity not yet proven",
            )
            db.add(chunk)
            inserted.append(chunk)

        try:
            db.flush()
            new_ids = [int(chunk.id) for chunk in inserted]
            text_search.index_chunks([(chunk.id, _es_doc(book, chunk)) for chunk in inserted])
            if old_ids:
                db.query(Translation).filter(Translation.chunk_id.in_(old_ids)).delete(synchronize_session=False)
                db.query(Chunk).filter(Chunk.id.in_(old_ids)).delete(synchronize_session=False)
            book.ingest_status = "done"
            book.ingest_error = None
            db.commit()
        except Exception:
            db.rollback()
            for chunk_id in new_ids:
                text_search.delete_chunk(chunk_id)
            raise

    # Stale semantic hits are harmless because public paths re-check the DB
    # fidelity row. Avoid loading Chroma here: some production builds have an
    # hnswlib crash during cleanup. Lexical documents are safe to remove now.
    for chunk_id in old_ids:
        text_search.delete_chunk(chunk_id)
    return len(old_ids), len(new_ids), backup_path


def reindex_target(
    target: BookTarget,
    extractor: PDFExtractor,
    chunker: Chunker,
    text_search: TextSearchClient,
    backup_root: Path,
    dry_run: bool,
) -> dict:
    storage = get_pdf_storage()
    local_path = storage.resolve_for_processing(target.stored_path)
    if not local_path:
        raise RuntimeError("PDF file is unavailable")
    if not extractor._is_digital(local_path):
        return {"status": "scanned_requires_visual_transcription", "book_id": target.book_id}

    pages = extractor._extract_digital(local_path)
    for page in pages:
        page["extraction_method"] = "digital_text_candidate"
        page["source_fidelity"] = "unverified"
        page["fidelity_score"] = None
        page["fidelity_reasons"] = "native text layer candidate; visual review required"
    raw_chunks = chunker.chunk(pages, {})
    quality = _validate_source_chunks(raw_chunks, pages)
    if dry_run:
        return {"status": "dry_run_text_layer_candidate", "book_id": target.book_id, **quality}

    removed, inserted, backup = _swap_chunks(target, raw_chunks, text_search, backup_root)
    return {
        "status": "reindexed_text_layer_candidate",
        "book_id": target.book_id,
        **quality,
        "removed_chunks": removed,
        "inserted_chunks": inserted,
        "backup": str(backup),
    }


def run(
    book_ids: list[int],
    languages: list[str],
    backup_root: Path,
    report_root: Path,
    dry_run: bool,
) -> dict:
    init_db()
    targets = _targets(book_ids, languages)
    extractor = PDFExtractor()
    chunker = Chunker()
    text_search = TextSearchClient()
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    checkpoint = report_root / f"digital-source-text-{stamp}.jsonl"
    output = report_root / f"digital-source-text-{stamp}.json"
    report = {"created_at": _now(), "dry_run": dry_run, "books": [], "totals": Counter()}

    for target in targets:
        _log({"event": "book_start", "book_id": target.book_id, "title": target.title})
        try:
            entry = reindex_target(target, extractor, chunker, text_search, backup_root, dry_run)
        except Exception as exc:
            entry = {
                "status": "error_fail_closed",
                "book_id": target.book_id,
                "error": f"{type(exc).__name__}: {exc}",
            }
        report["books"].append(entry)
        report["totals"][entry["status"]] += 1
        with checkpoint.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _log(entry)

    report["totals"] = dict(report["totals"])
    report["report_path"] = str(output)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log({"event": "summary", "targets": len(targets), "totals": report["totals"], "report": str(output)})
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", type=int, action="append", default=[])
    parser.add_argument("--language", action="append", default=[])
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    languages = args.language or ["la", "latim"]
    report = run(args.book_id, languages, args.backup_root, args.report_root, args.dry_run)
    return 1 if report["totals"].get("error_fail_closed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
