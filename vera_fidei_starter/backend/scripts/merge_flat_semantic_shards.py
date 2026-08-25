"""Atomically merge a completed prefix and tail semantic-index shard."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np


def _load(path: Path) -> np.ndarray:
    return np.load(path, mmap_mode="r", allow_pickle=False)


def merge(*, head: Path, head_count: int, tail: Path, output: Path) -> dict:
    if head_count <= 0:
        raise ValueError("head_count must be positive")
    head_vectors = _load(head / "embeddings.npy.tmp")
    head_ids = _load(head / "chunk_ids.npy.tmp")
    tail_vectors = _load(tail / "embeddings.npy")
    tail_ids = _load(tail / "chunk_ids.npy")
    if head_vectors.ndim != 2 or tail_vectors.ndim != 2:
        raise RuntimeError("both embedding shards must be matrices")
    if head_vectors.shape[1] != tail_vectors.shape[1]:
        raise RuntimeError("embedding shard dimensions differ")
    if head_count > head_vectors.shape[0] or head_count > head_ids.shape[0]:
        raise RuntimeError("head shard is shorter than head_count")
    if tail_vectors.shape[0] != tail_ids.shape[0]:
        raise RuntimeError("tail shard vector/id counts differ")

    selected_head_ids = np.asarray(head_ids[:head_count], dtype=np.int64)
    if selected_head_ids.size and tail_ids.size and selected_head_ids[-1] >= tail_ids[0]:
        raise RuntimeError("semantic shards overlap or are out of order")

    total = head_count + int(tail_ids.shape[0])
    dimension = int(head_vectors.shape[1])
    output.mkdir(parents=True, exist_ok=True)
    matrix_tmp = output / "embeddings.npy.merge.tmp"
    ids_tmp = output / "chunk_ids.npy.merge.tmp"
    manifest_tmp = output / "manifest.json.merge.tmp"
    matrix = np.lib.format.open_memmap(
        matrix_tmp, mode="w+", dtype=np.float32, shape=(total, dimension),
    )
    ids = np.lib.format.open_memmap(
        ids_tmp, mode="w+", dtype=np.int64, shape=(total,),
    )
    matrix[:head_count] = head_vectors[:head_count]
    matrix[head_count:] = tail_vectors
    ids[:head_count] = selected_head_ids
    ids[head_count:] = tail_ids
    matrix.flush()
    ids.flush()
    del matrix
    del ids

    tail_manifest = json.loads((tail / "manifest.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": 1,
        "embedding_model": tail_manifest["embedding_model"],
        "count": total,
        "dimension": dimension,
        "source": "postgres_public_chunks",
        "source_offset": 0,
        "corpus_total": tail_manifest.get("corpus_total", total),
        "public_fidelities": tail_manifest.get("public_fidelities", []),
        "merged_head_count": head_count,
    }
    manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    os.replace(matrix_tmp, output / "embeddings.npy")
    os.replace(ids_tmp, output / "chunk_ids.npy")
    os.replace(manifest_tmp, output / "manifest.json")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", type=Path, required=True)
    parser.add_argument("--head-count", type=int, required=True)
    parser.add_argument("--tail", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(merge(
        head=args.head,
        head_count=args.head_count,
        tail=args.tail,
        output=args.output,
    ), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
