from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
from math import ceil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import func

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import PDFExtractor
from models.database import Book, BookFile, Chunk, SessionLocal, init_db
from search.semantic_search import SemanticSearchClient, _get_model
from search.text_search import ES_INDEX, TextSearchClient

PDF_DIR = Path(__file__).resolve().parents[1] / "pdfs"
AUTHOR = "Santo Agostinho"
CANONICAL_AUTHOR = "Santo Agostinho de Hipona"
EDITOR = "Paulus"
TRANSLATOR = "Paulus Editora"

TARGETS: dict[str, dict] = {
    "vol9_1": {
        "pattern": "*Vol. 9_1*.pdf",
        "volume": 9,
        "title": "Patrística Vol. 9_1 — Comentário aos Salmos (1-50)",
        "canonical_title": "Comentário aos Salmos (1-50)",
    },
    "vol9_2": {
        "pattern": "*Vol. 9_2*.pdf",
        "volume": 9,
        "title": "Patrística Vol. 9_2 — Comentário aos Salmos (51-100)",
        "canonical_title": "Comentário aos Salmos (51-100)",
    },
    "vol9_3": {
        "pattern": "*Vol. 9_3*.pdf",
        "volume": 9,
        "title": "Patrística Vol. 9_3 — Comentário aos Salmos (101-150)",
        "canonical_title": "Comentário aos Salmos (101-150)",
    },
    "vol10": {
        "pattern": "*Vol. 10*.pdf",
        "volume": 10,
        "title": "Patrística Vol. 10 — Confissões",
        "canonical_title": "Confissões",
    },
    "vol11": {
        "pattern": "*Vol. 11*.pdf",
        "volume": 11,
        "title": "Patrística Vol. 11 — Solilóquios; A Vida Feliz",
        "canonical_title": "Solilóquios; A Vida Feliz",
    },
}


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)


def resolve_pdf(pattern: str) -> Path:
    matches = sorted(PDF_DIR.glob(pattern))
    raw_matches = [path for path in matches if not path.name[:1].isdigit()]
    chosen = raw_matches or matches
    if len(chosen) != 1:
        raise RuntimeError(
            f"{pattern}: esperado 1 arquivo, achei {len(chosen)}: "
            f"{[path.name for path in chosen]}"
        )
    return chosen[0]


def count_chunks(db, book_id: int) -> int:
    return db.query(func.count(Chunk.id)).filter(Chunk.book_id == book_id).scalar() or 0


def ensure_book(db, spec: dict) -> Book:
    book = db.query(Book).filter(Book.title == spec["title"]).order_by(Book.id.desc()).first()
    if book is None:
        book = Book(
            collection="PT",
            title=spec["title"],
            author=AUTHOR,
            language="pt",
            edition_label="Paulus",
            source_label="",
            is_primary_source=True,
            library_section="patristica",
            patristic_tradition="portuguesa",
            document_type=None,
            canonical_author=CANONICAL_AUTHOR,
            canonical_title=spec["canonical_title"],
            volume_number=spec["volume"],
            ingest_status="processing",
            ingest_error=None,
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        print(f"CRIADO book_id={book.id} {book.title}", flush=True)
    else:
        book.collection = "PT"
        book.author = AUTHOR
        book.language = "pt"
        book.edition_label = "Paulus"
        book.source_label = book.source_label or ""
        book.is_primary_source = True
        book.library_section = "patristica"
        book.patristic_tradition = "portuguesa"
        book.document_type = None
        book.canonical_author = CANONICAL_AUTHOR
        book.canonical_title = spec["canonical_title"]
        book.volume_number = spec["volume"]
        book.ingest_error = None
        db.commit()
        db.refresh(book)
        print(f"USANDO book_id={book.id} {book.title}", flush=True)
    return book


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
        return text_search.es.count(
            index=ES_INDEX,
            body={"query": {"term": {"book_id": book_id}}},
        ).get("count", 0)
    except Exception:
        return 0


def chroma_ids(semantic_search: SemanticSearchClient, book_id: int) -> set[str]:
    result = semantic_search.collection.get(
        where={"book_id": book_id},
        limit=10000,
        include=["metadatas"],
    )
    return set(result.get("ids", []))


def index_es(book_id: int, text_search: TextSearchClient) -> int:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.id).all()
        items = [(chunk.id, build_es_doc(book, chunk)) for chunk in chunks]
    text_search.index_chunks(items)
    return len(items)


def index_missing_chroma(
    book_id: int,
    semantic_search: SemanticSearchClient,
    batch_size: int,
    max_batches: int | None = None,
) -> tuple[int, int]:
    existing_ids = chroma_ids(semantic_search, book_id)
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.id).all()
        missing = [chunk for chunk in chunks if str(chunk.id) not in existing_ids]
        items = [
            (
                chunk.id,
                chunk.text,
                {
                    "book_id": book_id,
                    "book_file_id": chunk.book_file_id,
                    "author": book.canonical_author or book.author,
                    "work_title": book.title,
                    "chunk_id": str(chunk.id),
                    "language": book.language,
                },
            )
            for chunk in missing
        ]

    if not items:
        return len(existing_ids), 0

    model = _get_model()
    total_batches = ceil(len(items) / batch_size)
    starts = list(range(0, len(items), batch_size))
    if max_batches is not None:
        starts = starts[:max_batches]

    for idx, start in enumerate(starts, start=1):
        batch = items[start : start + batch_size]
        ids = [str(chunk_id) for chunk_id, _, _ in batch]
        texts = [text for _, text, _ in batch]
        metadatas = [metadata for _, _, metadata in batch]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        semantic_search.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        print(
            f"  Chroma batch {idx}/{total_batches}: "
            f"{min(start + batch_size, len(items))}/{len(items)} faltantes",
            flush=True,
        )
    return len(chroma_ids(semantic_search, book_id)), min(len(items), len(starts) * batch_size)


