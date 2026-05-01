from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import PDFExtractor
from models.database import Book, BookFile, Chunk, SessionLocal, init_db
from search.text_search import ES_INDEX, TextSearchClient
from utils.language import normalize_lang


SOURCE_LABEL = "Vatican.va"
LIBRARY_SECTION = "documentos"
DEFAULT_PDF_ROOT = BACKEND_DIR / "pdfs" / "documentos_pontificios"


@dataclass(frozen=True)
class FileTarget:
    file_id: int
    book_id: int
    title: str
    author: str
    pope: str
    document_type: str
    collection: str
    filename: str
    stored_path: str


def language_from_filename(filename: str) -> str:
    match = re.search(r"\s-\s([A-Za-z]{2,4})\.pdf$", filename, flags=re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return "pt"


def register_pdf_files(pdf_root: Path, dry_run: bool, report_every: int) -> dict[str, int]:
    from scripts.import_papal_docs_pdf_files import discover_targets, import_targets

    targets = discover_targets(pdf_root)
    print(f"REGISTER pdf_targets={len(targets)} dry_run={dry_run}", flush=True)
    return import_targets(targets, dry_run=dry_run, report_every=report_every)


def file_targets_without_chunks(limit: int | None) -> list[FileTarget]:
    with SessionLocal() as db:
        query = (
            db.query(BookFile.id)
            .join(Book, BookFile.book_id == Book.id)
            .outerjoin(Chunk, Chunk.book_file_id == BookFile.id)
            .filter(
                Book.library_section == LIBRARY_SECTION,
                Book.source_label == SOURCE_LABEL,
                BookFile.stored_path.like("%documentos_pontificios%"),
            )
            .group_by(BookFile.id)
            .having(func.count(Chunk.id) == 0)
            .order_by(BookFile.id.asc())
        )
        if limit:
            query = query.limit(limit)
        file_ids = [row[0] for row in query.all()]
        if not file_ids:
            return []

        rows = (
            db.query(BookFile, Book)
            .join(Book, BookFile.book_id == Book.id)
            .filter(BookFile.id.in_(file_ids))
            .order_by(BookFile.id.asc())
            .all()
        )

        return [
            FileTarget(
                file_id=book_file.id,
                book_id=book.id,
                title=book.title,
                author=book.author or book.pope or "Vatican.va",
                pope=book.pope or "",
                document_type=book.document_type or "",
                collection=book.collection or "MAG",
                filename=book_file.original_filename,
                stored_path=book_file.stored_path,
            )
            for book_file, book in rows
        ]


def extract_missing_file_chunks(targets: list[FileTarget], dry_run: bool) -> dict[str, int]:
    extractor = PDFExtractor()
    chunker = Chunker()
    stats = {
        "files_seen": len(targets),
        "files_extracted": 0,
        "files_missing": 0,
        "files_short": 0,
        "chunks_created": 0,
        "errors": 0,
    }

    print(f"CHUNK_BACKFILL files_without_chunks={len(targets)} dry_run={dry_run}", flush=True)
    for index, target in enumerate(targets, start=1):
        print(f"[{index}/{len(targets)}] file_id={target.file_id} book_id={target.book_id} {target.title}", flush=True)
        if not os.path.isfile(target.stored_path):
            print(f"  missing_file: {target.stored_path}", flush=True)
            stats["files_missing"] += 1
            if not dry_run:
                with SessionLocal() as db:
                    book = db.get(Book, target.book_id)
                    if book is not None:
                        book.ingest_status = "processing"
                        book.ingest_error = f"BookFile missing: {target.stored_path}"[:1000]
                        db.commit()
            continue

        try:
            pages = extractor.extract(target.stored_path)
            total_chars = sum(len(page.get("text", "")) for page in pages)
            raw_chunks = chunker.chunk(pages, document_meta={}) if total_chars >= 100 else []
            print(f"  pages={len(pages)} chars={total_chars} chunks={len(raw_chunks)}", flush=True)
            if total_chars < 100 or not raw_chunks:
                stats["files_short"] += 1
                continue
            if dry_run:
                stats["chunks_created"] += len(raw_chunks)
                continue

            with SessionLocal() as db:
                book_file = db.get(BookFile, target.file_id)
                if book_file is None:
                    stats["errors"] += 1
                    continue
                existing = db.query(Chunk).filter(Chunk.book_file_id == target.file_id).count()
                if existing:
                    print(f"  already_has_chunks={existing}", flush=True)
                    continue
                for sequence_index, chunk_data in enumerate(raw_chunks):
                    db.add(
                        Chunk(
                            book_id=target.book_id,
                            book_file_id=target.file_id,
                            text=chunk_data["text"],
                            sequence_index=sequence_index,
                            pdf_page=chunk_data.get("pdf_page"),
                            char_offset_start=chunk_data.get("char_offset_start"),
                            char_offset_end=chunk_data.get("char_offset_end"),
                        )
                    )
                book = db.get(Book, target.book_id)
                if book is not None:
                    book.ingest_status = "processing"
                    book.ingest_error = None
                db.commit()

            stats["files_extracted"] += 1
            stats["chunks_created"] += len(raw_chunks)
        except Exception as exc:  # noqa: BLE001
            print(f"  error: {exc}", flush=True)
            stats["errors"] += 1

    return stats


def es_count(text_search: TextSearchClient, book_id: int) -> int:
    try:
        return int(
            text_search.es.count(
                index=ES_INDEX,
                body={"query": {"term": {"book_id": book_id}}},
            ).get("count", 0)
        )
    except Exception:
        return 0


def chroma_collections(semantic_search) -> list:
    collections = [semantic_search.collection]
    delta = getattr(semantic_search, "delta_collection", None)
    if delta is not None and delta is not semantic_search.collection:
        collections.append(delta)
    return collections


def existing_chroma_ids(semantic_search, book_id: int) -> set[str]:
    ids: set[str] = set()
    for collection in chroma_collections(semantic_search):
        try:
            result = collection.get(
                where={"book_id": book_id},
                limit=100000,
                include=["metadatas"],
            )
            ids.update(result.get("ids") or [])
        except Exception:
            continue
    return ids


def chroma_count(semantic_search, book_id: int) -> int:
    return len(existing_chroma_ids(semantic_search, book_id))


def index_chroma_items(semantic_search, items: list[tuple[int, str, dict]], batch_size: int, cooldown_seconds: float) -> int:
    if not items:
        return 0

    from search.semantic_search import _get_model

    model = _get_model()
    collection = getattr(semantic_search, "delta_collection", semantic_search.collection)
    indexed = 0
    total_batches = (len(items) + batch_size - 1) // batch_size
    for batch_num, start in enumerate(range(0, len(items), batch_size), start=1):
        batch = items[start:start + batch_size]
        ids = [str(chunk_id) for chunk_id, _, _ in batch]
        texts = [chunk_text for _, chunk_text, _ in batch]
        metadatas = [metadata for _, _, metadata in batch]
        embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False).tolist()
        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        indexed += len(batch)
        print(f"    Chroma batch {batch_num}/{total_batches}: {indexed}/{len(items)}", flush=True)
        if cooldown_seconds > 0 and batch_num < total_batches:
            time.sleep(cooldown_seconds)
    return indexed


