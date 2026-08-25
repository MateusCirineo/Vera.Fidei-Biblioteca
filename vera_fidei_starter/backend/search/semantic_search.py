import os
import threading
import importlib.util
from pathlib import Path

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from dataclasses import dataclass

import numpy as np
from sentence_transformers import SentenceTransformer
import torch

from core.config import settings

_model: SentenceTransformer | None = None
_query_model: SentenceTransformer | None = None
_flat_lock = threading.Lock()
_flat_matrix: np.ndarray | None = None
_flat_chunk_ids: np.ndarray | None = None


def _flat_index_dir() -> Path:
    configured = os.environ.get("VERA_FLAT_SEMANTIC_INDEX", "").strip()
    return Path(configured) if configured else Path(settings.chroma_path) / "flat_semantic"


def _get_flat_index() -> tuple[np.ndarray, np.ndarray] | None:
    global _flat_matrix, _flat_chunk_ids
    if _flat_matrix is not None and _flat_chunk_ids is not None:
        return _flat_matrix, _flat_chunk_ids
    with _flat_lock:
        if _flat_matrix is not None and _flat_chunk_ids is not None:
            return _flat_matrix, _flat_chunk_ids
        root = _flat_index_dir()
        matrix_path = root / "embeddings.npy"
        ids_path = root / "chunk_ids.npy"
        if not matrix_path.is_file() or not ids_path.is_file():
            return None
        matrix = np.load(matrix_path, mmap_mode="r", allow_pickle=False)
        chunk_ids = np.load(ids_path, mmap_mode="r", allow_pickle=False)
        if matrix.ndim != 2 or chunk_ids.ndim != 1 or matrix.shape[0] != chunk_ids.shape[0]:
            raise RuntimeError("invalid flat semantic index shape")
        _flat_matrix = matrix
        _flat_chunk_ids = chunk_ids
        return matrix, chunk_ids


def _flat_semantic_query(embedding: np.ndarray, limit: int) -> list[tuple[int, float]] | None:
    loaded = _get_flat_index()
    if loaded is None:
        return None
    matrix, chunk_ids = loaded
    vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if matrix.shape[1] != vector.size:
        raise RuntimeError(
            f"flat semantic dimension mismatch: index={matrix.shape[1]} query={vector.size}"
        )
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return []
    vector = vector / norm
    scores = np.asarray(matrix @ vector, dtype=np.float32)
    take = min(max(0, int(limit)), scores.size)
    if take == 0:
        return []
    if take == scores.size:
        selected = np.argsort(-scores)
    else:
        selected = np.argpartition(scores, -take)[-take:]
        selected = selected[np.argsort(-scores[selected])]
    return [
        (int(chunk_ids[index]), float(scores[index]))
        for index in selected[:take]
    ]


def _resolve_embedding_device() -> str:
    requested = os.environ.get("VERA_EMBEDDING_DEVICE", settings.embedding_device).strip().lower()
    if requested in {"gpu", "cuda"}:
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return "cpu"


