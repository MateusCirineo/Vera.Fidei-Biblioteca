"""Promote logical excerpts only when an identical visual source is stored.

Some catalog records are short logical works without their own PDF. They may
become quotable only when their complete text exactly equals a visually checked
passage in another catalog PDF. This command records that explicit provenance
and points the PDF button at the real source file.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from models.database import Book, BookFile, Chunk, SessionLocal, Translation, VerifiedPassage
from search.text_search import TextSearchClient
from services.source_fidelity_service import normalize_literal


BACKUP_ROOT = Path("/app/pdfs/.visual_page_reviews/backups/source_aliases")

# target book -> (source book, source file, physical PDF page)
SOURCE_ALIASES: dict[int, tuple[int, int, int]] = {
    1: (1777, 3285, 256),
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        "extraction_method": chunk.extraction_method,
        "source_fidelity": chunk.source_fidelity,
        "fidelity_score": chunk.fidelity_score,
    }


def sync_alias(target_book_id: int, text_search: TextSearchClient) -> dict:
    source_book_id, source_file_id, source_page = SOURCE_ALIASES[target_book_id]
    with SessionLocal() as db:
        target = db.get(Book, target_book_id)
        source_file = db.get(BookFile, source_file_id)
        if target is None or source_file is None or source_file.book_id != source_book_id:
            raise RuntimeError("source alias catalog mapping is invalid")
        source_passages = (
            db.query(VerifiedPassage)
            .filter(
                VerifiedPassage.book_id == source_book_id,
                VerifiedPassage.book_file_id == source_file_id,
                VerifiedPassage.pdf_page == source_page,
                VerifiedPassage.verification_method == "visual_pdf",
            )
            .all()
        )
        if len(source_passages) != 1:
            raise RuntimeError("source alias requires exactly one visual_pdf passage")
        source = source_passages[0]
        chunks = db.query(Chunk).filter(Chunk.book_id == target_book_id).order_by(Chunk.id).all()
        if not chunks:
            raise RuntimeError("logical source alias has no chunks")
        target_text = normalize_literal(" ".join(chunk.text for chunk in chunks))
        source_text = normalize_literal(source.text)
        if target_text != source_text:
            raise RuntimeError("logical work text differs from the visually verified source passage")

        if all(
            chunk.source_fidelity == "verified"
            and chunk.book_file_id == source_file_id
            and chunk.pdf_page == source_page
            for chunk in chunks
        ):
            return {"status": "already_synced", "book_id": target_book_id, "chunks": len(chunks)}

        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_ROOT / f"book_{target_book_id}_before_alias_{stamp}.json.gz"
        translations = (
            db.query(Translation).filter(Translation.chunk_id.in_([chunk.id for chunk in chunks])).all()
        )
        payload = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "target_book_id": target_book_id,
            "source": {
                "book_id": source_book_id,
                "book_file_id": source_file_id,
                "pdf_page": source_page,
                "verified_passage_id": source.id,
                "evidence_ref": source.evidence_ref,
            },
            "chunks": [
                {
                    "id": chunk.id,
                    "book_file_id": chunk.book_file_id,
                    "pdf_page": chunk.pdf_page,
                    "text": chunk.text,
                    "extraction_method": chunk.extraction_method,
                    "source_fidelity": chunk.source_fidelity,
                    "fidelity_score": chunk.fidelity_score,
                    "fidelity_reasons": chunk.fidelity_reasons,
                }
                for chunk in chunks
            ],
            "translations": [
                {"id": row.id, "chunk_id": row.chunk_id, "language": row.language, "text": row.text}
                for row in translations
            ],
        }
        with gzip.open(backup, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)

        for chunk in chunks:
            chunk.book_file_id = source_file_id
            chunk.pdf_page = source_page
            chunk.extraction_method = "visual_transcription_alias"
            chunk.source_fidelity = "verified"
            chunk.fidelity_score = 1.0
            chunk.fidelity_reasons = f"exact_logical_alias_of_verified_passage:{source.id}"

        fingerprint = _sha256(source.text)
        stored = (
            db.query(VerifiedPassage)
            .filter(
                VerifiedPassage.book_id == target_book_id,
                VerifiedPassage.pdf_page == source_page,
                VerifiedPassage.text_sha256 == fingerprint,
            )
            .first()
        )
        if stored is None:
            stored = VerifiedPassage(
                book_id=target_book_id,
                pdf_page=source_page,
                text_sha256=fingerprint,
            )
            db.add(stored)
        stored.book_file_id = source_file_id
        stored.text = source.text
        stored.language = source.language
        stored.verification_method = "visual_pdf_source_alias"
        stored.evidence_ref = (
            f"alias_of_verified_passage:{source.id};{source.evidence_ref or ''}"
        )

        try:
            text_search.index_chunks([(chunk.id, _es_doc(target, chunk)) for chunk in chunks])
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {
        "status": "synced",
        "book_id": target_book_id,
        "source_book_id": source_book_id,
        "source_file_id": source_file_id,
        "pdf_page": source_page,
        "chunks": len(chunks),
        "backup": str(backup),
    }


def main() -> int:
    text_search = TextSearchClient()
    failed = 0
    for target_book_id in SOURCE_ALIASES:
        try:
            print(json.dumps(sync_alias(target_book_id, text_search), ensure_ascii=False), flush=True)
        except Exception as exc:
            failed += 1
            print(json.dumps({"status": "failed", "book_id": target_book_id, "error": str(exc)}), flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