def target_book_ids(limit: int | None) -> list[int]:
    with SessionLocal() as db:
        query = (
            db.query(Book.id)
            .filter(Book.library_section == LIBRARY_SECTION, Book.source_label == SOURCE_LABEL)
            .order_by(Book.document_type.asc(), Book.document_year.asc().nulls_last(), Book.id.asc())
        )
        if limit:
            query = query.limit(limit)
        return [row[0] for row in query.all()]


def book_chunks(book_id: int) -> tuple[Book | None, list[Chunk], int]:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            return None, [], 0
        chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.id.asc()).all()
        missing_files = (
            db.query(BookFile.id)
            .outerjoin(Chunk, Chunk.book_file_id == BookFile.id)
            .filter(BookFile.book_id == book_id)
            .group_by(BookFile.id)
            .having(func.count(Chunk.id) == 0)
            .count()
        )
        db.expunge(book)
        for chunk in chunks:
            db.expunge(chunk)
        return book, chunks, missing_files


def update_book_status(
    book_id: int,
    db_chunks: int,
    missing_files: int,
    es_docs: int,
    chroma_docs: int,
    semantic_enabled: bool,
) -> str:
    if db_chunks <= 0:
        status = "file_only"
        error = "Parcial: nenhum chunk extraido."
    elif missing_files > 0:
        status = "processing"
        error = f"Parcial: {missing_files} BookFile(s) sem chunks; DB={db_chunks}, ES={es_docs}, Chroma={chroma_docs}"
    elif es_docs >= db_chunks and chroma_docs >= db_chunks:
        status = "done"
        error = None
    else:
        status = "processing"
        chroma_label = chroma_docs if semantic_enabled else "pulado"
        error = f"Parcial: DB={db_chunks}, ES={es_docs}, Chroma={chroma_label}"

    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is not None:
            book.ingest_status = status
            book.ingest_error = error
            db.commit()
    return status


