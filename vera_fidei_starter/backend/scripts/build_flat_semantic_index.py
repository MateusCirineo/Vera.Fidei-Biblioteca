"""Build a crash-safe flat vector index from the existing Chroma corpus.

The public search uses this read-only matrix for fast multilingual retrieval.
Only chunks whose source wording is native or visually verified are exported.
The delta collection overrides the legacy collection for repeated chunk IDs.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

from core.config import settings
from models.database import Chunk, SessionLocal
from services.source_fidelity_service import PUBLIC_SOURCE_FIDELITIES
from search.semantic_search import _get_query_model, _query_model_name, passage_embedding_text


DEFAULT_OUTPUT = Path(settings.chroma_path) / "flat_semantic"
COLLECTIONS = ("vera_fidei", "vera_fidei_delta")


def _public_chunk_ids() -> set[int]:
    with SessionLocal() as db:
        return {
            int(chunk_id)
            for (chunk_id,) in (
                db.query(Chunk.id)
                .filter(Chunk.source_fidelity.in_(PUBLIC_SOURCE_FIDELITIES))
                .all()
            )
        }


def _collection_vectors(collection, *, batch_size: int):
    total = collection.count()
    for offset in range(0, total, batch_size):
        payload = collection.get(
            limit=min(batch_size, total - offset),
            offset=offset,
            include=["embeddings", "metadatas"],
        )
        ids = payload.get("ids") or []
        embeddings = payload.get("embeddings")
        if embeddings is None:
            continue
        for raw_id, embedding in zip(ids, embeddings):
            try:
                chunk_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            vector = np.asarray(embedding, dtype=np.float32)
            if vector.ndim == 1 and vector.size:
                yield chunk_id, vector


def build_from_chroma(output: Path, *, batch_size: int) -> dict:
    import chromadb

    allowed = _public_chunk_ids()
    client = chromadb.PersistentClient(path=settings.chroma_path)
    available = {collection.name: collection for collection in client.list_collections()}
    vectors: dict[int, np.ndarray] = {}
    source_counts: dict[str, int] = {}

    for name in COLLECTIONS:
        collection = available.get(name)
        if collection is None:
            continue
        accepted = 0
        for chunk_id, vector in _collection_vectors(collection, batch_size=batch_size):
            if chunk_id not in allowed:
                continue
            vectors[chunk_id] = vector
            accepted += 1
        source_counts[name] = accepted

    if not vectors:
        raise RuntimeError("no public vectors were found in Chroma")

    ordered_ids = np.asarray(sorted(vectors), dtype=np.int64)
    dimension = int(vectors[int(ordered_ids[0])].size)
    if any(vector.size != dimension for vector in vectors.values()):
        raise RuntimeError("mixed embedding dimensions cannot share one flat index")
    matrix = np.stack([vectors[int(chunk_id)] for chunk_id in ordered_ids]).astype(np.float32, copy=False)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.divide(matrix, np.maximum(norms, 1e-12), out=matrix)

    output.mkdir(parents=True, exist_ok=True)
    matrix_tmp = output / "embeddings.npy.tmp"
    ids_tmp = output / "chunk_ids.npy.tmp"
    manifest_tmp = output / "manifest.json.tmp"
    with matrix_tmp.open("wb") as handle:
        np.save(handle, matrix, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    with ids_tmp.open("wb") as handle:
        np.save(handle, ordered_ids, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())

    manifest = {
        "schema_version": 1,
        "embedding_model": settings.embedding_model,
        "count": int(ordered_ids.size),
        "dimension": dimension,
        "source_counts": source_counts,
        "public_fidelities": sorted(PUBLIC_SOURCE_FIDELITIES),
    }
    manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    os.replace(matrix_tmp, output / "embeddings.npy")
    os.replace(ids_tmp, output / "chunk_ids.npy")
    os.replace(manifest_tmp, output / "manifest.json")
    return manifest


def build_from_db(
    output: Path,
    *,
    batch_size: int,
    offset: int = 0,
    limit: int | None = None,
) -> dict:
    model = _get_query_model()
    dimension = int(model.get_sentence_embedding_dimension())
    with SessionLocal() as db:
        query = (
            db.query(Chunk.id, Chunk.text)
            .filter(
                Chunk.source_fidelity.in_(PUBLIC_SOURCE_FIDELITIES),
                Chunk.text.isnot(None),
                Chunk.text != "",
            )
            .order_by(Chunk.id)
        )
        corpus_total = query.count()
        start = min(max(0, int(offset)), corpus_total)
        total = corpus_total - start
        if limit is not None:
            total = min(total, max(0, int(limit)))
        if total <= 0:
            raise RuntimeError("no public source chunks were found in the database")
        query = query.offset(start)
        if limit is not None:
            query = query.limit(total)

        output.mkdir(parents=True, exist_ok=True)
        matrix_tmp = output / "embeddings.npy.tmp"
        ids_tmp = output / "chunk_ids.npy.tmp"
        manifest_tmp = output / "manifest.json.tmp"
        matrix = np.lib.format.open_memmap(
            matrix_tmp,
            mode="w+",
            dtype=np.float32,
            shape=(total, dimension),
        )
        chunk_ids = np.lib.format.open_memmap(
            ids_tmp,
            mode="w+",
            dtype=np.int64,
            shape=(total,),
        )

        written = 0
        batch_ids: list[int] = []
        batch_texts: list[str] = []

        def flush_batch() -> None:
            nonlocal written
            if not batch_ids:
                return
            vectors = model.encode(
                batch_texts,
                batch_size=len(batch_texts),
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            ).astype(np.float32, copy=False)
            end = written + len(batch_ids)
            matrix[written:end] = vectors
            chunk_ids[written:end] = np.asarray(batch_ids, dtype=np.int64)
            written = end
            batch_ids.clear()
            batch_texts.clear()
            if written % max(batch_size * 25, 1) == 0 or written == total:
                print(json.dumps({
                    "event": "flat_index_progress",
                    "completed": written,
                    "total": total,
                }), flush=True)

        for chunk_id, text in query.yield_per(batch_size):
            batch_ids.append(int(chunk_id))
            batch_texts.append(passage_embedding_text(text))
            if len(batch_ids) >= batch_size:
                flush_batch()
        flush_batch()
        if written != total:
            raise RuntimeError(f"flat index row mismatch: expected {total}, wrote {written}")
        matrix.flush()
        chunk_ids.flush()
        del matrix
        del chunk_ids

    manifest = {
        "schema_version": 1,
        "embedding_model": _query_model_name(),
        "count": total,
        "dimension": dimension,
        "source": "postgres_public_chunks",
        "source_offset": start,
        "corpus_total": corpus_total,
        "public_fidelities": sorted(PUBLIC_SOURCE_FIDELITIES),
    }
    manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    os.replace(matrix_tmp, output / "embeddings.npy")
    os.replace(ids_tmp, output / "chunk_ids.npy")
    os.replace(manifest_tmp, output / "manifest.json")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--source", choices=("db", "chroma"), default="db")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.source == "db":
        report = build_from_db(
            args.output,
            batch_size=max(1, args.batch_size),
            offset=max(0, args.offset),
            limit=args.limit,
        )
    else:
        if args.offset or args.limit is not None:
            parser.error("--offset/--limit are supported only with --source db")
        report = build_from_chroma(args.output, batch_size=max(1, args.batch_size))
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