def create_chunks_for_book(book_id: int, spec: dict, source_path: Path) -> int:
    extractor = PDFExtractor()
    chunker = Chunker()

    print(f"EXTRAINDO book_id={book_id}: {source_path.name}", flush=True)
    pages = extractor.extract(str(source_path))
    raw_chunks = chunker.chunk(pages, {"volume_number": spec["volume"]})
    if not raw_chunks:
        raise RuntimeError("Nenhum chunk gerado.")
    print(f"  paginas={len(pages)} chunks={len(raw_chunks)}", flush=True)

    timestamp = int(datetime.datetime.utcnow().timestamp())
    stored_filename = f"{book_id}_{timestamp}_{sanitize_filename(source_path.name)}"
    stored_path = str(PDF_DIR / stored_filename)
    with open(source_path, "rb") as src, open(stored_path, "wb") as dst:
        dst.write(src.read())

    with SessionLocal() as db:
        book = db.get(Book, book_id)
        next_seq = db.query(func.max(Chunk.sequence_index)).filter(Chunk.book_id == book_id).scalar()
        next_seq = (next_seq + 1) if next_seq is not None else 0
        book_file = BookFile(
            book_id=book_id,
            original_filename=source_path.name,
            stored_path=stored_path,
            volume_number=spec["volume"],
            editor=EDITOR,
            translator=TRANSLATOR,
        )
        db.add(book_file)
        db.flush()

        for i, chunk_data in enumerate(raw_chunks):
            db.add(
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
                    chunk_author=CANONICAL_AUTHOR,
                )
            )

        db.commit()
        print(f"  DB ok file_id={book_file.id} chunks={len(raw_chunks)}", flush=True)
    return len(raw_chunks)


def refresh_status(book_id: int, text_search: TextSearchClient, semantic_search: SemanticSearchClient) -> None:
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        db_chunks = count_chunks(db, book_id)
        es_docs = es_count(text_search, book_id)
        chroma_docs = len(chroma_ids(semantic_search, book_id))
        if db_chunks > 0 and es_docs >= db_chunks and chroma_docs >= db_chunks:
            book.ingest_status = "done"
            book.ingest_error = None
        else:
            book.ingest_status = "processing"
            book.ingest_error = f"Parcial: DB={db_chunks}, ES={es_docs}, Chroma={chroma_docs}"
        db.commit()
        print(
            f"STATUS book_id={book_id}: DB={db_chunks} ES={es_docs} "
            f"Chroma={chroma_docs} status={book.ingest_status}",
            flush=True,
        )


def import_target(
    key: str,
    batch_size: int,
    skip_chroma: bool = False,
    max_batches: int | None = None,
) -> int:
    spec = TARGETS[key]
    source_path = resolve_pdf(spec["pattern"])
    text_search = TextSearchClient()
    semantic_search = SemanticSearchClient()

    with SessionLocal() as db:
        book = ensure_book(db, spec)
        book_id = book.id
        if count_chunks(db, book_id) == 0:
            book.ingest_status = "processing"
            book.ingest_error = None
            db.commit()

    with SessionLocal() as db:
        existing_chunks = count_chunks(db, book_id)

    if existing_chunks == 0:
        create_chunks_for_book(book_id, spec, source_path)
    else:
        print(f"DB já tem {existing_chunks} chunks para book_id={book_id}; retomando índices.", flush=True)

    print("  ES indexando/upsert...", flush=True)
    indexed = index_es(book_id, text_search)
    print(f"  ES ok chunks={indexed}", flush=True)

    if skip_chroma:
        print("  Chroma pulado nesta rodada; livro fica como processing até completar embeddings.", flush=True)
        refresh_status(book_id, text_search, semantic_search)
        return book_id

    before = len(chroma_ids(semantic_search, book_id))
    print(f"  Chroma existente={before}; completando faltantes...", flush=True)
    final_count, added = index_missing_chroma(
        book_id,
        semantic_search,
        batch_size=batch_size,
        max_batches=max_batches,
    )
    print(f"  Chroma final={final_count}; adicionados={added}", flush=True)

    refresh_status(book_id, text_search, semantic_search)
    return book_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=TARGETS.keys(), action="append")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--skip-chroma", action="store_true")
    parser.add_argument("--max-batches", type=int, default=None)
    args = parser.parse_args()

    init_db()
    keys = args.only or list(TARGETS.keys())
    for key in keys:
        print("=" * 70, flush=True)
        print(f"IMPORTANDO {key}", flush=True)
        import_target(
            key,
            batch_size=args.batch_size,
            skip_chroma=args.skip_chroma,
            max_batches=args.max_batches,
        )


if __name__ == "__main__":
    main()
