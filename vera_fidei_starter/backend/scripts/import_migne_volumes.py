from __future__ import annotations

import argparse
import os
import sys
import time
from math import ceil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import func

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import PDFExtractor
from models.database import Book, BookFile, Chunk, SessionLocal, init_db
from search.semantic_search import SemanticSearchClient, _get_model
from search.text_search import ES_INDEX, TextSearchClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
PDF_DIR = BACKEND_DIR / "pdfs"

TARGETS: dict[str, dict] = {
    "PG002": {
        "filename": "PG002.pdf",
        "collection": "PG",
        "title": "Patrologia Graeca PG002",
        "canonical_title": "Patrologia Graeca Tomus II",
        "author": "Varios Padres Gregos",
        "canonical_author": "Varios Padres Gregos",
        "language": "latim/grego",
        "semantic_language": "grc+la",
        "tradition": "grega",
        "volume": 2,
        "edition_label": "Migne PG",
    },
    "PG003": {
        "filename": "PG003.pdf",
        "collection": "PG",
        "title": "Patrologia Graeca PG003",
        "canonical_title": "Patrologia Graeca Tomus III",
        "author": "Varios Padres Gregos",
        "canonical_author": "Varios Padres Gregos",
        "language": "latim/grego",
        "semantic_language": "grc+la",
        "tradition": "grega",
        "volume": 3,
        "edition_label": "Migne PG",
    },
    "PG004": {
        "filename": "PG004.pdf",
        "collection": "PG",
        "title": "Patrologia Graeca PG004",
        "canonical_title": "Patrologia Graeca Tomus IV",
        "author": "Varios Padres Gregos",
        "canonical_author": "Varios Padres Gregos",
        "language": "latim/grego",
        "semantic_language": "grc+la",
        "tradition": "grega",
        "volume": 4,
        "edition_label": "Migne PG",
    },
    "PG005": {
        "filename": "PG005.pdf",
        "collection": "PG",
        "title": "Patrologia Graeca PG005",
        "canonical_title": "Patrologia Graeca Tomus V",
        "author": "Varios Padres Gregos",
        "canonical_author": "Varios Padres Gregos",
        "language": "latim/grego",
        "semantic_language": "grc+la",
        "tradition": "grega",
        "volume": 5,
        "edition_label": "Migne PG",
    },
    "PL001": {
        "filename": "PL001.pdf",
        "collection": "PL",
        "title": "Patrologia Latina PL001",
        "canonical_title": "Patrologia Latina Tomus I",
        "author": "Varios Padres Latinos",
        "canonical_author": "Varios Padres Latinos",
        "language": "latim",
        "semantic_language": "la",
        "tradition": "latina",
        "volume": 1,
        "edition_label": "Migne PL",
    },
    "PL002": {
        "filename": "PL002.pdf",
        "collection": "PL",
        "title": "Patrologia Latina PL002",
        "canonical_title": "Patrologia Latina Tomus II",
        "author": "Varios Padres Latinos",
        "canonical_author": "Varios Padres Latinos",
        "language": "latim",
        "semantic_language": "la",
        "tradition": "latina",
        "volume": 2,
        "edition_label": "Migne PL",
    },
    "PL003": {
        "filename": "PL003.pdf",
        "collection": "PL",
        "title": "Patrologia Latina PL003",
        "canonical_title": "Patrologia Latina Tomus III",
        "author": "Varios Padres Latinos",
        "canonical_author": "Varios Padres Latinos",
        "language": "latim",
        "semantic_language": "la",
        "tradition": "latina",
        "volume": 3,
        "edition_label": "Migne PL",
    },
    "PL004": {
        "filename": "PL004.pdf",
        "collection": "PL",
        "title": "Patrologia Latina PL004",
        "canonical_title": "Patrologia Latina Tomus IV",
        "author": "Varios Padres Latinos",
        "canonical_author": "Varios Padres Latinos",
        "language": "latim",
        "semantic_language": "la",
        "tradition": "latina",
        "volume": 4,
        "edition_label": "Migne PL",
    },
    "PL005": {
        "filename": "PL005.pdf",
        "collection": "PL",
        "title": "Patrologia Latina PL005",
        "canonical_title": "Patrologia Latina Tomus V",
        "author": "Varios Padres Latinos",
        "canonical_author": "Varios Padres Latinos",
        "language": "latim",
        "semantic_language": "la",
        "tradition": "latina",
        "volume": 5,
        "edition_label": "Migne PL",
    },
}

