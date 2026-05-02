import os

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from dataclasses import dataclass

import chromadb
from sentence_transformers import SentenceTransformer
import torch

from core.config import settings

_model: SentenceTransformer | None = None


def _resolve_embedding_device() -> str:
    requested = os.environ.get("VERA_EMBEDDING_DEVICE", settings.embedding_device).strip().lower()
    if requested in {"gpu", "cuda"}:
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return "cpu"


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        device = _resolve_embedding_device()
        _model = SentenceTransformer(settings.embedding_model, device=device)
    return _model


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
        client = chromadb.PersistentClient(path=self._chroma_path)
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

        model = _get_model()
        embedding = model.encode([query]).tolist()

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
        batch_size: int = 32,
    ) -> None:
        if not items:
            return
        model = _get_model()
        for start in range(0, len(items), batch_size):
            batch = items[start:start + batch_size]
            texts = [text for _, text, _ in batch]
            embeddings = model.encode(texts).tolist()
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
        model = _get_model()
        embedding = model.encode([text]).tolist()
        translation_id = f"{chunk_id}_translation_{language}"
        self.delta_collection.add(
            ids=[translation_id],
            embeddings=embedding,
            documents=[text],
            metadatas=[{**metadata, "chunk_id": str(chunk_id), "language": language, "is_translation": "true"}],
        )
