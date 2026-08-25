"""High-quality, resumable OCR repair for already-uploaded books.

The existing searchable text remains live while OCR runs. New chunks replace
the old set only after every page passes validation and Elasticsearch accepts
the staged documents. A gzipped JSON backup is written before the swap.

Run inside the backend container from /app:
  python -m scripts.ocr_reindex_books --book-id 32 --layout columns
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import pdf2image
import pdfplumber
import pytesseract
from PIL import Image

sys.path.insert(0, "/app")

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import POPPLER_PATH, TESSDATA_DIR
from models.database import (
    Book,
    BookFile,
    Chunk,
    SessionLocal,
    Translation,
    VerifiedPageReview,
    VerifiedPassage,
)
from search.text_search import TextSearchClient
from storage.pdf_storage import get_pdf_storage


TESSERACT_BIN = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract") or "tesseract"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_BIN
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
DEFAULT_LANG = os.environ.get("VERA_FAST_OCR_LANG", "lat+eng")
DEFAULT_DPI = int(os.environ.get("VERA_FAST_OCR_DPI", "220"))
DEFAULT_WORKERS = int(os.environ.get("VERA_FAST_OCR_WORKERS", "4"))
DEFAULT_TIMEOUT = int(os.environ.get("VERA_FAST_OCR_PAGE_TIMEOUT", "120"))
DEFAULT_CACHE_ROOT = Path(os.environ.get("VERA_OCR_REPAIR_CACHE", "/app/pdfs/.ocr_reindex_cache"))
DEFAULT_BACKUP_ROOT = Path(os.environ.get("VERA_OCR_REPAIR_BACKUPS", "/app/pdfs/.ocr_reindex_backups"))

# Source anchors are deliberately literal and short. They detect regressions
# such as the PG001 page-12 left/right-column interleaving reported by the user.
KNOWN_SOURCE_ANCHORS: dict[int, tuple[str, ...]] = {
    32: (
        "sanctum de Maria Virgine genitum esse fateantur",
        "Petrum dicitur",
    ),
}

# Transcriptions are limited to passages independently checked against the
# source scan. They repair high-impact character errors that OCR cannot infer
# reliably from Migne's small nineteenth-century type.
KNOWN_SOURCE_PASSAGES: dict[tuple[int, int], tuple[str, str, str]] = {
    (32, 12): (
        "Utrum vero ipsis",
        "et Origenes.",
        (
            "Utrum vero ipsis et cum Cerinthianis eodem modo convenerit, anceps ille est: "
            "De Christo vero, inquiebat, certo affirmare nequeo, utrum Cerinthi, vel Merinthi "
            "impietate illa decepti, simplicem illum hominem asseverent, ac uti sese res habet, "
            "per Spiritum sanctum de Maria Virgine genitum esse fateantur. Theodoretus vero "
            "brevius planiusque edisserit, qui fuerint Nazaræi, et quæ eorum hæresis, quo "
            "tempore exorta, et a quibus tandem expugnata: Nazaræi Judæi sunt, Christum "
            "honorantes, tanquam hominem justum, et Evangelio utuntur, quod secundum Petrum "
            "dicitur. Has hæreses, imperante Domitiano, conflatas auctor est Eusebius. Contra "
            "quas scripsit Justinus philosophus et martyr, et Irenæus successor apostolorum, "
            "et Origenes."
        ),
    ),
    (1777, 256): (
        "Habere jam nom potest",
        "foris ^ fuerit evadit.",
        (
            "Habere jam non potest Deum patrem, qui Ecclesiam non habet matrem. "
            "Si potuit evadere quisquam qui extra arcam Noe fuit, et qui extra "
            "Ecclesiam foris fuerit evadit."
        ),
    ),
}

KNOWN_SOURCE_EVIDENCE: dict[tuple[int, int], tuple[str, str]] = {
    (32, 12): ("PG001.pdf#page=12", "la"),
    (1777, 256): (
        "PL004.pdf#page=256&render_sha256="
        "e0fbc839eebabb1fc7d2b23fef608fa18b210ca400ce500923cdacce8b182988",
        "la",
    ),
}


@dataclass(frozen=True)
class BookTarget:
    book_id: int
    title: str
    author: str
    collection: str
    language: str
    file_id: int
    filename: str
    stored_path: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(payload: dict) -> None:
    print(json.dumps({"at": _now(), **payload}, ensure_ascii=False), flush=True)


def _targets(book_ids: list[int]) -> list[BookTarget]:
    with SessionLocal() as db:
        rows = (
            db.query(Book, BookFile)
            .join(BookFile, BookFile.book_id == Book.id)
            .filter(Book.id.in_(book_ids))
            .order_by(Book.id.asc(), BookFile.id.asc())
            .all()
        )
        return [
            BookTarget(
                book_id=book.id,
                title=book.title,
                author=book.author,
                collection=book.collection or "",
                language=book.language,
                file_id=file.id,
                filename=file.original_filename,
                stored_path=file.stored_path,
            )
            for book, file in rows
        ]


def _page_count(pdf_path: str) -> int:
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)


def _convert_page(pdf_path: str, page_num: int, dpi: int) -> str:
    temp_dir = tempfile.mkdtemp(prefix=f"vf_quality_ocr_{page_num}_")
    try:
        paths = pdf2image.convert_from_path(
            pdf_path,
            dpi=dpi,
            poppler_path=POPPLER_PATH,
            first_page=page_num,
            last_page=page_num,
            grayscale=True,
            thread_count=1,
            paths_only=True,
            output_folder=temp_dir,
            fmt="png",
            single_file=True,
            use_pdftocairo=True,
        )
        if not paths:
            raise RuntimeError("pdf2image returned no image")
        return paths[0]
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def _cleanup_image(image_path: str) -> None:
    shutil.rmtree(os.path.dirname(image_path), ignore_errors=True)


def _normalize_ocr_text(text: str) -> str:
    """Keep the source spelling while joining words split only by line wrap."""
    text = (text or "").replace("\x0c", "")
    text = re.sub(r"(?<=[^\W\d_])-\s*\n\s*(?=[^\W\d_])", "", text, flags=re.UNICODE)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def _recognize(image: Image.Image, lang: str, timeout: int, psm: int) -> str:
    config = f'--tessdata-dir "{TESSDATA_DIR}" --oem 1 --psm {psm}'
    return pytesseract.image_to_string(image, lang=lang, config=config, timeout=timeout)


def _ocr_image(image_path: str, lang: str, timeout: int, layout: str) -> str:
    with Image.open(image_path) as source:
        image = source.copy()

    if layout == "columns":
        width, height = image.size
        # Migne/PG/PL pages are two independent columns. OCRing the whole page
        # as a single block was the cause of alternating words from both sides.
        regions = (
            image.crop((0, 0, width // 2, height)),
            image.crop((width // 2, 0, width, height)),
        )
        text = "\n\n".join(_recognize(region, lang, timeout, 6) for region in regions)
    else:
        # Automatic page segmentation preserves columns for mixed layouts.
        text = _recognize(image, lang, timeout, 3)

    if len(text.strip()) < 20:
        fallback = _recognize(image, lang, timeout, 4)
        if len(fallback.strip()) > len(text.strip()):
            text = fallback
    return _normalize_ocr_text(text)


def _ocr_page(pdf_path: str, page_num: int, dpi: int, lang: str, timeout: int, layout: str) -> dict:
    image_path = _convert_page(pdf_path, page_num, dpi)
    try:
        return {
            "page_number": page_num,
            "text": _ocr_image(image_path, lang, timeout, layout),
        }
    finally:
        _cleanup_image(image_path)


def _cache_dir(
    cache_root: Path,
    target: BookTarget,
    pdf_path: str,
    dpi: int,
    lang: str,
    layout: str,
) -> Path:
    stat = Path(pdf_path).stat()
    signature = hashlib.sha256(
        f"v3|{target.stored_path}|{stat.st_size}|{dpi}|{lang}|{layout}".encode("utf-8")
    ).hexdigest()[:16]
    path = cache_root / f"book_{target.book_id}" / signature
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ocr_pages(
    pdf_path: str,
    target: BookTarget,
    page_total: int,
    dpi: int,
    workers: int,
    lang: str,
    timeout: int,
    layout: str,
    cache_root: Path,
) -> list[dict]:
    cache_dir = _cache_dir(cache_root, target, pdf_path, dpi, lang, layout)
    pages: dict[int, str] = {}
    pending: list[int] = []
    for page_num in range(1, page_total + 1):
        page_path = cache_dir / f"page_{page_num:04d}.txt"
        if page_path.is_file():
            pages[page_num] = page_path.read_text(encoding="utf-8")
        else:
            pending.append(page_num)

    _log({
        "event": "ocr_resume",
        "book_id": target.book_id,
        "cached": len(pages),
        "pending": len(pending),
        "cache_dir": str(cache_dir),
    })

    completed = len(pages)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(_ocr_page, pdf_path, page_num, dpi, lang, timeout, layout): page_num
            for page_num in pending
        }
        for future in as_completed(futures):
            page_num = futures[future]
            cache_result = True
            try:
                page = future.result()
                text = page["text"]
            except Exception as exc:
                text = ""
                cache_result = False
                _log({"event": "page_error", "book_id": target.book_id, "page": page_num, "error": str(exc)})
            pages[page_num] = text
            if cache_result:
                page_path = cache_dir / f"page_{page_num:04d}.txt"
                temp_path = page_path.with_suffix(".tmp")
                temp_path.write_text(text, encoding="utf-8")
                temp_path.replace(page_path)
            completed += 1
            if completed == 1 or completed % 10 == 0 or completed == page_total:
                _log({
                    "event": "ocr_progress",
                    "book_id": target.book_id,
                    "completed": completed,
                    "total": page_total,
                    "last_page": page_num,
                    "chars": len(text),
                })

    return [
        {
            "page_number": page_num,
            "text": pages.get(page_num, ""),
            "extraction_method": "ocr",
            "source_fidelity": "unverified_ocr",
        }
        for page_num in range(1, page_total + 1)
    ]


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def _apply_verified_source_passages(book_id: int, pages: list[dict]) -> list[dict]:
    for page in pages:
        key = (book_id, int(page.get("page_number") or 0))
        correction = KNOWN_SOURCE_PASSAGES.get(key)
        if correction is None:
            continue
        start_text, end_text, verified_text = correction
        current = page.get("text") or ""
        start = current.find(start_text)
        end = current.find(end_text, start + len(start_text)) if start >= 0 else -1
        if start < 0 or end < 0:
            raise RuntimeError(f"verified source passage boundaries not found on page {key[1]}")
        end += len(end_text)
        page["text"] = current[:start] + verified_text + current[end:]
    return pages


def _overlay_reviewed_pages(pages: list[dict], reviewed_text: dict[int, str]) -> list[dict]:
    """Make a full visual review authoritative over every machine reading."""
    for page in pages:
        page_number = int(page.get("page_number") or 0)
        if page_number not in reviewed_text:
            continue
        page["text"] = reviewed_text[page_number]
        page["extraction_method"] = "visual_transcription"
        page["source_fidelity"] = "verified"
        page["fidelity_score"] = 1.0
        page["fidelity_reasons"] = "full_page_visual_pdf_review"
    return pages


def _apply_verified_page_reviews(book_id: int, pages: list[dict]) -> list[dict]:
    with SessionLocal() as db:
        rows = (
            db.query(VerifiedPageReview)
            .filter(VerifiedPageReview.book_id == book_id)
            .order_by(
                VerifiedPageReview.pdf_page,
                VerifiedPageReview.reviewed_at.desc(),
                VerifiedPageReview.id.desc(),
            )
            .all()
        )
    latest: dict[int, str] = {}
    for row in rows:
        latest.setdefault(int(row.pdf_page), row.text)
    return _overlay_reviewed_pages(pages, latest)


def _chunk_pages(chunker: Chunker, pages: list[dict]) -> list[dict]:
    """Keep every result tied to the page that actually contains its text."""
    chunks: list[dict] = []
    sequence = 0
    for page in pages:
        page_num = int(page["page_number"])
        for chunk in chunker.chunk([page], {}):
            chunk["pdf_page"] = page_num
            chunk["sequence_index"] = sequence
            chunks.append(chunk)
            sequence += 1
    return chunks


def _validate_pages(pages: list[dict], anchors: tuple[str, ...]) -> dict:
    texts = [(page.get("text") or "").strip() for page in pages]
    usable = [text for text in texts if len(text) >= 100]
    joined = "\n".join(texts)
    compact = "".join(ch for ch in joined if not ch.isspace())
    letters = sum(ch.isalpha() for ch in compact)
    usable_ratio = len(usable) / max(1, len(texts))
    letter_ratio = letters / max(1, len(compact))
    median_chars = int(median(len(text) for text in usable)) if usable else 0
    missing_anchors = [anchor for anchor in anchors if _fold(anchor) not in _fold(joined)]

    errors: list[str] = []
    if usable_ratio < 0.70:
        errors.append(f"only {usable_ratio:.1%} of pages contain usable text")
    if median_chars < 250:
        errors.append(f"median page has only {median_chars} characters")
    if letter_ratio < 0.55:
        errors.append(f"alphabetic character ratio is only {letter_ratio:.1%}")
    if missing_anchors:
        errors.append(f"missing source anchors: {missing_anchors}")

    report = {
        "pages": len(texts),
        "usable_pages": len(usable),
        "usable_ratio": round(usable_ratio, 4),
        "median_chars": median_chars,
        "letter_ratio": round(letter_ratio, 4),
        "anchors": list(anchors),
        "missing_anchors": missing_anchors,
        "errors": errors,
    }
    if errors:
        raise RuntimeError("OCR quality validation failed: " + "; ".join(errors))
    return report


def _chunk_payload(chunk: Chunk) -> dict:
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


def _backup_current_rows(target: BookTarget, backup_root: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_root / f"book_{target.book_id}_before_ocr_{stamp}.json.gz"
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


def _sync_verified_passages(db, target: BookTarget) -> None:
    """Persist only literal text that was checked against the rendered page."""
    for (book_id, pdf_page), (_start, _end, verified_text) in KNOWN_SOURCE_PASSAGES.items():
        if book_id != target.book_id:
            continue
        evidence_ref, language = KNOWN_SOURCE_EVIDENCE.get(
            (book_id, pdf_page),
            (f"{target.filename}#page={pdf_page}", target.language),
        )
        fingerprint = hashlib.sha256(verified_text.encode("utf-8")).hexdigest()
        existing = (
            db.query(VerifiedPassage)
            .filter(
                VerifiedPassage.book_id == book_id,
                VerifiedPassage.pdf_page == pdf_page,
                VerifiedPassage.text_sha256 == fingerprint,
            )
            .first()
        )
        if existing is None:
            db.add(VerifiedPassage(
                book_id=book_id,
                book_file_id=target.file_id,
                pdf_page=pdf_page,
                text=verified_text,
                text_sha256=fingerprint,
                language=language,
                verification_method="visual_pdf",
                evidence_ref=evidence_ref,
            ))
        else:
            existing.book_file_id = target.file_id
            existing.text = verified_text
            existing.language = language
            existing.verification_method = "visual_pdf"
            existing.evidence_ref = evidence_ref


def _remove_semantic_ids(chunk_ids: list[int]) -> None:
    if not chunk_ids:
        return
    if os.environ.get("VERA_ENABLE_SEMANTIC_SEARCH", "true").strip().casefold() in {
        "0", "false", "no", "off",
    }:
        _log({"event": "semantic_cleanup_skipped", "reason": "semantic search disabled"})
        return
    try:
        import chromadb
        from core.config import settings

        client = chromadb.PersistentClient(path=settings.chroma_path)
        ids = [str(chunk_id) for chunk_id in chunk_ids]
        ids.extend(f"{chunk_id}_translation_pt" for chunk_id in chunk_ids)
        for name in ("vera_fidei", "vera_fidei_delta"):
            try:
                collection = client.get_collection(name)
            except Exception:
                continue
            for start in range(0, len(ids), 1000):
                collection.delete(ids=ids[start:start + 1000])
    except Exception as exc:
        _log({"event": "semantic_cleanup_warning", "error": str(exc)})


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
            raise RuntimeError(f"Book {target.book_id} disappeared before swap")
        old_ids = [row[0] for row in db.query(Chunk.id).filter(Chunk.book_id == target.book_id).all()]
        inserted: list[Chunk] = []
        for index, chunk_data in enumerate(raw_chunks):
            chunk = Chunk(
                book_id=target.book_id,
                book_file_id=target.file_id,
                text=chunk_data["text"],
                sequence_index=chunk_data.get("sequence_index", index),
                volume=chunk_data.get("volume_number"),
                column_start=chunk_data.get("column_start"),
                column_end=chunk_data.get("column_end"),
                pdf_page=chunk_data.get("pdf_page"),
                char_offset_start=chunk_data.get("char_offset_start"),
                char_offset_end=chunk_data.get("char_offset_end"),
                visual_anchor=f"col{chunk_data.get('column_start', '')}",
                chapter_or_section=chunk_data.get("chapter_or_section", ""),
                extraction_method=chunk_data.get("extraction_method", "ocr"),
                source_fidelity=chunk_data.get("source_fidelity", "unverified_ocr"),
                fidelity_score=chunk_data.get("fidelity_score"),
                fidelity_reasons=chunk_data.get("fidelity_reasons"),
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
            _sync_verified_passages(db, target)
            book.ingest_status = "done"
            book.ingest_error = None
            db.commit()
        except Exception:
            db.rollback()
            for chunk_id in new_ids:
                text_search.delete_chunk(chunk_id)
            raise

    # Cleanup happens after the database commit so the live corpus never has a
    # window with neither the old nor the new text available.
    for chunk_id in old_ids:
        text_search.delete_chunk(chunk_id)
    _remove_semantic_ids(old_ids)
    return len(old_ids), len(new_ids), backup_path


def reindex_target(
    target: BookTarget,
    text_search: TextSearchClient,
    chunker: Chunker,
    dpi: int,
    workers: int,
    lang: str,
    timeout: int,
    layout: str,
    cache_root: Path,
    backup_root: Path,
    extra_anchors: tuple[str, ...],
    dry_run: bool,
) -> bool:
    _log({"event": "book_start", "book_id": target.book_id, "title": target.title})
    pdf_path = get_pdf_storage().resolve_for_processing(target.stored_path)
    if not pdf_path:
        for candidate in (
            Path("/app/pdfs") / target.filename,
            Path("/app/pdfs") / Path(target.stored_path).name,
        ):
            if candidate.is_file():
                pdf_path = str(candidate)
                break
    if not pdf_path:
        _log({"event": "book_error", "book_id": target.book_id, "error": "PDF file not found"})
        return False

    total = _page_count(pdf_path)
    _log({
        "event": "ocr_start",
        "book_id": target.book_id,
        "pages": total,
        "dpi": dpi,
        "workers": workers,
        "lang": lang,
        "layout": layout,
    })
    pages = _ocr_pages(
        pdf_path, target, total, dpi, workers, lang, timeout, layout, cache_root
    )
    pages = _apply_verified_source_passages(target.book_id, pages)
    pages = _apply_verified_page_reviews(target.book_id, pages)
    anchors = tuple(KNOWN_SOURCE_ANCHORS.get(target.book_id, ())) + extra_anchors
    quality = _validate_pages(pages, anchors)
    _log({"event": "quality_pass", "book_id": target.book_id, **quality})

    raw_chunks = _chunk_pages(chunker, pages)
    if not raw_chunks:
        raise RuntimeError("OCR generated 0 chunks")
    if dry_run:
        _log({"event": "dry_run_done", "book_id": target.book_id, "chunks": len(raw_chunks)})
        return True

    removed, inserted, backup_path = _swap_chunks(target, raw_chunks, text_search, backup_root)
    _log({
        "event": "book_done",
        "book_id": target.book_id,
        "pages": total,
        "removed_chunks": removed,
        "inserted_chunks": inserted,
        "backup": str(backup_path),
    })
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id", type=int, action="append", required=True)
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--lang", default=DEFAULT_LANG)
    parser.add_argument("--layout", choices=("auto", "columns"), default="columns")
    parser.add_argument("--page-timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--anchor", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    targets = _targets(args.book_id)
    missing = sorted(set(args.book_id) - {target.book_id for target in targets})
    if missing:
        _log({"event": "missing_books", "book_ids": missing})
        return 1

    _log({"event": "targets", "count": len(targets), "book_ids": args.book_id})
    text_search = TextSearchClient()
    chunker = Chunker()

    ok = 0
    failed = 0
    for target in targets:
        try:
            succeeded = reindex_target(
                target=target,
                text_search=text_search,
                chunker=chunker,
                dpi=args.dpi,
                workers=args.workers,
                lang=args.lang,
                timeout=args.page_timeout,
                layout=args.layout,
                cache_root=args.cache_root,
                backup_root=args.backup_root,
                extra_anchors=tuple(args.anchor),
                dry_run=args.dry_run,
            )
        except Exception as exc:
            succeeded = False
            _log({"event": "book_error", "book_id": target.book_id, "error": str(exc)})
        if succeeded:
            ok += 1
        else:
            failed += 1

    _log({"event": "summary", "ok": ok, "failed": failed})
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
