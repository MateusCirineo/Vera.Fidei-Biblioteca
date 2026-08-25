"""Import full-page transcriptions that were visually checked against a PDF.

The command fails closed. It accepts only manifests that explicitly record a
visual review and whose PDF, rendered pixel and transcription hashes still
match. It backs up and replaces only the reviewed page; unrelated pages stay
live throughout the swap.

Run inside the backend container from /app::

    python -m scripts.import_verified_pages /app/pdfs/.visual_page_reviews/review.json
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pdf2image
from PIL import Image

sys.path.insert(0, "/app")

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import POPPLER_PATH
from models.database import (
    Book,
    BookFile,
    Chunk,
    SessionLocal,
    Translation,
    VerifiedPageReview,
    init_db,
)
from search.text_search import TextSearchClient
from services.source_fidelity_service import normalize_literal
from storage.pdf_storage import get_pdf_storage


DEFAULT_BACKUP_ROOT = Path("/app/pdfs/.visual_page_reviews/backups")
DEFAULT_EVIDENCE_ROOT = Path("/app/pdfs/.visual_page_reviews/evidence")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReviewEntry:
    book_id: int
    book_file_id: int
    pdf_page: int
    language: str
    reviewer: str
    reviewed_at: datetime
    render_dpi: int
    pdf_sha256: str
    render_pixel_sha256: str
    transcription_sha256: str
    transcription_path: Path
    blank_page: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(payload: dict[str, Any]) -> None:
    print(json.dumps({"at": _now(), **payload}, ensure_ascii=False), flush=True)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def transcription_sha256(text: str | None) -> str:
    return _sha256_bytes(normalize_literal(text).encode("utf-8"))


def rendered_page_fingerprint(image: Image.Image) -> str:
    """Hash visible pixels plus dimensions/mode, not PNG encoder metadata."""
    header = f"{image.mode}\0{image.width}\0{image.height}\0".encode("ascii")
    return _sha256_bytes(header + image.tobytes())


def _required_string(raw: dict[str, Any], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _valid_sha256(raw: dict[str, Any], field: str) -> str:
    value = _required_string(raw, field).casefold()
    if not SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _reviewed_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewed_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("reviewed_at must include a timezone")
    if parsed > datetime.now(timezone.utc):
        raise ValueError("reviewed_at cannot be in the future")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def parse_review_entry(raw: dict[str, Any], manifest_dir: Path) -> ReviewEntry:
    if raw.get("verification_method") != "visual_pdf":
        raise ValueError("verification_method must be visual_pdf")
    if raw.get("visual_confirmation") is not True:
        raise ValueError("visual_confirmation must be explicitly true")

    try:
        book_id = int(raw["book_id"])
        book_file_id = int(raw["book_file_id"])
        pdf_page = int(raw["pdf_page"])
        render_dpi = int(raw["render_dpi"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("book_id, book_file_id, pdf_page and render_dpi must be integers") from exc
    if min(book_id, book_file_id, pdf_page) < 1:
        raise ValueError("book_id, book_file_id and pdf_page must be positive")
    if not 150 <= render_dpi <= 600:
        raise ValueError("render_dpi must be between 150 and 600")

    relative = Path(_required_string(raw, "transcription_file"))
    if relative.is_absolute():
        raise ValueError("transcription_file must be relative to the manifest")
    manifest_root = manifest_dir.resolve()
    transcription_path = (manifest_root / relative).resolve()
    if manifest_root not in transcription_path.parents:
        raise ValueError("transcription_file must stay inside the manifest directory")

    return ReviewEntry(
        book_id=book_id,
        book_file_id=book_file_id,
        pdf_page=pdf_page,
        language=_required_string(raw, "language"),
        reviewer=_required_string(raw, "reviewer"),
        reviewed_at=_reviewed_at(_required_string(raw, "reviewed_at")),
        render_dpi=render_dpi,
        pdf_sha256=_valid_sha256(raw, "pdf_sha256"),
        render_pixel_sha256=_valid_sha256(raw, "render_pixel_sha256"),
        transcription_sha256=_valid_sha256(raw, "transcription_sha256"),
        transcription_path=transcription_path,
        blank_page=raw.get("blank_page") is True,
    )


def load_manifest(path: Path) -> tuple[str, list[ReviewEntry]]:
    raw_bytes = path.read_bytes()
    payload = json.loads(raw_bytes)
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("manifest schema_version must be 1")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("manifest entries must be a non-empty list")
    entries = [parse_review_entry(raw, path.parent) for raw in raw_entries]
    sources = {(entry.book_id, entry.pdf_page) for entry in entries}
    if len(sources) != len(entries):
        raise ValueError("manifest cannot review the same book/page more than once")
    return _sha256_bytes(raw_bytes), entries


def _resolve_pdf(book_file: BookFile) -> Path:
    resolved = get_pdf_storage().resolve_for_processing(book_file.stored_path)
    candidates = [
        Path(resolved) if resolved else None,
        Path("/app/pdfs") / book_file.original_filename,
        Path("/app/pdfs") / Path(book_file.stored_path).name,
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    raise RuntimeError(f"PDF file not found for book_file_id={book_file.id}")


def _render_page(pdf_path: Path, page: int, dpi: int) -> Image.Image:
    images = pdf2image.convert_from_path(
        str(pdf_path),
        dpi=dpi,
        first_page=page,
        last_page=page,
        fmt="png",
        thread_count=1,
        poppler_path=POPPLER_PATH,
    )
    if len(images) != 1:
        raise RuntimeError(f"could not render PDF page {page}")
    return images[0]


def _chunk_payload(chunk: Chunk) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "book_id": chunk.book_id,
        "book_file_id": chunk.book_file_id,
        "text": chunk.text,
        "sequence_index": chunk.sequence_index,
        "chunk_author": chunk.chunk_author,
        "volume": chunk.volume,
        "column_start": chunk.column_start,
        "column_end": chunk.column_end,
        "chapter_or_section": chunk.chapter_or_section,
        "pdf_page": chunk.pdf_page,
        "char_offset_start": chunk.char_offset_start,
        "char_offset_end": chunk.char_offset_end,
        "visual_anchor": chunk.visual_anchor,
        "extraction_method": chunk.extraction_method,
        "source_fidelity": chunk.source_fidelity,
        "fidelity_score": chunk.fidelity_score,
        "fidelity_reasons": chunk.fidelity_reasons,
    }


def _backup_page(book: Book, entry: ReviewEntry, backup_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = backup_root / f"book_{book.id}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"page_{entry.pdf_page:04d}_before_visual_{stamp}.json.gz"
    with SessionLocal() as db:
        chunks = (
            db.query(Chunk)
            .filter(Chunk.book_id == book.id, Chunk.pdf_page == entry.pdf_page)
            .order_by(Chunk.id)
            .all()
        )
        chunk_ids = [chunk.id for chunk in chunks]
        translations = (
            db.query(Translation).filter(Translation.chunk_id.in_(chunk_ids)).order_by(Translation.id).all()
            if chunk_ids else []
        )
        payload = {
            "created_at": _now(),
            "book_id": book.id,
            "pdf_page": entry.pdf_page,
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


def _es_doc(book: Book, chunk: Chunk) -> dict[str, Any]:
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


def _evidence_path(evidence_root: Path, entry: ReviewEntry) -> Path:
    return (
        evidence_root
        / f"book_{entry.book_id}"
        / entry.render_pixel_sha256[:16]
        / f"page_{entry.pdf_page:04d}_{entry.render_dpi}dpi.png"
    )


def _validate_transcription(entry: ReviewEntry) -> str:
    if not entry.transcription_path.is_file():
        raise RuntimeError(f"transcription file not found: {entry.transcription_path}")
    text = entry.transcription_path.read_text(encoding="utf-8")
    normalized = normalize_literal(text)
    if not normalized and not entry.blank_page:
        raise RuntimeError("empty transcription requires blank_page=true")
    if normalized and entry.blank_page:
        raise RuntimeError("blank_page=true requires an empty transcription")
    actual = transcription_sha256(text)
    if actual != entry.transcription_sha256:
        raise RuntimeError(
            f"transcription hash mismatch: expected {entry.transcription_sha256}, got {actual}"
        )
    return text


def import_review(
    entry: ReviewEntry,
    *,
    manifest_sha256: str,
    text_search: TextSearchClient,
    chunker: Chunker,
    backup_root: Path,
    evidence_root: Path,
    pdf_hash_cache: dict[Path, str],
    dry_run: bool,
) -> dict[str, Any]:
    with SessionLocal() as db:
        book = db.get(Book, entry.book_id)
        book_file = db.get(BookFile, entry.book_file_id)
        if book is None or book_file is None or book_file.book_id != entry.book_id:
            raise RuntimeError("book_id/book_file_id do not identify the same source")
        existing = (
            db.query(VerifiedPageReview)
            .filter(
                VerifiedPageReview.book_id == entry.book_id,
                VerifiedPageReview.pdf_page == entry.pdf_page,
                VerifiedPageReview.text_sha256 == entry.transcription_sha256,
                VerifiedPageReview.pdf_sha256 == entry.pdf_sha256,
                VerifiedPageReview.render_pixel_sha256 == entry.render_pixel_sha256,
            )
            .first()
        )
        current_page_fidelity_rows = (
            db.query(Chunk.source_fidelity)
            .filter(Chunk.book_id == entry.book_id, Chunk.pdf_page == entry.pdf_page)
            .all()
        )
        current_page_fidelities = {value for (value,) in current_page_fidelity_rows}
        page_is_already_current = (
            (entry.blank_page and not current_page_fidelity_rows)
            or (
                not entry.blank_page
                and bool(current_page_fidelity_rows)
                and current_page_fidelities == {"verified"}
            )
        )
        if existing is not None and page_is_already_current:
            return {"status": "already_imported", "book_id": entry.book_id, "pdf_page": entry.pdf_page}

    text = _validate_transcription(entry)
    pdf_path = _resolve_pdf(book_file)
    actual_pdf_sha256 = pdf_hash_cache.get(pdf_path)
    if actual_pdf_sha256 is None:
        actual_pdf_sha256 = _sha256_file(pdf_path)
        pdf_hash_cache[pdf_path] = actual_pdf_sha256
    if actual_pdf_sha256 != entry.pdf_sha256:
        raise RuntimeError(f"PDF hash mismatch: expected {entry.pdf_sha256}, got {actual_pdf_sha256}")

    image = _render_page(pdf_path, entry.pdf_page, entry.render_dpi)
    actual_render_sha256 = rendered_page_fingerprint(image)
    if actual_render_sha256 != entry.render_pixel_sha256:
        image.close()
        raise RuntimeError(
            f"rendered pixel hash mismatch: expected {entry.render_pixel_sha256}, got {actual_render_sha256}"
        )
    if dry_run:
        image.close()
        return {"status": "validated", "book_id": entry.book_id, "pdf_page": entry.pdf_page}

    evidence_path = _evidence_path(evidence_root, entry)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_evidence = evidence_path.with_suffix(".tmp.png")
    image.save(temporary_evidence, format="PNG")
    image.close()
    temporary_evidence.replace(evidence_path)

    backup_path = _backup_page(book, entry, backup_root)
    raw_chunks = chunker.chunk(
        [{
            "page_number": entry.pdf_page,
            "text": text,
            "extraction_method": "visual_transcription",
            "source_fidelity": "verified",
            "fidelity_score": 1.0,
            "fidelity_reasons": "full_page_visual_pdf_review",
        }],
        {},
    )

    new_ids: list[int] = []
    old_ids: list[int] = []
    with SessionLocal() as db:
        book = db.get(Book, entry.book_id)
        if book is None:
            raise RuntimeError(f"book {entry.book_id} disappeared before swap")
        old_chunks = (
            db.query(Chunk)
            .filter(Chunk.book_id == entry.book_id, Chunk.pdf_page == entry.pdf_page)
            .order_by(Chunk.sequence_index, Chunk.id)
            .all()
        )
        old_ids = [chunk.id for chunk in old_chunks]
        first = old_chunks[0] if old_chunks else None
        base_sequence = min(
            (chunk.sequence_index for chunk in old_chunks if chunk.sequence_index is not None),
            default=entry.pdf_page * 1000,
        )
        inserted: list[Chunk] = []
        for index, raw in enumerate(raw_chunks):
            chunk = Chunk(
                book_id=entry.book_id,
                book_file_id=entry.book_file_id,
                text=raw["text"],
                sequence_index=base_sequence + index,
                chunk_author=first.chunk_author if first else None,
                volume=first.volume if first else book.volume_number,
                column_start=raw.get("column_start"),
                column_end=raw.get("column_end"),
                pdf_page=entry.pdf_page,
                char_offset_start=raw.get("char_offset_start"),
                char_offset_end=raw.get("char_offset_end"),
                visual_anchor=f"page{entry.pdf_page}",
                chapter_or_section=first.chapter_or_section if first else "",
                extraction_method="visual_transcription",
                source_fidelity="verified",
                fidelity_score=1.0,
                fidelity_reasons="full_page_visual_pdf_review",
            )
            db.add(chunk)
            inserted.append(chunk)

        try:
            db.flush()
            new_ids = [int(chunk.id) for chunk in inserted if chunk.id is not None]
            text_search.index_chunks([(chunk.id, _es_doc(book, chunk)) for chunk in inserted])
            if old_ids:
                db.query(Translation).filter(Translation.chunk_id.in_(old_ids)).delete(synchronize_session=False)
                db.query(Chunk).filter(Chunk.id.in_(old_ids)).delete(synchronize_session=False)
            review = (
                db.query(VerifiedPageReview)
                .filter(
                    VerifiedPageReview.book_id == entry.book_id,
                    VerifiedPageReview.pdf_page == entry.pdf_page,
                    VerifiedPageReview.text_sha256 == entry.transcription_sha256,
                    VerifiedPageReview.pdf_sha256 == entry.pdf_sha256,
                    VerifiedPageReview.render_pixel_sha256 == entry.render_pixel_sha256,
                )
                .first()
            )
            if review is None:
                review = VerifiedPageReview(
                    book_id=entry.book_id,
                    pdf_page=entry.pdf_page,
                    text_sha256=entry.transcription_sha256,
                    pdf_sha256=entry.pdf_sha256,
                    render_pixel_sha256=entry.render_pixel_sha256,
                )
                db.add(review)
            review.book_file_id = entry.book_file_id
            review.text = text
            review.render_dpi = entry.render_dpi
            review.language = entry.language
            review.reviewer = entry.reviewer
            review.reviewed_at = entry.reviewed_at
            review.verification_method = "visual_pdf"
            review.evidence_ref = str(evidence_path)
            review.manifest_sha256 = manifest_sha256
            db.commit()
        except Exception:
            db.rollback()
            for chunk_id in new_ids:
                text_search.delete_chunk(chunk_id)
            raise

    for chunk_id in old_ids:
        text_search.delete_chunk(chunk_id)
    return {
        "status": "imported",
        "book_id": entry.book_id,
        "pdf_page": entry.pdf_page,
        "removed_chunks": len(old_ids),
        "inserted_chunks": len(new_ids),
        "backup": str(backup_path),
        "evidence": str(evidence_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest_sha256, entries = load_manifest(args.manifest)
    init_db()
    text_search = TextSearchClient()
    chunker = Chunker()
    pdf_hash_cache: dict[Path, str] = {}
    failed = 0
    for entry in entries:
        try:
            result = import_review(
                entry,
                manifest_sha256=manifest_sha256,
                text_search=text_search,
                chunker=chunker,
                backup_root=args.backup_root,
                evidence_root=args.evidence_root,
                pdf_hash_cache=pdf_hash_cache,
                dry_run=args.dry_run,
            )
            _log(result)
        except Exception as exc:
            failed += 1
            _log({
                "status": "failed",
                "book_id": entry.book_id,
                "pdf_page": entry.pdf_page,
                "error": str(exc),
            })
    _log({"status": "summary", "pages": len(entries), "failed": failed})
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
