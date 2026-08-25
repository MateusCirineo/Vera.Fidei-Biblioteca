"""Prepare fail-closed visual review packs for PDF pages.

The generated manifest is deliberately not importable: every entry starts with
``visual_confirmation=false`` and has no reviewer/review timestamp. A reviewer
must inspect the rendered image, correct the transcription file and explicitly
finalize the evidence before ``import_verified_pages`` can accept it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from models.database import Book, BookFile, SessionLocal
from scripts.import_verified_pages import (
    _render_page,
    _sha256_file,
    rendered_page_fingerprint,
    transcription_sha256,
)
from storage.pdf_storage import get_pdf_storage


DEFAULT_CANDIDATE_ROOT = Path("/app/pdfs/.ocr_reindex_cache")
DEFAULT_VERIFICATION_ROOT = Path("/app/pdfs/.page_verification")
DEFAULT_OUTPUT_ROOT = Path("/app/pdfs/.visual_page_reviews/pending")


def parse_pages(values: list[str]) -> list[int]:
    pages: set[int] = set()
    for value in values:
        for part in value.split(","):
            token = part.strip()
            if not token:
                continue
            if "-" in token:
                start_text, end_text = token.split("-", 1)
                start, end = int(start_text), int(end_text)
                if start < 1 or end < start:
                    raise ValueError(f"invalid page range: {token}")
                pages.update(range(start, end + 1))
            else:
                page = int(token)
                if page < 1:
                    raise ValueError(f"invalid page number: {token}")
                pages.add(page)
    if not pages:
        raise ValueError("at least one page is required")
    return sorted(pages)


def _target(book_id: int) -> tuple[Book, BookFile]:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        book_file = (
            db.query(BookFile).filter(BookFile.book_id == book_id).order_by(BookFile.id).first()
        )
        if book is None or book_file is None:
            raise RuntimeError(f"book {book_id} does not have a PDF source")
        db.expunge(book)
        db.expunge(book_file)
        return book, book_file


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


def _latest_page_file(root: Path, book_id: int, folder: str, page: int) -> Path | None:
    base = root / f"book_{book_id}"
    candidates = list(base.glob(f"*/{folder}/page_{page:04d}.txt"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _candidate_page(root: Path, book_id: int, page: int) -> Path:
    base = root / f"book_{book_id}"
    candidates = list(base.glob(f"*/page_{page:04d}.txt"))
    if not candidates:
        raise RuntimeError(f"candidate OCR missing for book={book_id} page={page}")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _atomic_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def prepare_pack(
    *,
    book_id: int,
    pages: list[int],
    dpi: int,
    candidate_root: Path,
    verification_root: Path,
    output_root: Path,
    force_transcription: bool,
) -> dict:
    book, book_file = _target(book_id)
    pdf_path = _resolve_pdf(book_file)
    pdf_sha256 = _sha256_file(pdf_path)
    pack_dir = output_root / f"book_{book_id}" / pdf_sha256[:16]
    pack_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []

    for page in pages:
        candidate_path = _candidate_page(candidate_root, book_id, page)
        verifier_path = _latest_page_file(verification_root, book_id, "verifier_text", page)
        candidate_text = candidate_path.read_text(encoding="utf-8")
        verifier_text = verifier_path.read_text(encoding="utf-8") if verifier_path else ""

        image = _render_page(pdf_path, page, dpi)
        pixel_sha256 = rendered_page_fingerprint(image)
        image_path = pack_dir / f"page_{page:04d}_{dpi}dpi.png"
        temporary_image = image_path.with_suffix(".tmp.png")
        image.save(temporary_image, format="PNG")
        image.close()
        temporary_image.replace(image_path)

        candidate_copy = pack_dir / f"page_{page:04d}.candidate.txt"
        verifier_copy = pack_dir / f"page_{page:04d}.verifier.txt"
        transcription_path = pack_dir / f"page_{page:04d}.transcription.txt"
        _atomic_text(candidate_copy, candidate_text)
        _atomic_text(verifier_copy, verifier_text)
        if force_transcription or not transcription_path.exists():
            _atomic_text(transcription_path, candidate_text)

        transcription_text = transcription_path.read_text(encoding="utf-8")
        entries.append({
            "book_id": book_id,
            "book_file_id": book_file.id,
            "pdf_page": page,
            "language": book.language,
            "reviewer": None,
            "reviewed_at": None,
            "render_dpi": dpi,
            "pdf_sha256": pdf_sha256,
            "render_pixel_sha256": pixel_sha256,
            "transcription_sha256": transcription_sha256(transcription_text),
            "transcription_file": transcription_path.name,
            "verification_method": "pending_visual_pdf",
            "visual_confirmation": False,
            "blank_page": not bool(transcription_text.strip()),
            "review_image": image_path.name,
            "candidate_file": candidate_copy.name,
            "candidate_sha256": transcription_sha256(candidate_text),
            "candidate_origin": str(candidate_path),
            "verifier_file": verifier_copy.name,
            "verifier_sha256": transcription_sha256(verifier_text) if verifier_text else None,
            "verifier_origin": str(verifier_path) if verifier_path else None,
        })

    manifest = {
        "schema_version": 1,
        "status": "pending_visual_review",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "book": {
            "id": book.id,
            "title": book.title,
            "language": book.language,
            "book_file_id": book_file.id,
            "pdf": book_file.original_filename,
        },
        "public_promotion": False,
        "entries": entries,
    }
    manifest_path = pack_dir / "manifest.draft.json"
    _atomic_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    return {
        "status": "visual_review_pack_prepared",
        "book_id": book_id,
        "pages": len(entries),
        "pack_dir": str(pack_dir),
        "manifest": str(manifest_path),
        "public_promotion": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", type=int, required=True)
    parser.add_argument("--page", action="append", required=True, help="Page, comma list, or inclusive range")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--verification-root", type=Path, default=DEFAULT_VERIFICATION_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--force-transcription", action="store_true")
    args = parser.parse_args()
    if not 150 <= args.dpi <= 600:
        parser.error("--dpi must be between 150 and 600")
    try:
        pages = parse_pages(args.page)
        report = prepare_pack(
            book_id=args.book_id,
            pages=pages,
            dpi=args.dpi,
            candidate_root=args.candidate_root,
            verification_root=args.verification_root,
            output_root=args.output_root,
            force_transcription=args.force_transcription,
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), flush=True)
        return 1
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
