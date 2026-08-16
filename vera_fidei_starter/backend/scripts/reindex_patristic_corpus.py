"""Full reindexation of the patristic corpus in Elasticsearch.

Idempotent, resumable, batch-capable. Processes all books in patristic
collections, or a subset by collection/book-id. Produces a per-book report
and writes a JSON summary to the report root.

This script does NOT re-extract PDFs. It rebuilds ES documents from the
existing PostgreSQL chunks. To re-run OCR extraction use ocr_reindex_books.py.

Run inside the backend container from /app:

    # Reindex all patristic collections
    python -m scripts.reindex_patristic_corpus

    # Reindex only PG and PL
    python -m scripts.reindex_patristic_corpus --collections PG PL

    # Dry run — show what would be reindexed
    python -m scripts.reindex_patristic_corpus --dry-run

    # Single book
    python -m scripts.reindex_patristic_corpus --book-id 42

    # Resume after partial failure (skips books already marked done in report)
    python -m scripts.reindex_patristic_corpus --resume --report-file /tmp/reindex_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

sys.path.insert(0, "/app")

from elasticsearch.helpers import bulk
from models.database import Book, BookFile, Chunk, SessionLocal
from search.text_search import ES_INDEX, TextSearchClient
from core.config import settings

DEFAULT_REPORT_ROOT = Path("/app/pdfs/.patristic_reindex_reports")
PATRISTIC_COLLECTIONS = ("PL", "PG", "PO", "PT", "Patrística EN", "Patrística LA", "Patrística PT", "DIDAQUE")
BATCH_SIZE = 500


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(event: str, data: dict | None = None) -> None:
    payload = {"at": _now(), "event": event}
    if data:
        payload.update(data)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _get_patristic_books(
    book_ids: list[int] | None,
    collections: list[str],
    session,
) -> list[Book]:
    q = session.query(Book)
    if book_ids:
        q = q.filter(Book.id.in_(book_ids))
    else:
        q = q.filter(Book.collection.in_(collections))
    return q.order_by(Book.id).all()


def _get_chunks_for_book(book_id: int, session) -> list[Chunk]:
    return (
        session.query(Chunk)
        .filter(Chunk.book_id == book_id)
        .order_by(Chunk.id)
        .all()
    )


def _chunk_to_es_doc(chunk: Chunk, book: Book) -> dict:
    """Convert a Chunk row to an ES document dict."""
    text = chunk.text or ""
    literal_text = None
    fidelity = chunk.source_fidelity or "unverified"
    if fidelity in ("source_text", "verified"):
        literal_text = text

    return {
        "_index": ES_INDEX,
        "_id": str(chunk.id),
        "_source": {
            "chunk_id": chunk.id,
            "book_id": chunk.book_id,
            "book_file_id": chunk.book_file_id,
            "text": text,
            "literal_search_text": literal_text,
            "author": book.author or "",
            "work_title": book.title or "",
            "collection": book.collection or "",
            "language": book.language or "",
            "pdf_page": chunk.pdf_page,
            "source_fidelity": fidelity,
            "is_quotable": fidelity in ("source_text", "verified"),
            "source_page_key": _source_page_key(chunk),
            "extraction_method": chunk.extraction_method or "pdfminer",
        }
    }


def _source_page_key(chunk: Chunk) -> str:
    if chunk.pdf_page is None:
        return f"chunk:{chunk.id}"
    if chunk.book_file_id is not None:
        return f"file:{chunk.book_file_id}:page:{chunk.pdf_page}"
    return f"book:{chunk.book_id}:page:{chunk.pdf_page}"


def _reindex_book(book: Book, client: TextSearchClient, dry_run: bool) -> dict:
    """Reindex one book's chunks into ES. Returns a per-book report."""
    start = time.monotonic()
    with SessionLocal() as db:
        chunks = _get_chunks_for_book(book.id, db)

    report: dict = {
        "book_id": book.id,
        "title": book.title,
        "author": book.author,
        "collection": book.collection,
        "language": book.language,
        "status": "pending",
        "chunks_total": len(chunks),
        "chunks_indexed": 0,
        "chunks_source_text": 0,
        "chunks_unverified": 0,
        "chunks_ocr": 0,
        "chunks_empty": 0,
        "errors": [],
    }

    if not chunks:
        report["status"] = "no_chunks"
        _log("book_skip", {"book_id": book.id, "reason": "no_chunks"})
        return report

    docs = []
    for chunk in chunks:
        fidelity = chunk.source_fidelity or "unverified"
        text = (chunk.text or "").strip()
        if not text:
            report["chunks_empty"] += 1
            continue
        if fidelity in ("source_text", "verified"):
            report["chunks_source_text"] += 1
        elif fidelity == "unverified_ocr":
            report["chunks_ocr"] += 1
        else:
            report["chunks_unverified"] += 1
        docs.append(_chunk_to_es_doc(chunk, book))

    if not docs:
        report["status"] = "all_chunks_empty"
        return report

    if dry_run:
        report["status"] = "dry_run"
        report["chunks_indexed"] = len(docs)
        _log("book_dry_run", {"book_id": book.id, "docs": len(docs)})
        return report

    try:
        success, failed = bulk(
            client.es,
            docs,
            chunk_size=BATCH_SIZE,
            raise_on_error=False,
            stats_only=False,
        )
        report["chunks_indexed"] = success
        if failed:
            report["errors"] = [str(f)[:200] for f in failed[:5]]
            report["status"] = "partial"
        else:
            report["status"] = "complete"
    except Exception as exc:
        report["status"] = "failed"
        report["errors"] = [str(exc)[:500]]

    elapsed = time.monotonic() - start
    _log("book_done", {
        "book_id": book.id,
        "status": report["status"],
        "chunks_indexed": report["chunks_indexed"],
        "elapsed_s": round(elapsed, 2),
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Reindex patristic corpus in Elasticsearch")
    parser.add_argument("--collections", nargs="*", default=list(PATRISTIC_COLLECTIONS),
                        help="Collections to reindex (default: all patristic)")
    parser.add_argument("--book-id", type=int, nargs="*", dest="book_ids",
                        help="Reindex only these book IDs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be reindexed without writing to ES")
    parser.add_argument("--resume", action="store_true",
                        help="Skip books already marked 'complete' in --report-file")
    parser.add_argument("--report-file", type=Path,
                        default=None,
                        help="Path to existing report JSON for --resume mode")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help=f"ES bulk batch size (default: {BATCH_SIZE})")
    args = parser.parse_args()

    report_root = DEFAULT_REPORT_ROOT
    report_root.mkdir(parents=True, exist_ok=True)

    client = TextSearchClient()

    already_done: set[int] = set()
    if args.resume and args.report_file and args.report_file.exists():
        with open(args.report_file) as f:
            prev = json.load(f)
        for item in prev.get("books", []):
            if item.get("status") == "complete":
                already_done.add(item["book_id"])
        _log("resume_mode", {"skipping": len(already_done), "report": str(args.report_file)})

    with SessionLocal() as db:
        books = _get_patristic_books(args.book_ids, args.collections, db)

    _log("reindex_start", {
        "total_books": len(books),
        "collections": args.collections,
        "dry_run": args.dry_run,
    })

    book_reports = []
    for book in books:
        if book.id in already_done:
            _log("book_skip", {"book_id": book.id, "reason": "already_complete"})
            book_reports.append({"book_id": book.id, "status": "already_complete"})
            continue
        report = _reindex_book(book, client, dry_run=args.dry_run)
        book_reports.append(report)

    summary = {
        "started_at": _now(),
        "query_params": {
            "collections": args.collections,
            "book_ids": args.book_ids,
            "dry_run": args.dry_run,
        },
        "totals": {
            "books_processed": len([r for r in book_reports if r.get("status") not in ("already_complete",)]),
            "books_complete": len([r for r in book_reports if r.get("status") == "complete"]),
            "books_partial": len([r for r in book_reports if r.get("status") == "partial"]),
            "books_failed": len([r for r in book_reports if r.get("status") == "failed"]),
            "books_no_chunks": len([r for r in book_reports if r.get("status") == "no_chunks"]),
            "books_dry_run": len([r for r in book_reports if r.get("status") == "dry_run"]),
            "chunks_indexed": sum(r.get("chunks_indexed", 0) for r in book_reports),
            "chunks_source_text": sum(r.get("chunks_source_text", 0) for r in book_reports),
            "chunks_unverified": sum(r.get("chunks_unverified", 0) for r in book_reports),
            "chunks_ocr": sum(r.get("chunks_ocr", 0) for r in book_reports),
            "chunks_empty": sum(r.get("chunks_empty", 0) for r in book_reports),
        },
        "books": book_reports,
    }

    # Save report
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = report_root / f"reindex_{ts}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    _log("reindex_complete", {
        **summary["totals"],
        "report_file": str(report_path),
    })

    print("\n" + "=" * 60)
    print("REINDEX SUMMARY")
    print("=" * 60)
    for k, v in summary["totals"].items():
        print(f"  {k:<30} {v:>8}")
    print(f"\nReport saved: {report_path}")

    failed = [r for r in book_reports if r.get("status") in ("failed", "partial")]
    if failed:
        print(f"\n⚠️  {len(failed)} books with errors:")
        for r in failed[:10]:
            print(f"  book_id={r['book_id']} status={r['status']} errors={r.get('errors', [])[:1]}")

    if not args.dry_run and summary["totals"]["books_failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
