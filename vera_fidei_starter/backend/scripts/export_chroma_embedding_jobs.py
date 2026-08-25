from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.database import Book, Chunk, SessionLocal
from search.semantic_search import SemanticSearchClient


def _clean_meta(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _metadata(book: Book, chunk: Chunk) -> dict:
    raw = {
        "book_id": book.id,
        "book_file_id": chunk.book_file_id,
        "author": chunk.chunk_author or book.canonical_author or book.author,
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
        "source_label": book.source_label,
    }
    return {key: cleaned for key, value in raw.items() if (cleaned := _clean_meta(value)) is not None}


def _existing_delta_ids(semantic: SemanticSearchClient, book_id: int) -> set[int]:
    try:
        result = semantic.delta_collection.get(where={"book_id": book_id}, include=["metadatas"])
    except Exception:
        return set()
    ids: set[int] = set()
    for item in result.get("ids") or []:
        try:
            ids.add(int(str(item).split("_", 1)[0]))
        except ValueError:
            continue
    for meta in result.get("metadatas") or []:
        if not meta:
            continue
        raw = meta.get("chunk_id")
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    return ids


def _parse_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in raw.replace(",", " ").split():
        if "-" in part:
            start, end = part.split("-", 1)
            ids.extend(range(int(start), int(end) + 1))
        else:
            ids.append(int(part))
    return sorted(set(ids))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-ids", required=True, help="Ex.: 2136-2147,2149-2159")
    parser.add_argument("--output", required=True)
    parser.add_argument("--include-existing", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    book_ids = _parse_ids(args.book_ids)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    semantic = SemanticSearchClient()
    exported = 0
    with SessionLocal() as db, gzip.open(output, "wt", encoding="utf-8") as fh:
        for book_id in book_ids:
            book = db.get(Book, book_id)
            if book is None:
                print(f"missing book_id={book_id}", flush=True)
                continue
            existing = set() if args.include_existing else _existing_delta_ids(semantic, book_id)
            query = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.sequence_index.asc(), Chunk.id.asc())
            book_exported = 0
            for chunk in query:
                if chunk.id in existing or not (chunk.text or "").strip():
                    continue
                payload = {
                    "chunk_id": chunk.id,
                    "text": chunk.text,
                    "language": book.language or "unknown",
                    "metadata": _metadata(book, chunk),
                }
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
                exported += 1
                book_exported += 1
                if args.limit and exported >= args.limit:
                    break
            print(f"book_id={book_id} exported={book_exported} existing={len(existing)} title={book.title}", flush=True)
            if args.limit and exported >= args.limit:
                break

    print(f"exported_total={exported} output={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
