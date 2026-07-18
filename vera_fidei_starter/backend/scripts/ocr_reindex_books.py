"""
OCR reindex selected already-uploaded books with full page extraction.

This is for PDFs whose embedded text layer is incomplete. It clears old chunks
and search docs, OCRs every page, rebuilds chunks, indexes Elasticsearch, and
marks the book done only after the full text pass succeeds.

Run inside the backend container from /app:
  python -m scripts.ocr_reindex_books --book-id 2109 --book-id 2110
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone

import pdf2image
import pdfplumber
from sqlalchemy import func

sys.path.insert(0, "/app")

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import POPPLER_PATH, TESSDATA_DIR
from models.database import Book, BookFile, Chunk, SessionLocal, Translation
from search.semantic_search import SemanticSearchClient
from search.text_search import TextSearchClient
from storage.pdf_storage import get_pdf_storage


TESSERACT_BIN = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract") or "tesseract"
DEFAULT_LANG = os.environ.get("VERA_FAST_OCR_LANG", "por+lat+eng")
DEFAULT_DPI = int(os.environ.get("VERA_FAST_OCR_DPI", "120"))
DEFAULT_WORKERS = int(os.environ.get("VERA_FAST_OCR_WORKERS", "4"))
DEFAULT_TIMEOUT = int(os.environ.get("VERA_FAST_OCR_PAGE_TIMEOUT", "75"))


@dataclass(frozen=True)
class BookTarget:
    book_id: int
    title: str
    author: str
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
                language=book.language,
                file_id=file.id,
                filename=file.original_filename,
                stored_path=file.stored_path,
            )
            for book, file in rows
        ]


def _set_status(book_id: int, status: str, error: str | None = None) -> None:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is not None:
            book.ingest_status = status
            book.ingest_error = error
            db.commit()


def _clear_book(book_id: int, text_search: TextSearchClient, semantic_search: SemanticSearchClient) -> int:
    with SessionLocal() as db:
        chunk_ids = [row[0] for row in db.query(Chunk.id).filter(Chunk.book_id == book_id).all()]

    for chunk_id in chunk_ids:
        text_search.delete_chunk(int(chunk_id))
        semantic_search.delete_chunk(int(chunk_id))

    if not chunk_ids:
        _set_status(book_id, "file_only", None)
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


def _page_count(pdf_path: str) -> int:
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)


def _convert_page(pdf_path: str, page_num: int, dpi: int) -> str:
    temp_dir = tempfile.mkdtemp(prefix=f"vf_fast_ocr_{page_num}_")
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
        )
        if not paths:
            raise RuntimeError("pdf2image returned no image")
        return paths[0]
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def _cleanup_image(image_path: str) -> None:
    temp_dir = os.path.dirname(image_path)
    shutil.rmtree(temp_dir, ignore_errors=True)


def _ocr_image(image_path: str, lang: str, timeout: int) -> str:
    env = os.environ.copy()
    env.setdefault("OMP_THREAD_LIMIT", "1")
    cmd = [
        TESSERACT_BIN,
        image_path,
        "stdout",
        "-l",
        lang,
        "--tessdata-dir",
        TESSDATA_DIR,
        "--oem",
        "1",
        "--psm",
        "6",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        check=False,
    )
    return result.stdout or ""


def _ocr_page(pdf_path: str, page_num: int, dpi: int, lang: str, timeout: int) -> dict:
    image_path = _convert_page(pdf_path, page_num, dpi)
    try:
        text = _ocr_image(image_path, lang, timeout)
        if len(text.strip()) < 20:
            # Page segmentation 3 is slower, but helps with title pages and complex layouts.
            env = os.environ.copy()
            env.setdefault("OMP_THREAD_LIMIT", "1")
            result = subprocess.run(
                [
                    TESSERACT_BIN,
                    image_path,
                    "stdout",
                    "-l",
                    lang,
                    "--tessdata-dir",
                    TESSDATA_DIR,
                    "--oem",
                    "1",
                    "--psm",
                    "3",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
                check=False,
            )
            fallback = result.stdout or ""
            if len(fallback.strip()) > len(text.strip()):
                text = fallback
        return {"page_number": page_num, "text": text}
    finally:
        _cleanup_image(image_path)


def _ocr_pages(pdf_path: str, page_total: int, dpi: int, workers: int, lang: str, timeout: int) -> list[dict]:
    pages: dict[int, str] = {}
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_ocr_page, pdf_path, page_num, dpi, lang, timeout): page_num
            for page_num in range(1, page_total + 1)
        }
        for future in as_completed(futures):
            page_num = futures[future]
            try:
                page = future.result()
                text = page["text"]
            except Exception as exc:
                text = ""
                _log({"event": "page_error", "page": page_num, "error": str(exc)})
            pages[page_num] = text
            completed += 1
            if completed == 1 or completed % 10 == 0 or completed == page_total:
                _log({
                    "event": "ocr_progress",
                    "completed": completed,
                    "total": page_total,
                    "last_page": page_num,
                    "chars": len(text.strip()),
                })

    return [
        {"page_number": page_num, "text": pages.get(page_num, "")}
        for page_num in range(1, page_total + 1)
    ]


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
    }


def _insert_chunks(book_id: int, file_id: int, raw_chunks: list[dict]) -> list[tuple[int, dict]]:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            return []
        inserted: list[Chunk] = []
        for index, chunk_data in enumerate(raw_chunks):
            chunk = Chunk(
                book_id=book_id,
                book_file_id=file_id,
                text=chunk_data["text"],
                sequence_index=index,
                volume=chunk_data.get("volume_number"),
                column_start=chunk_data.get("column_start"),
                column_end=chunk_data.get("column_end"),
                pdf_page=chunk_data.get("pdf_page"),
                char_offset_start=chunk_data.get("char_offset_start"),
                char_offset_end=chunk_data.get("char_offset_end"),
                visual_anchor=f"col{chunk_data.get('column_start', '')}",
                chapter_or_section=chunk_data.get("chapter_or_section", ""),
            )
            db.add(chunk)
            inserted.append(chunk)
        db.flush()
        items = [(chunk.id, _es_doc(book, chunk)) for chunk in inserted if chunk.id is not None]
        db.commit()
        return items


def reindex_target(
    target: BookTarget,
    text_search: TextSearchClient,
    semantic_search: SemanticSearchClient,
    chunker: Chunker,
    dpi: int,
    workers: int,
    lang: str,
    timeout: int,
) -> bool:
    _log({"event": "book_start", "book_id": target.book_id, "title": target.title})
    removed = _clear_book(target.book_id, text_search, semantic_search)
    _log({"event": "chunks_cleared", "book_id": target.book_id, "removed": removed})

    pdf_path = get_pdf_storage().resolve_for_processing(target.stored_path)
    if not pdf_path:
        _set_status(target.book_id, "error", f"PDF file not found: {target.stored_path}")
        return False

    total = _page_count(pdf_path)
    _log({
        "event": "ocr_start",
        "book_id": target.book_id,
        "pages": total,
        "dpi": dpi,
        "workers": workers,
        "lang": lang,
    })
    pages = _ocr_pages(pdf_path, total, dpi, workers, lang, timeout)
    raw_chunks = chunker.chunk(pages, {})
    if not raw_chunks:
        _set_status(target.book_id, "error", "OCR generated 0 chunks.")
        _log({"event": "book_error", "book_id": target.book_id, "error": "OCR generated 0 chunks."})
        return False

    items = _insert_chunks(target.book_id, target.file_id, raw_chunks)
    text_search.index_chunks(items)
    _set_status(target.book_id, "done", None)
    _log({
        "event": "book_done",
        "book_id": target.book_id,
        "pages": total,
        "chunks": len(items),
    })
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id", type=int, action="append", required=True)
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--lang", default=DEFAULT_LANG)
    parser.add_argument("--page-timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    targets = _targets(args.book_id)
    _log({"event": "targets", "count": len(targets), "book_ids": args.book_id})

    text_search = TextSearchClient()
    semantic_search = SemanticSearchClient()
    chunker = Chunker()

    ok = 0
    failed = 0
    for target in targets:
        if reindex_target(
            target,
            text_search,
            semantic_search,
            chunker,
            args.dpi,
            args.workers,
            args.lang,
            args.page_timeout,
        ):
            ok += 1
        else:
            failed += 1

    _log({"event": "summary", "ok": ok, "failed": failed})
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
