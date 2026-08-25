"""Validate the public flat semantic index against the authoritative DB set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from models.database import Chunk, SessionLocal
from services.source_fidelity_service import PUBLIC_SOURCE_FIDELITIES


def validate(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    vectors = np.load(root / "embeddings.npy", mmap_mode="r", allow_pickle=False)
    chunk_ids = np.load(root / "chunk_ids.npy", mmap_mode="r", allow_pickle=False)
    if vectors.ndim != 2 or chunk_ids.ndim != 1:
        raise RuntimeError("invalid vector/id rank")
    if vectors.shape[0] != chunk_ids.shape[0]:
        raise RuntimeError("vector/id row mismatch")
    if int(manifest.get("count", -1)) != chunk_ids.shape[0]:
        raise RuntimeError("manifest count mismatch")
    if int(manifest.get("dimension", -1)) != vectors.shape[1]:
        raise RuntimeError("manifest dimension mismatch")
    if chunk_ids.size and not bool(np.all(chunk_ids[1:] > chunk_ids[:-1])):
        raise RuntimeError("chunk IDs must be unique and strictly increasing")
    if not bool(np.isfinite(vectors).all()):
        raise RuntimeError("index contains non-finite embeddings")
    norms = np.linalg.norm(vectors, axis=1)
    if norms.size and (float(norms.min()) < 0.98 or float(norms.max()) > 1.02):
        raise RuntimeError("index embeddings are not normalized")

    with SessionLocal() as db:
        expected = np.asarray([
            int(chunk_id)
            for (chunk_id,) in (
                db.query(Chunk.id)
                .filter(
                    Chunk.source_fidelity.in_(PUBLIC_SOURCE_FIDELITIES),
                    Chunk.text.isnot(None),
                    Chunk.text != "",
                )
                .order_by(Chunk.id)
                .all()
            )
        ], dtype=np.int64)
    if not np.array_equal(expected, np.asarray(chunk_ids)):
        raise RuntimeError("flat index IDs do not equal the current public DB corpus")

    return {
        "status": "ok",
        "count": int(chunk_ids.shape[0]),
        "dimension": int(vectors.shape[1]),
        "embedding_model": manifest.get("embedding_model"),
        "min_norm": round(float(norms.min()), 6) if norms.size else None,
        "max_norm": round(float(norms.max()), 6) if norms.size else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.root), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