def _resolve_index_batch_size(default: int = 8) -> int:
    raw = os.environ.get("VERA_SEMANTIC_INDEX_BATCH_SIZE", str(default)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _chroma_query_fallback_enabled() -> bool:
    explicitly_enabled = os.environ.get("VERA_DISABLE_CHROMA_QUERY_FALLBACK", "").strip().lower() not in {
        "1", "true", "yes", "on",
    }
    return explicitly_enabled and importlib.util.find_spec("chromadb") is not None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        device = _resolve_embedding_device()
        _model = SentenceTransformer(settings.embedding_model, device=device)
    return _model


def _query_model_name() -> str:
    return os.environ.get("VERA_QUERY_EMBEDDING_MODEL", "intfloat/multilingual-e5-small").strip()


def _get_query_model() -> SentenceTransformer:
    global _query_model
    if _query_model is None:
        _query_model = SentenceTransformer(_query_model_name(), device=_resolve_embedding_device())
    return _query_model


def _query_embedding_text(query: str) -> str:
    return f"query: {query}" if "e5" in _query_model_name().casefold() else query


def passage_embedding_text(text: str) -> str:
    return f"passage: {text}" if "e5" in _query_model_name().casefold() else text


@dataclass
class SemanticSearchHit:
    chunk_id: int
    score: float


def _chroma_query_worker(conn, chroma_path: str, collection_name: str, embedding: list, n_results: int) -> None:
    """Runs inside a spawned subprocess. If hnswlib segfaults, only this process dies."""
    try:
        import chromadb as _chroma
        client = _chroma.PersistentClient(path=chroma_path)
        try:
            col = client.get_collection(collection_name)
        except Exception:
            conn.send(None)
            return
        cnt = col.count()
        if cnt == 0:
            conn.send({"metadatas": [[]], "distances": [[]]})
            return
        raw = col.query(
            query_embeddings=embedding,
            n_results=min(n_results, cnt),
            include=["metadatas", "distances"],
        )
        conn.send(raw)
    except Exception:
        conn.send(None)
    finally:
        conn.close()


def _isolated_chroma_query(chroma_path: str, collection_name: str, embedding: list, n_results: int, timeout: float = 12.0) -> dict | None:
    """
    Runs a ChromaDB HNSW query in a separate spawned process.
    If the process segfaults (known hnswlib bug on some kernels), only it dies — uvicorn survives.
    """
    import multiprocessing as _mp
    import logging as _log
    ctx = _mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    p = ctx.Process(target=_chroma_query_worker, args=(child_conn, chroma_path, collection_name, embedding, n_results))
    p.start()
    child_conn.close()
    result = None
    try:
        if parent_conn.poll(timeout):
            result = parent_conn.recv()
        else:
            _log.getLogger(__name__).warning("ChromaDB subprocess timed out after %ss for %s", timeout, collection_name)
    except Exception:
        pass
    finally:
        parent_conn.close()
        if p.is_alive():
            p.terminate()
        p.join(timeout=2)
        if p.exitcode not in (0, None, -15):
            _log.getLogger(__name__).warning("ChromaDB subprocess exited with code %s (likely segfault in hnswlib)", p.exitcode)
    return result


class SemanticSearchClient:
    PRIMARY_COLLECTION_NAME = "vera_fidei"
    DELTA_COLLECTION_NAME = "vera_fidei_delta"

    def __init__(self) -> None:
        self._chroma_path = settings.chroma_path
        self._chroma_client = None
        self.collection = None
        self.delta_collection = None
        if _chroma_query_fallback_enabled():
            self._ensure_chroma_collections()

    def _ensure_chroma_collections(self) -> None:
        if self.collection is not None and self.delta_collection is not None:
            return
        if importlib.util.find_spec("chromadb") is None:
            return
        import chromadb

        client = chromadb.PersistentClient(path=self._chroma_path)
        self._chroma_client = client
        self.collection = client.get_or_create_collection(self.PRIMARY_COLLECTION_NAME)
        self.delta_collection = client.get_or_create_collection(self.DELTA_COLLECTION_NAME)

    def _search_collection_names(self) -> list[str]:
        if os.environ.get("VERA_QUERY_LEGACY_CHROMA", "").strip().lower() in {"1", "true", "yes"}:
            return [self.DELTA_COLLECTION_NAME, self.PRIMARY_COLLECTION_NAME]
        return [self.DELTA_COLLECTION_NAME]

    def search(self, query: str, limit: int = 5, timeout: float = 15.0) -> list[SemanticSearchHit]:
        import logging as _logging
        if not query.strip():
            return []

        # Without an atomic flat index there is nothing safe to query when the
        # legacy Chroma fallback is disabled. Return immediately instead of
        # loading a transformer during a user request (especially on mobile).
        flat_loaded = _get_flat_index()
        if flat_loaded is None and not _chroma_query_fallback_enabled():
            return []

        model = _get_query_model()
        encoded = model.encode([_query_embedding_text(query)], normalize_embeddings=True)
        flat_hits = _flat_semantic_query(encoded[0], limit)
        if flat_hits is not None:
            return [
                SemanticSearchHit(chunk_id=chunk_id, score=max(0.0, min(1.0, score)))
                for chunk_id, score in flat_hits
            ]
        if not _chroma_query_fallback_enabled():
            return []
        embedding = encoded.tolist()

        hits_by_chunk: dict[int, float] = {}
        for name in self._search_collection_names():
            raw = _isolated_chroma_query(self._chroma_path, name, embedding, limit, timeout=timeout - 2)
            if raw is None:
                _logging.getLogger(__name__).warning("ChromaDB query failed/segfaulted for collection %s — skipping", name)
                continue

            metadatas = (raw.get("metadatas") or [[]])[0]
            distances = (raw.get("distances") or [[]])[0]
            for i, meta in enumerate(metadatas):
                if not meta or i >= len(distances):
                    continue
                chunk_id = int(meta["chunk_id"])
                similarity = max(0.0, 1.0 - distances[i])
                hits_by_chunk[chunk_id] = max(hits_by_chunk.get(chunk_id, 0.0), similarity)

        return [
            SemanticSearchHit(chunk_id=chunk_id, score=score)
            for chunk_id, score in sorted(hits_by_chunk.items(), key=lambda item: item[1], reverse=True)[:limit]
        ]

    def index_chunk(self, chunk_id: int, text: str, metadata: dict, language: str = "la") -> None:
        self.index_chunks([(chunk_id, text, metadata)], language=language)

    def index_chunks(
        self,
        items: list[tuple[int, str, dict]],
        language: str = "la",
        batch_size: int | None = None,
    ) -> None:
        if not items:
            return
        if os.environ.get("VERA_SKIP_SEMANTIC_INDEX", "").strip().lower() in {"1", "true", "yes"}:
            return
        self._ensure_chroma_collections()
        if self.collection is None or self.delta_collection is None:
            # Production queries use the atomic flat semantic index. ChromaDB
            # is intentionally absent from the web image until its upstream
            # server-side code-injection advisories have a patched release.
            # New uploads remain immediately available to lexical search and
            # enter the semantic corpus on the next flat-index rebuild.
            return
        model = _get_model()
        batch_size = batch_size or _resolve_index_batch_size()
        for start in range(0, len(items), batch_size):
            batch = items[start:start + batch_size]
            texts = [text for _, text, _ in batch]
            embeddings = model.encode(
                texts,
                batch_size=min(batch_size, len(texts)),
                show_progress_bar=False,
            ).tolist()
            self.delta_collection.add(
                ids=[str(chunk_id) for chunk_id, _, _ in batch],
                embeddings=embeddings,
                documents=texts,
                metadatas=[
                    {**metadata, "chunk_id": str(chunk_id), "language": language}
                    for chunk_id, _, metadata in batch
                ],
            )

    def delete_chunk(self, chunk_id: int) -> None:
        self._ensure_chroma_collections()
        for collection in (self.collection, self.delta_collection):
            try:
                collection.delete(ids=[str(chunk_id)])
            except Exception:
                pass
            try:
                collection.delete(ids=[f"{chunk_id}_translation_pt"])
            except Exception:
                pass

    def index_translation(self, chunk_id: int, text: str, metadata: dict, language: str = "pt") -> None:
        self._ensure_chroma_collections()
        if self.delta_collection is None:
            return
        model = _get_model()
        embedding = model.encode([text]).tolist()
        translation_id = f"{chunk_id}_translation_{language}"
        self.delta_collection.add(
            ids=[translation_id],
            embeddings=embedding,
            documents=[text],
            metadatas=[{**metadata, "chunk_id": str(chunk_id), "language": language, "is_translation": "true"}],
        )
