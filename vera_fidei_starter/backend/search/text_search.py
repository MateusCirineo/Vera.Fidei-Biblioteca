from dataclasses import dataclass
from models.database import Chunk, SessionLocal


@dataclass
class TextSearchHit:
    chunk_id: int
    score: float
    excerpt: str


class TextSearchClient:
    def search(self, query: str, limit: int = 5) -> list[TextSearchHit]:
        q = query.lower().strip()
        if not q:
            return []
        with SessionLocal() as db:
            chunks = db.query(Chunk).all()
            hits = []
            for chunk in chunks:
                text_lower = chunk.text.lower()
                if q in text_lower:
                    hits.append(TextSearchHit(chunk.id, float(text_lower.count(q)) + 1.0, chunk.text[:350]))
            hits.sort(key=lambda x: x.score, reverse=True)
            return hits[:limit]