# PG003 appears to be the only target without useful embedded text in the first
# sample. Process it last so the digital volumes land in the DB first.
DEFAULT_ORDER = ["PG002", "PG004", "PG005", "PL001", "PL002", "PL003", "PL004", "PL005", "PG003"]


def pdf_path(spec: dict) -> Path:
    return PDF_DIR / spec["filename"]


def count_chunks(db, book_id: int) -> int:
    return db.query(func.count(Chunk.id)).filter(Chunk.book_id == book_id).scalar() or 0


def ensure_book(db, spec: dict) -> Book:
    book = db.query(Book).filter(Book.title == spec["title"]).order_by(Book.id.desc()).first()
    if book is None:
        book = Book(
            collection=spec["collection"],
            title=spec["title"],
            author=spec["author"],
            language=spec["language"],
            edition_label=spec["edition_label"],
            source_label="Migne",
            is_primary_source=True,
            library_section="patristica",
            patristic_tradition=spec["tradition"],
            document_type=None,
            canonical_author=spec["canonical_author"],
            canonical_title=spec["canonical_title"],
            volume_number=spec["volume"],
            ingest_status="processing",
            ingest_error=None,
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        print(f"CRIADO book_id={book.id} {book.title}", flush=True)
        return book

    book.collection = spec["collection"]
    book.author = spec["author"]
    book.language = spec["language"]
    book.edition_label = spec["edition_label"]
    book.source_label = book.source_label or "Migne"
    book.is_primary_source = True
    book.library_section = "patristica"
    book.patristic_tradition = spec["tradition"]
    book.document_type = None
    book.canonical_author = spec["canonical_author"]
    book.canonical_title = spec["canonical_title"]
    book.volume_number = spec["volume"]
    book.ingest_error = None
    db.commit()
    db.refresh(book)
    print(f"USANDO book_id={book.id} {book.title}", flush=True)
    return book


def ensure_book_file(db, book_id: int, spec: dict, source_path: Path) -> BookFile:
    stored_path = str(source_path.resolve())
    book_file = (
        db.query(BookFile)
        .filter(BookFile.book_id == book_id, BookFile.stored_path == stored_path)
        .order_by(BookFile.id.desc())
        .first()
    )
    if book_file is not None:
        return book_file

    book_file = BookFile(
        book_id=book_id,
        original_filename=source_path.name,
        stored_path=stored_path,
        volume_number=spec["volume"],
        editor="Jacques-Paul Migne",
        translator=None,
    )
    db.add(book_file)
    db.commit()
    db.refresh(book_file)
    return book_file


def build_es_doc(book: Book, chunk: Chunk) -> dict:
    return {
        "book_id": book.id,
        "book_file_id": chunk.book_file_id,
        "text": chunk.text,
        "author": book.canonical_author or book.author,
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


def es_count(text_search: TextSearchClient, book_id: int) -> int:
    try:
        return int(text_search.es.count(index=ES_INDEX, body={"query": {"term": {"book_id": book_id}}}).get("count", 0))
    except Exception:
        return 0


def chroma_delta_ids(semantic_search: SemanticSearchClient, book_id: int) -> set[str]:
    try:
        result = semantic_search.delta_collection.get(
            where={"book_id": book_id},
            limit=100000,
            include=["metadatas"],
        )
        return set(result.get("ids", []))
    except Exception:
        return set()


def create_chunks_if_missing(book_id: int, spec: dict, source_path: Path) -> int:
    extractor = PDFExtractor()
    chunker = Chunker()

    with SessionLocal() as db:
        existing = count_chunks(db, book_id)
        book = db.get(Book, book_id)
        book.ingest_status = "processing"
        book.ingest_error = None
        book_file = ensure_book_file(db, book_id, spec, source_path)
        book_file_id = book_file.id
        db.commit()

    if existing > 0:
        print(f"  DB ja tem {existing} chunks; pulando extracao.", flush=True)
        return existing

    print(f"  Extraindo texto: {source_path.name}", flush=True)
    pages = extractor.extract(str(source_path))
    raw_chunks = chunker.chunk(pages, {"volume_number": spec["volume"]})
    if not raw_chunks:
        raise RuntimeError("Nenhum chunk gerado pelo extrator.")

    with SessionLocal() as db:
        book_file = db.get(BookFile, book_file_id)
        next_seq = db.query(func.max(Chunk.sequence_index)).filter(Chunk.book_id == book_id).scalar()
        next_seq = (next_seq + 1) if next_seq is not None else 0
        records = []
        for i, chunk_data in enumerate(raw_chunks):
            records.append(
                Chunk(
                    book_id=book_id,
                    book_file_id=book_file.id,
                    text=chunk_data["text"],
                    sequence_index=next_seq + i,
                    volume=chunk_data.get("volume_number"),
                    column_start=chunk_data.get("column_start"),
                    column_end=chunk_data.get("column_end"),
                    pdf_page=chunk_data.get("pdf_page"),
                    char_offset_start=chunk_data.get("char_offset_start"),
                    char_offset_end=chunk_data.get("char_offset_end"),
                    visual_anchor=f"col{chunk_data.get('column_start', '')}",
                    chapter_or_section=chunk_data.get("chapter_or_section", ""),
                    chunk_author=spec["canonical_author"],
                )
            )
        db.add_all(records)
        db.commit()

    print(f"  DB ok: paginas={len(pages)} chunks={len(raw_chunks)}", flush=True)
    return len(raw_chunks)


def index_es(book_id: int, text_search: TextSearchClient) -> int:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.id).all()
        items = [(chunk.id, build_es_doc(book, chunk)) for chunk in chunks]
    text_search.index_chunks(items)
    return len(items)


def index_missing_chroma(
    book_id: int,
    spec: dict,
    semantic_search: SemanticSearchClient,
    batch_size: int,
    cooldown_seconds: float,
) -> tuple[int, int]:
    existing = chroma_delta_ids(semantic_search, book_id)
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.id).all()
        missing = [chunk for chunk in chunks if str(chunk.id) not in existing]
        items = [
            (
                chunk.id,
                chunk.text,
                {
                    "book_id": book_id,
                    "book_file_id": chunk.book_file_id or 0,
                    "author": book.canonical_author or book.author,
                    "work_title": book.title,
                    "chunk_id": str(chunk.id),
                    "collection": book.collection,
                    "volume": chunk.volume or spec["volume"],
                    "language": spec["semantic_language"],
                    "source_label": "Migne",
                },
            )
            for chunk in missing
        ]

    if not items:
        return len(existing), 0

    model = _get_model()
    total_batches = ceil(len(items) / batch_size)
    indexed = 0
    for batch_num, start in enumerate(range(0, len(items), batch_size), start=1):
        batch = items[start:start + batch_size]
        ids = [str(chunk_id) for chunk_id, _, _ in batch]
        texts = [text for _, text, _ in batch]
        metadatas = [metadata for _, _, metadata in batch]
        embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False).tolist()
        semantic_search.delta_collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        indexed += len(batch)
        print(f"  Chroma delta batch {batch_num}/{total_batches}: {indexed}/{len(items)}", flush=True)
        if cooldown_seconds > 0 and batch_num < total_batches:
            time.sleep(cooldown_seconds)

    return len(chroma_delta_ids(semantic_search, book_id)), indexed


