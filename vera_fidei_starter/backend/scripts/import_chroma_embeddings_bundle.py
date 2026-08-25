from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.database import Book, Chunk, SessionLocal
from search.semantic_search import SemanticSearchClient
from search.text_search import ES_INDEX, TextSearchClient


def _clean_metadata(metadata: dict, chunk_id: int, language: str) -> dict:
    cleaned = {}
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    cleaned["chunk_id"] = str(chunk_id)
    cleaned["language"] = language
    return cleaned


def _open_text(path: Path):
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open("rt", encoding="utf-8")


def _bundle_paths(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.glob("*.jsonl.gz") if not p.name.endswith(".tmp"))
    return [path]


def _read_bundle(path: Path):
    with _open_text(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _chroma_count(semantic: SemanticSearchClient, book_id: int) -> int:
    try:
        result = semantic.delta_collection.get(where={"book_id": book_id}, include=["metadatas"])
    except Exception:
        return 0
    return len(result.get("ids") or [])


def _update_status(book_ids: set[int], semantic: SemanticSearchClient, text_search: TextSearchClient) -> None:
    with SessionLocal() as db:
        for book_id in sorted(book_ids):
            book = db.get(Book, book_id)
            if not book:
                continue
            db_chunks = db.query(Chunk).filter(Chunk.book_id == book_id).count()
            try:
                es_docs = int(text_search.es.count(index=ES_INDEX, body={"query": {"term": {"book_id": book_id}}}).get("count", 0))
            except Exception:
                es_docs = 0
            chroma_docs = _chroma_count(semantic, book_id)
            if db_chunks > 0 and es_docs >= db_chunks and chroma_docs >= db_chunks:
                book.ingest_status = "done"
                book.ingest_error = None
            else:
                book.ingest_status = "processing"
                book.ingest_error = f"Parcial: DB={db_chunks}, ES={es_docs}, ChromaDelta={chroma_docs}"
            print(f"status book_id={book_id} DB={db_chunks} ES={es_docs} ChromaDelta={chroma_docs} status={book.ingest_status}", flush=True)
        db.commit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    semantic = SemanticSearchClient()
    text_search = TextSearchClient()
    imported = 0
    book_ids: set[int] = set()
    batch: list[dict] = []

    def flush() -> None:
        nonlocal imported, batch
        if not batch:
            return
        ids = [str(item["chunk_id"]) for item in batch]
        documents = [item["text"] for item in batch]
        embeddings = [item["embedding"] for item in batch]
        metadatas = [
            _clean_metadata(item.get("metadata") or {}, int(item["chunk_id"]), item.get("language") or "unknown")
            for item in batch
        ]
        if not args.dry_run:
            semantic.delta_collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        imported += len(batch)
        print(f"imported={imported}", flush=True)
        batch = []

    for bundle_path in _bundle_paths(Path(args.input)):
        print(f"reading={bundle_path}", flush=True)
        for item in _read_bundle(bundle_path):
            metadata = item.get("metadata") or {}
            if metadata.get("book_id") is not None:
                book_ids.add(int(metadata["book_id"]))
            batch.append(item)
            if len(batch) >= args.batch_size:
                flush()
    flush()

    if not args.dry_run:
        _update_status(book_ids, semantic, text_search)
    print(f"imported_total={imported}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
