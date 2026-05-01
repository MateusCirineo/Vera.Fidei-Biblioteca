from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from core.config import settings


def copy_collection(source, target, batch_size: int, label: str) -> int:
    total = source.count()
    copied = 0
    start_time = time.time()

    for offset in range(0, total, batch_size):
        batch = source.get(
            limit=batch_size,
            offset=offset,
            include=["embeddings", "documents", "metadatas"],
        )
        ids = batch.get("ids") or []
        if not ids:
            continue
        target.add(
            ids=ids,
            embeddings=batch.get("embeddings"),
            documents=batch.get("documents"),
            metadatas=batch.get("metadatas"),
        )
        copied += len(ids)
        elapsed = max(time.time() - start_time, 0.001)
        rate = copied / elapsed
        print(f"{label}: {copied}/{total} ({rate:.1f}/s)", flush=True)

    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild a Chroma collection in place.")
    parser.add_argument("--collection", default="vera_fidei")
    parser.add_argument("--temp-collection", default="vera_fidei_rebuild_tmp")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    client = chromadb.PersistentClient(path=settings.chroma_path)
    source = client.get_collection(args.collection)
    source_count = source.count()
    print(f"Source {args.collection}: {source_count}", flush=True)

    try:
        client.delete_collection(args.temp_collection)
        print(f"Deleted stale temp collection {args.temp_collection}", flush=True)
    except Exception:
        pass

    temp = client.get_or_create_collection(args.temp_collection)
    copied_to_temp = copy_collection(source, temp, args.batch_size, "old->temp")
    temp_count = temp.count()
    print(f"Temp count: {temp_count}", flush=True)
    if copied_to_temp != source_count or temp_count != source_count:
        raise RuntimeError(f"Temp copy mismatch: source={source_count} copied={copied_to_temp} temp={temp_count}")

    client.delete_collection(args.collection)
    print(f"Deleted old collection {args.collection}", flush=True)
    rebuilt = client.get_or_create_collection(args.collection)
    copied_back = copy_collection(temp, rebuilt, args.batch_size, "temp->new")
    rebuilt_count = rebuilt.count()
    print(f"Rebuilt count: {rebuilt_count}", flush=True)
    if copied_back != source_count or rebuilt_count != source_count:
        raise RuntimeError(f"Rebuild mismatch: source={source_count} copied={copied_back} rebuilt={rebuilt_count}")

    if not args.keep_temp:
        client.delete_collection(args.temp_collection)
        print(f"Deleted temp collection {args.temp_collection}", flush=True)

    print("REBUILD_OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
