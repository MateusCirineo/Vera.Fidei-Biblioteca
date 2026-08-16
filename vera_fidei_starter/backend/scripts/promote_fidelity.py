"""Promote patristic chunks from 'unverified' to 'verified' for known reliable editions.

Targets books where the PDF source is a well-known scholarly edition (Paulus
Editora / Patrística series) and manual inspection confirms the text extraction
is clean. Updates both the PostgreSQL fidelity field and the ES index.

Usage (from inside the backend container):

    # Dry run — show what would change
    python /app/scripts/promote_fidelity.py --dry-run

    # Promote Inácio de Antioquia (book_id=2090)
    python /app/scripts/promote_fidelity.py --book-ids 2090

    # Promote Justino Mártir (book_id=10) — content pages only (skips TOC/index)
    python /app/scripts/promote_fidelity.py --book-ids 10 --skip-non-quotable

    # Promote both
    python /app/scripts/promote_fidelity.py --book-ids 2090 10 --skip-non-quotable
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from elasticsearch.helpers import bulk
from models.database import Book, Chunk, SessionLocal
from search.content_quality import assess_content
from search.text_search import ES_INDEX, TextSearchClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(event: str, **data) -> None:
    print(json.dumps({"at": _now(), "event": event, **data}, ensure_ascii=False), flush=True)


def _source_page_key(chunk: Chunk) -> str:
    if chunk.pdf_page is None:
        return f"chunk:{chunk.id}"
    if chunk.book_file_id is not None:
        return f"file:{chunk.book_file_id}:page:{chunk.pdf_page}"
    return f"book:{chunk.book_id}:page:{chunk.pdf_page}"


def promote_book(
    book_id: int,
    client: TextSearchClient,
    *,
    dry_run: bool = False,
    skip_non_quotable: bool = False,
    from_fidelity: str = "unverified",
    to_fidelity: str = "verified",
) -> dict:
    start = time.monotonic()
    stats = {
        "book_id": book_id,
        "chunks_inspected": 0,
        "chunks_promoted": 0,
        "chunks_skipped_non_quotable": 0,
        "chunks_skipped_wrong_fidelity": 0,
        "es_docs_updated": 0,
        "errors": [],
    }

    with SessionLocal() as db:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            _log("book_not_found", book_id=book_id)
            stats["errors"].append("book not found")
            return stats

        _log("promote_start", book_id=book_id, title=book.title, author=book.author,
             from_fidelity=from_fidelity, to_fidelity=to_fidelity,
             skip_non_quotable=skip_non_quotable, dry_run=dry_run)

        chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.id).all()
        stats["chunks_inspected"] = len(chunks)

        es_docs = []
        chunks_to_update = []

        for chunk in chunks:
            if chunk.source_fidelity != from_fidelity:
                stats["chunks_skipped_wrong_fidelity"] += 1
                continue

            text = chunk.text or ""
            if not text.strip():
                stats["chunks_skipped_non_quotable"] += 1
                continue

            if skip_non_quotable:
                assessment = assess_content(
                    text,
                    author=book.author,
                    work_title=book.title,
                    section=None,
                    pdf_page=chunk.pdf_page,
                )
                if not assessment.is_quotable:
                    stats["chunks_skipped_non_quotable"] += 1
                    _log("skip_non_quotable", chunk_id=chunk.id, pdf_page=chunk.pdf_page,
                         role=assessment.role)
                    continue

            chunks_to_update.append(chunk)
            es_docs.append({
                "_op_type": "update",
                "_index": ES_INDEX,
                "_id": str(chunk.id),
                "doc": {
                    "source_fidelity": to_fidelity,
                    "is_quotable": to_fidelity in ("source_text", "verified"),
                    "literal_search_text": text,
                },
            })

        stats["chunks_promoted"] = len(chunks_to_update)

        if dry_run:
            _log("dry_run_result", **stats, elapsed_s=round(time.monotonic() - start, 2))
            for c in chunks_to_update[:5]:
                snippet = (c.text or "")[:80].replace("\n", " ")
                print(f"  [DRY] chunk_id={c.id} page={c.pdf_page}: {snippet!r}")
            if len(chunks_to_update) > 5:
                print(f"  ... and {len(chunks_to_update) - 5} more")
            return stats

        # Update DB
        for chunk in chunks_to_update:
            chunk.source_fidelity = to_fidelity
        db.commit()
        _log("db_updated", chunks=len(chunks_to_update))

        # Update ES
        if es_docs:
            success, failed = bulk(
                client.es,
                es_docs,
                chunk_size=200,
                raise_on_error=False,
                stats_only=False,
            )
            stats["es_docs_updated"] = success
            if failed:
                stats["errors"] += [str(f)[:200] for f in failed[:3]]
                _log("es_partial_failure", count=len(failed))

    elapsed = time.monotonic() - start
    _log("promote_done", **stats, elapsed_s=round(elapsed, 2))
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote patristic chunk fidelity to 'verified'")
    parser.add_argument("--book-ids", type=int, nargs="+", required=True,
                        help="Book IDs to promote")
    parser.add_argument("--from-fidelity", default="unverified",
                        help="Source fidelity to promote from (default: unverified)")
    parser.add_argument("--to-fidelity", default="verified",
                        help="Target fidelity (default: verified)")
    parser.add_argument("--skip-non-quotable", action="store_true",
                        help="Skip TOC/index/publisher pages (content_quality check)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be promoted without writing")
    args = parser.parse_args()

    client = TextSearchClient()
    all_stats = []

    for book_id in args.book_ids:
        stats = promote_book(
            book_id,
            client,
            dry_run=args.dry_run,
            skip_non_quotable=args.skip_non_quotable,
            from_fidelity=args.from_fidelity,
            to_fidelity=args.to_fidelity,
        )
        all_stats.append(stats)

    print("\n" + "=" * 60)
    print("PROMOTION SUMMARY")
    print("=" * 60)
    for s in all_stats:
        status = "DRY RUN" if args.dry_run else ("OK" if not s["errors"] else "PARTIAL")
        print(f"  book_id={s['book_id']}: {s['chunks_promoted']} promoted  "
              f"{s['chunks_skipped_non_quotable']} skipped  "
              f"{s['es_docs_updated']} ES updated  [{status}]")
    if args.dry_run:
        print("\nNenhuma alteração foi feita (--dry-run ativo).")


if __name__ == "__main__":
    main()