def reindex_books(
    book_ids: list[int],
    dry_run: bool,
    no_semantic: bool,
    batch_size: int,
    cooldown_seconds: float,
) -> dict[str, int]:
    text_search = TextSearchClient()
    semantic_search = None
    if not no_semantic:
        from search.semantic_search import SemanticSearchClient

        semantic_search = SemanticSearchClient()

    stats = {
        "books_seen": len(book_ids),
        "books_done": 0,
        "books_processing": 0,
        "es_reindexed": 0,
        "chroma_indexed": 0,
        "zero_chunk_books": 0,
    }

    for index, book_id in enumerate(book_ids, start=1):
        book, chunks, missing_files = book_chunks(book_id)
        if book is None:
            continue
        db_chunks = len(chunks)
        current_es = es_count(text_search, book_id)
        current_chroma = chroma_count(semantic_search, book_id) if semantic_search is not None else 0
        print(
            f"INDEX [{index}/{len(book_ids)}] book_id={book_id} {book.document_type} "
            f"{book.title} DB={db_chunks} ES={current_es} Chroma={current_chroma} missing_files={missing_files}",
            flush=True,
        )

        if db_chunks <= 0:
            stats["zero_chunk_books"] += 1
            if not dry_run:
                status = update_book_status(book_id, db_chunks, missing_files, current_es, current_chroma, semantic_search is not None)
                stats[f"books_{status}"] = stats.get(f"books_{status}", 0) + 1
            continue

        if current_es < db_chunks:
            es_items = [
                (
                    chunk.id,
                    {
                        "book_id": book.id,
                        "book_file_id": chunk.book_file_id,
                        "text": chunk.text,
                        "author": book.author or book.pope or "Vatican.va",
                        "work_title": book.title,
                        "collection": book.collection or "MAG",
                        "language": language_from_filename((chunk.source_file.original_filename if chunk.source_file else "") or ""),
                        "pdf_page": chunk.pdf_page,
                        "edition_label": book.edition_label or "Vatican.va",
                        "chapter_or_section": chunk.chapter_or_section or "",
                        "char_offset_start": chunk.char_offset_start,
                        "char_offset_end": chunk.char_offset_end,
                    },
                )
                for chunk in chunks
            ]
            if not dry_run:
                text_search.index_chunks(es_items)
            stats["es_reindexed"] += len(es_items)
            current_es = db_chunks
            print(f"  ES indexed={len(es_items)}", flush=True)

        if semantic_search is not None:
            existing_ids = existing_chroma_ids(semantic_search, book_id)
            chroma_items = []
            for chunk in chunks:
                if str(chunk.id) in existing_ids:
                    continue
                language = language_from_filename((chunk.source_file.original_filename if chunk.source_file else "") or "")
                chroma_items.append(
                    (
                        chunk.id,
                        chunk.text,
                        {
                            "chunk_id": str(chunk.id),
                            "book_id": book.id,
                            "book_file_id": chunk.book_file_id or 0,
                            "author": book.author or book.pope or "Vatican.va",
                            "work_title": book.title,
                            "collection": book.collection or "MAG",
                            "document_type": book.document_type or "",
                            "source_label": book.source_label or "",
                            "pope": book.pope or "",
                            "language": normalize_lang(language),
                        },
                    )
                )
            if chroma_items:
                print(f"  Chroma missing={len(chroma_items)}", flush=True)
                if not dry_run:
                    indexed = index_chroma_items(semantic_search, chroma_items, batch_size, cooldown_seconds)
                    stats["chroma_indexed"] += indexed
                    current_chroma += indexed
                else:
                    stats["chroma_indexed"] += len(chroma_items)

        if not dry_run:
            final_es = es_count(text_search, book_id)
            final_chroma = chroma_count(semantic_search, book_id) if semantic_search is not None else current_chroma
            status = update_book_status(book_id, db_chunks, missing_files, final_es, final_chroma, semantic_search is not None)
            if status == "done":
                stats["books_done"] += 1
            else:
                stats["books_processing"] += 1

    return stats


def configure_torch(device: str, threads: int) -> None:
    os.environ["VERA_EMBEDDING_DEVICE"] = device
    os.environ["OMP_NUM_THREADS"] = str(threads)
    os.environ["MKL_NUM_THREADS"] = str(threads)
    try:
        import torch

        torch.set_num_threads(threads)
        torch.set_num_interop_threads(max(1, min(threads, 4)))
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
        print(f"Torch {torch.__version__}; cuda={torch.cuda.is_available()}; device={gpu}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN torch config failed: {exc}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume import/index of Vatican.va papal document PDFs.")
    parser.add_argument("--pdf-root", type=Path, default=DEFAULT_PDF_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-register", action="store_true")
    parser.add_argument("--register-only", action="store_true")
    parser.add_argument("--no-semantic", action="store_true")
    parser.add_argument("--limit-files", type=int, default=0)
    parser.add_argument("--limit-books", type=int, default=0)
    parser.add_argument("--report-every", type=int, default=250)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--cooldown-seconds", type=float, default=0.5)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="cuda")
    args = parser.parse_args()

    configure_torch(args.device, args.threads)
    init_db(reset=False)

    if not args.skip_register:
        register_stats = register_pdf_files(args.pdf_root, dry_run=args.dry_run, report_every=args.report_every)
        print("REGISTER_STATS " + " ".join(f"{key}={value}" for key, value in register_stats.items()), flush=True)
        if args.register_only:
            return 0

    targets = file_targets_without_chunks(args.limit_files or None)
    chunk_stats = extract_missing_file_chunks(targets, dry_run=args.dry_run)
    print("CHUNK_STATS " + " ".join(f"{key}={value}" for key, value in chunk_stats.items()), flush=True)

    book_ids = target_book_ids(args.limit_books or None)
    index_stats = reindex_books(
        book_ids=book_ids,
        dry_run=args.dry_run,
        no_semantic=args.no_semantic,
        batch_size=args.batch_size,
        cooldown_seconds=args.cooldown_seconds,
    )
    print("INDEX_STATS " + " ".join(f"{key}={value}" for key, value in index_stats.items()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
