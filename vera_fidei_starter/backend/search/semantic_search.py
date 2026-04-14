from dataclasses import dataclass
import chromadb
from sentence_transformers import SentenceTransformer
from core.config import settings

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


@dataclass
class SemanticSearchHit:
    chunk_id: int
    score: float


class SemanticSearchClient:
    def __init__(self) -> None:
        client = chromadb.PersistentClient(path=settings.chroma_path)
        self.collection = client.get_or_create_collection("vera_fidei")

    def search(self, query: str, limit: int = 5) -> list[SemanticSearchHit]:
        if not query.strip():
            return []

        model = _get_model()
        embedding = model.encode([query]).tolist()

        try:
            raw = self.collection.query(
                query_embeddings=embedding,
                n_results=limit,
                include=["metadatas", "distances"],
            )
        except Exception:
            return []

        hits = []
        for i, meta in enumerate(raw["metadatas"][0]):
            similarity = 1.0 - raw["distances"][0][i]
            hits.append(SemanticSearchHit(
                chunk_id=int(meta["chunk_id"]),
                score=max(0.0, similarity),
            ))
        return hits

    def index_chunk(self, chunk_id: int, text: str, metadata: dict, language: str = "la") -> None:
        model = _get_model()
        embedding = model.encode([text]).tolist()
        self.collection.add(
            ids=[str(chunk_id)],
            embeddings=embedding,
            documents=[text],
            metadatas=[{**metadata, "chunk_id": str(chunk_id), "language": language}],
        )

    def delete_chunk(self, chunk_id: int) -> None:
        try:
            self.collection.delete(ids=[str(chunk_id)])
        except Exception:
            pass
        # Remove também a tradução associada, se existir
        try:
            self.collection.delete(ids=[f"{chunk_id}_translation_pt"])
        except Exception:
            pass

    def index_translation(self, chunk_id: int, text: str, metadata: dict, language: str = "pt") -> None:
        model = _get_model()
        embedding = model.encode([text]).tolist()
        translation_id = f"{chunk_id}_translation_{language}"
        self.collection.add(
            ids=[translation_id],
            embeddings=embedding,
            documents=[text],
            metadatas=[{**metadata, "chunk_id": str(chunk_id), "language": language, "is_translation": "true"}],
        )