def refresh_status(book_id: int, text_search: TextSearchClient, semantic_search: SemanticSearchClient) -> tuple[int, int, int, str]:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        db_chunks = count_chunks(db, book_id)
        es_docs = es_count(text_search, book_id)
        chroma_docs = len(chroma_delta_ids(semantic_search, book_id))
        if db_chunks > 0 and es_docs >= db_chunks and chroma_docs >= db_chunks:
            book.ingest_status = "done"
            book.ingest_error = None
        else:
            book.ingest_status = "processing"
            book.ingest_error = f"Parcial: DB={db_chunks}, ES={es_docs}, ChromaDelta={chroma_docs}"
        status = book.ingest_status
        db.commit()
        return db_chunks, es_docs, chroma_docs, status


def import_target(key: str, batch_size: int, cooldown_seconds: float, skip_chroma: bool = False) -> None:
    spec = TARGETS[key]
    source_path = pdf_path(spec)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    if source_path.stat().st_size == 0:
        raise RuntimeError(f"Arquivo zerado: {source_path}")

    text_search = TextSearchClient()
    semantic_search = SemanticSearchClient()

    with SessionLocal() as db:
        book = ensure_book(db, spec)
        book_id = book.id

    create_chunks_if_missing(book_id, spec, source_path)

    print("  ES indexando/upsert...", flush=True)
    es_indexed = index_es(book_id, text_search)
    print(f"  ES ok: {es_indexed}", flush=True)

    if skip_chroma:
        print("  Chroma pulado nesta rodada.", flush=True)
    else:
        before = len(chroma_delta_ids(semantic_search, book_id))
        print(f"  Chroma delta existente={before}; completando faltantes...", flush=True)
        final_count, added = index_missing_chroma(book_id, spec, semantic_search, batch_size, cooldown_seconds)
        print(f"  Chroma delta final={final_count}; adicionados={added}", flush=True)

    db_chunks, es_docs, chroma_docs, status = refresh_status(book_id, text_search, semantic_search)
    print(f"  STATUS {status}: DB={db_chunks} ES={es_docs} ChromaDelta={chroma_docs}", flush=True)


