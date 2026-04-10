from dataclasses import dataclass


@dataclass
class SemanticSearchHit:
    chunk_id: int
    score: float


class SemanticSearchClient:
    def search(self, query: str, limit: int = 5) -> list[SemanticSearchHit]:
        return []
