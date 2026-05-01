from __future__ import annotations

import argparse
import os
import time

from models.database import Book, Chunk, SessionLocal
from search.semantic_search import SemanticSearchClient, _get_model
from search.text_search import ES_INDEX, TextSearchClient
from utils.language import normalize_lang


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


def books_to_process(only_processing: bool) -> list[tuple[int, str]]:
    with SessionLocal() as db:
        q = (
            db.query(Book)
            .filter(Book.document_type == "enciclica", Book.source_label == "Vatican.va")
            .order_by(Book.author, Book.title, Book.id)
        )
        if only_processing:
            q = q.filter(Book.ingest_status != "done")
        return [(book.id, f"{book.author} — {book.title}") for book in q.all()]


def complete_book(
    book_id: int,
    semantic_search: SemanticSearchClient,
    text_search: TextSearchClient,
    batch_size: int,
    max_batches: int | None,
    cooldown_seconds: float,
) -> tuple[int, int, int, int]:
    existing_ids = chroma_ids(semantic_search, book_id)
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.id).all()
        missing = [chunk for chunk in chunks if str(chunk.id) not in existing_ids]
        items = [
            (
                str(chunk.id),
                chunk.text,
                {
                    "chunk_id": str(chunk.id),
                    "book_id": book.id,
                    "book_file_id": chunk.book_file_id or 0,
                    "author": book.author,
                    "work_title": book.title,
                    "collection": book.collection or "",
                    "document_type": book.document_type or "",
                    "source_label": book.source_label or "",
                    "pope": book.pope or "",
                    "language": normalize_lang(book.language),
                },
            )
            for chunk in missing
        ]

    if items:
        model = _get_model()
        starts = list(range(0, len(items), batch_size))
        if max_batches is not None:
            starts = starts[:max_batches]
        for idx, start in enumerate(starts, start=1):
            batch = items[start:start + batch_size]
            ids = [chunk_id for chunk_id, _, _ in batch]
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
                f"    Chroma batch {idx}/{len(starts)}: "
                f"{min(start + batch_size, len(items))}/{len(items)} faltantes",
                flush=True,
            )
            if cooldown_seconds > 0 and idx < len(starts):
                time.sleep(cooldown_seconds)

    with SessionLocal() as db:
        book = db.get(Book, book_id)
        db_chunks = db.query(Chunk).filter(Chunk.book_id == book_id).count()
        es_docs = es_count(text_search, book_id)
        chroma_docs = len(chroma_ids(semantic_search, book_id))
        if db_chunks > 0 and es_docs >= db_chunks and chroma_docs >= db_chunks:
            book.ingest_status = "done"
            book.ingest_error = None
        else:
            book.ingest_status = "processing"
            book.ingest_error = f"Parcial: DB={db_chunks}, ES={es_docs}, Chroma={chroma_docs}"
        db.commit()
    return db_chunks, es_docs, chroma_docs, len(items)


def main() -> int:
    parser = argparse.ArgumentParser(description="Completa Chroma para encíclicas Vatican.va.")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-books", type=int, default=0)
    parser.add_argument("--max-batches", type=int, default=None)
    parser.add_argument("--only-processing", action="store_true")
    parser.add_argument("--threads", type=int, default=0, help="Threads de CPU para PyTorch; 0 usa os núcleos disponíveis.")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="auto", help="Dispositivo para embeddings; cuda usa GPU quando disponível.")
    parser.add_argument("--cooldown-seconds", type=float, default=1.0, help="Pausa entre batches para reduzir picos contínuos na GPU.")
    args = parser.parse_args()

    os.environ["VERA_EMBEDDING_DEVICE"] = args.device
    threads = args.threads or (os.cpu_count() or 4)
    os.environ["OMP_NUM_THREADS"] = str(threads)
    os.environ["MKL_NUM_THREADS"] = str(threads)
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        import torch

        torch.set_num_threads(threads)
        torch.set_num_interop_threads(max(1, min(threads, 4)))
    except Exception as exc:  # noqa: BLE001
        print(f"AVISO: não foi possível ajustar threads do torch: {exc}", flush=True)

    targets = books_to_process(only_processing=args.only_processing)
    if args.max_books:
        targets = targets[: args.max_books]

    print(
        f"Processando {len(targets)} encíclica(s) com "
        f"device={args.device}, threads={threads}, batch_size={args.batch_size}, "
        f"cooldown={args.cooldown_seconds}s.",
        flush=True,
    )
    semantic_search = SemanticSearchClient()
    text_search = TextSearchClient()

    for index, (book_id, label) in enumerate(targets, start=1):
        print(f"[{index}/{len(targets)}] book_id={book_id} {label}", flush=True)
        db_chunks, es_docs, chroma_docs, missing = complete_book(
            book_id=book_id,
            semantic_search=semantic_search,
            text_search=text_search,
            batch_size=args.batch_size,
            max_batches=args.max_batches,
            cooldown_seconds=args.cooldown_seconds,
        )
        print(
            f"  DB={db_chunks} ES={es_docs} Chroma={chroma_docs} "
            f"faltavam={missing}",
            flush=True,
        )
        if args.cooldown_seconds > 0 and index < len(targets):
            time.sleep(args.cooldown_seconds)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
