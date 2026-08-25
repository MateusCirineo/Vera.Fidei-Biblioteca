"""Audit every indexed chunk against the exact PDF text layer.

Scanned/OCR text is never promoted by this script. A legacy chunk becomes
``source_text`` only when its complete wording (apart from layout whitespace
and soft hyphens) occurs on the exact recorded page of the same PDF file.

Run inside the backend container from /app:
  python -m scripts.audit_source_fidelity
  python -m scripts.audit_source_fidelity --apply
  python -m scripts.audit_source_fidelity --apply --book-id 32
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ingestion.pdf_extractor import PDFExtractor
from models.database import Book, BookFile, Chunk, SessionLocal, init_db
from services.source_fidelity_service import normalize_literal
from storage.pdf_storage import get_pdf_storage


AUDIT_DIR = Path("/app/pdfs/.source_fidelity_audits")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _targets(book_ids: list[int]) -> list[tuple[Book, BookFile]]:
    with SessionLocal() as db:
        query = (
            db.query(Book, BookFile)
            .join(BookFile, BookFile.book_id == Book.id)
            .filter(db.query(Chunk.id).filter(Chunk.book_id == Book.id).exists())
        )
        if book_ids:
            query = query.filter(Book.id.in_(book_ids))
        return query.order_by(Book.id, BookFile.id).all()


def _exact_page_matches(chunks: list[Chunk], pages: list[dict]) -> tuple[list[int], Counter]:
    page_text = {
        int(page["page_number"]): normalize_literal(page.get("text"))
        for page in pages
    }
    matched: list[int] = []
    reasons: Counter = Counter()
    for chunk in chunks:
        if chunk.pdf_page is None:
            reasons["missing_pdf_page"] += 1
            continue
        source_page = page_text.get(int(chunk.pdf_page), "")
        literal_chunk = normalize_literal(chunk.text)
        if not source_page:
            reasons["empty_source_page"] += 1
        elif not literal_chunk:
            reasons["empty_chunk"] += 1
        elif literal_chunk in source_page:
            matched.append(chunk.id)
        else:
            reasons["wording_differs_from_pdf_text_layer"] += 1
    return matched, reasons


def _audit_target(book: Book, book_file: BookFile, extractor: PDFExtractor, storage, apply: bool) -> tuple[dict, Counter]:
    entry = {
        "book_id": book.id,
        "book_file_id": book_file.id,
        "title": book.title,
        "filename": book_file.original_filename,
        "status": "pending",
        "matched_chunks": 0,
        "unverified_chunks": 0,
        "reasons": {},
    }
    totals: Counter = Counter()
    local_path = storage.resolve_for_processing(book_file.stored_path)
    if not local_path:
        entry["status"] = "file_unavailable"
        totals["file_unavailable"] += 1
        return entry, totals

    with SessionLocal() as db:
        chunks = (
            db.query(Chunk)
            .filter(
                Chunk.book_id == book.id,
                Chunk.book_file_id == book_file.id,
            )
            .order_by(Chunk.id)
            .all()
        )
        if not chunks:
            entry["status"] = "no_file_bound_chunks"
            totals["no_file_bound_chunks"] += 1
            return entry, totals

        already_audited = all(
            chunk.source_fidelity == "verified"
            or chunk.extraction_method in {
                "digital_text_audited",
                "digital_text_candidate",
                "legacy_audited",
                "scanned_audited",
            }
            for chunk in chunks
        )
        if apply and already_audited:
            matched = sum(chunk.source_fidelity in {"source_text", "verified"} for chunk in chunks)
            entry["status"] = "already_audited"
            entry["matched_chunks"] = matched
            entry["unverified_chunks"] = len(chunks) - matched
            totals["already_audited_files"] += 1
            totals["matched_chunks"] += matched
            totals["unverified_chunks"] += len(chunks) - matched
            return entry, totals

        if not extractor._is_digital(local_path):
            entry["status"] = "scanned_requires_visual_transcription"
            entry["unverified_chunks"] = len(chunks)
            entry["reasons"] = {"no_trusted_text_layer": len(chunks)}
            totals["scanned_files"] += 1
            totals["unverified_chunks"] += len(chunks)
            if apply:
                db.query(Chunk).filter(
                    Chunk.book_id == book.id,
                    Chunk.book_file_id == book_file.id,
                    Chunk.source_fidelity != "verified",
                ).update(
                    {
                        Chunk.extraction_method: "scanned_audited",
                        Chunk.source_fidelity: "unverified",
                        Chunk.fidelity_score: None,
                        Chunk.fidelity_reasons: "scan requires literal visual transcription",
                    },
                    synchronize_session=False,
                )
                db.commit()
            return entry, totals

        pages = extractor._extract_digital(local_path)
        matched_ids, reasons = _exact_page_matches(chunks, pages)
        entry["matched_chunks"] = len(matched_ids)
        entry["unverified_chunks"] = len(chunks) - len(matched_ids)
        entry["reasons"] = dict(reasons)
        entry["status"] = "exact_text_layer_audited"
        totals["digital_files"] += 1
        totals["matched_chunks"] += len(matched_ids)
        totals["unverified_chunks"] += len(chunks) - len(matched_ids)

        if apply:
            # First fail closed for this edition, then promote only exact
            # same-page matches in the same transaction.
            db.query(Chunk).filter(
                Chunk.book_id == book.id,
                Chunk.book_file_id == book_file.id,
                Chunk.source_fidelity != "verified",
            ).update(
                {
                    Chunk.extraction_method: "legacy_audited",
                    Chunk.source_fidelity: "unverified",
                    Chunk.fidelity_score: None,
                    Chunk.fidelity_reasons: "not an exact same-page PDF text-layer match",
                },
                synchronize_session=False,
            )
            if matched_ids:
                db.query(Chunk).filter(Chunk.id.in_(matched_ids)).update(
                    {
                        Chunk.extraction_method: "digital_text_audited",
                        Chunk.source_fidelity: "source_text",
                        Chunk.fidelity_score: 1.0,
                        Chunk.fidelity_reasons: "exact wording found on recorded PDF page",
                    },
                    synchronize_session=False,
                )
            db.commit()
    return entry, totals


def _fail_closed(book_id: int, book_file_id: int, error: str) -> None:
    with SessionLocal() as db:
        db.query(Chunk).filter(
            Chunk.book_id == book_id,
            Chunk.book_file_id == book_file_id,
            Chunk.source_fidelity != "verified",
        ).update(
            {
                Chunk.source_fidelity: "unverified",
                Chunk.fidelity_score: None,
                Chunk.fidelity_reasons: f"source audit error: {error}"[:1000],
            },
            synchronize_session=False,
        )
        db.commit()


def audit(book_ids: list[int], apply: bool) -> dict:
    init_db()
    extractor = PDFExtractor()
    storage = get_pdf_storage()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    checkpoint = AUDIT_DIR / f"source-fidelity-{stamp}.jsonl"
    output = AUDIT_DIR / f"source-fidelity-{stamp}.json"
    report = {
        "created_at": _now(),
        "apply": apply,
        "books": [],
        "totals": Counter(),
        "checkpoint_path": str(checkpoint),
    }

    # A book may have multiple source files. Only the chunks explicitly tied
    # to each file are compared with it; no cross-edition promotion is allowed.
    for book, book_file in _targets(book_ids):
        try:
            entry, target_totals = _audit_target(book, book_file, extractor, storage, apply)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            entry = {
                "book_id": book.id,
                "book_file_id": book_file.id,
                "title": book.title,
                "filename": book_file.original_filename,
                "status": "audit_error_fail_closed",
                "matched_chunks": 0,
                "unverified_chunks": 0,
                "reasons": {"error": error},
            }
            target_totals = Counter({"audit_error_files": 1})
            if apply:
                _fail_closed(book.id, book_file.id, error)
        report["books"].append(entry)
        report["totals"].update(target_totals)
        with checkpoint.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(json.dumps(entry, ensure_ascii=False), flush=True)

    report["totals"] = dict(report["totals"])
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(output)
    print(json.dumps({"report_path": str(output), "totals": report["totals"]}, ensure_ascii=False), flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", type=int, action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    audit(args.book_id, args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