def report(keys: list[str]) -> None:
    text_search = TextSearchClient()
    semantic_search = SemanticSearchClient()
    with SessionLocal() as db:
        print("\nRELATORIO MIGNE")
        for key in keys:
            spec = TARGETS[key]
            book = db.query(Book).filter(Book.title == spec["title"]).order_by(Book.id.desc()).first()
            if book is None:
                print(f"  {key}: ausente")
                continue
            files = db.query(BookFile).filter(BookFile.book_id == book.id).count()
            chunks = count_chunks(db, book.id)
            es_docs = es_count(text_search, book.id)
            chroma_docs = len(chroma_delta_ids(semantic_search, book.id))
            print(
                f"  {key} id={book.id} files={files} chunks={chunks} "
                f"ES={es_docs} ChromaDelta={chroma_docs} status={book.ingest_status}",
                flush=True,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa volumes Migne PG/PL colocados em backend/pdfs.")
    parser.add_argument("--only", action="append", choices=TARGETS.keys())
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--cooldown-seconds", type=float, default=1.0)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="cuda")
    parser.add_argument("--skip-chroma", action="store_true")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    os.environ["VERA_EMBEDDING_DEVICE"] = args.device
    os.environ["OMP_NUM_THREADS"] = str(args.threads)
    os.environ["MKL_NUM_THREADS"] = str(args.threads)
    try:
        import torch

        torch.set_num_threads(args.threads)
        torch.set_num_interop_threads(max(1, min(args.threads, 4)))
        print(
            f"Torch {torch.__version__}; cuda={torch.cuda.is_available()}; "
            f"device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'}",
            flush=True,
        )
    except Exception as exc:
        print(f"AVISO: nao foi possivel configurar torch: {exc}", flush=True)

    init_db()
    keys = args.only or DEFAULT_ORDER
    if args.status_only:
        report(keys)
        return 0

    errors = 0
    for idx, key in enumerate(keys, start=1):
        print("=" * 72, flush=True)
        print(f"IMPORTANDO [{idx}/{len(keys)}] {key}", flush=True)
        try:
            import_target(key, batch_size=args.batch_size, cooldown_seconds=args.cooldown_seconds, skip_chroma=args.skip_chroma)
        except Exception as exc:
            errors += 1
            print(f"ERRO {key}: {exc}", flush=True)
            with SessionLocal() as db:
                spec = TARGETS[key]
                book = db.query(Book).filter(Book.title == spec["title"]).order_by(Book.id.desc()).first()
                if book is not None:
                    book.ingest_status = "error"
                    book.ingest_error = str(exc)[:1000]
                    db.commit()

    report(keys)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
