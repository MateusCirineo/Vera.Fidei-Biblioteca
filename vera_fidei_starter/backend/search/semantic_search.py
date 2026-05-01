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


class SemanticSearchClient:
    PRIMARY_COLLECTION_NAME = "vera_fidei"
    DELTA_COLLECTION_NAME = "vera_fidei_delta"

    def __init__(self) -> None:
        client = chromadb.PersistentClient(path=settings.chroma_path)
        self.collection = client.get_or_create_collection(self.PRIMARY_COLLECTION_NAME)
        self.delta_collection = client.get_or_create_collection(self.DELTA_COLLECTION_NAME)

    def _search_collections(self) -> tuple:
        if os.environ.get("VERA_QUERY_LEGACY_CHROMA", "").strip().lower() in {"1", "true", "yes"}:
            return (self.delta_collection, self.collection)
        return (self.delta_collection,)

    def search(self, query: str, limit: int = 5, timeout: float = 15.0) -> list[SemanticSearchHit]:
        import concurrent.futures
        import logging as _logging
        if not query.strip():
            return []

        model = _get_model()
        embedding = model.encode([query]).tolist()

        hits_by_chunk: dict[int, float] = {}
        for collection in self._search_collections():
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                future = executor.submit(
                    collection.query,
                    query_embeddings=embedding,
                    n_results=limit,
                    include=["metadatas", "distances"],
                )
                try:
                    raw = future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    _logging.getLogger(__name__).warning(
                        "ChromaDB query timed out after %ss (HNSW index may be rebuilding)",
                        timeout,
                    )
                    executor.shutdown(wait=False)
                    continue
            except Exception:
                executor.shutdown(wait=False)
                continue
            executor.shutdown(wait=False)

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
