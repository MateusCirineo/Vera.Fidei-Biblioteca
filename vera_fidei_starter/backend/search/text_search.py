from dataclasses import dataclass
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from core.config import settings

ES_INDEX = "vera_fidei_chunks"


@dataclass
class TextSearchHit:
    chunk_id: int
    score: float
    excerpt: str


class TextSearchClient:
    def __init__(self) -> None:
        self.es = Elasticsearch([settings.elasticsearch_url])
        self._ensure_index()

    def _ensure_index(self) -> None:
        if not self.es.indices.exists(index=ES_INDEX):
            self.es.indices.create(index=ES_INDEX, body={
                "mappings": {
                    "properties": {
                        "chunk_id":          {"type": "integer"},
                        "book_id":           {"type": "integer"},
                        "book_file_id":      {"type": "integer"},
                        "text":              {"type": "text", "analyzer": "standard"},
                        "author":            {"type": "keyword"},
                        "work_title":        {"type": "keyword"},
                        "collection":        {"type": "keyword"},
                        "volume":            {"type": "integer"},
                        "column_start":      {"type": "integer"},
                        "language":          {"type": "keyword"},
                        "pdf_page":          {"type": "integer"},
                        "edition_label":     {"type": "keyword"},
                        "chapter_or_section":{"type": "keyword"},
                        "char_offset_start": {"type": "integer"},
                        "char_offset_end":   {"type": "integer"},
                        "translation_text":  {"type": "text", "analyzer": "standard"},
                        "translation_language": {"type": "keyword"},
                    }
                }
            })

    def search(self, query: str, attributed_to: str = "", limit: int = 5, query_language: str = "unknown") -> list[TextSearchHit]:
        if not query.strip():
            return []

        _ORIGINAL_LANGS = {"la", "grc", "el", "he"}
        _TRANSLATION_LANGS = {"pt", "es", "fr", "it", "en", "de"}

        query_langs = set((query_language or "unknown").split("+"))

        if query_langs & _TRANSLATION_LANGS:
            fields = ["translation_text^2", "text"]
        elif query_langs & _ORIGINAL_LANGS:
            fields = ["text^2", "translation_text"]
        else:
            fields = ["text^1.2", "translation_text^1.2"]

        body = {
            "query": {
                "bool": {
                    "must": [{"multi_match": {"query": query, "fields": fields}}],
                    "should": ([{"match": {"author": attributed_to}}] if attributed_to else []),
                }
            },
            "size": limit,
        }

        try:
            resp = self.es.search(index=ES_INDEX, body=body)
        except Exception:
            return []

        hits = []
        for hit in resp["hits"]["hits"]:
            hits.append(TextSearchHit(
                chunk_id=hit["_source"]["chunk_id"],
                score=hit["_score"],
                excerpt=hit["_source"].get("text", "")[:350],
            ))
        return hits

    def index_chunk(self, chunk_id: int, doc: dict) -> None:
        self.es.index(index=ES_INDEX, id=str(chunk_id), document={**doc, "chunk_id": chunk_id})

    def index_chunks(self, items: list[tuple[int, dict]]) -> None:
        if not items:
            return
        actions = [
            {
                "_op_type": "index",
                "_index": ES_INDEX,
                "_id": str(chunk_id),
                "_source": {**doc, "chunk_id": chunk_id},
            }
            for chunk_id, doc in items
        ]
        bulk(self.es, actions)

    def delete_chunk(self, chunk_id: int) -> None:
        try:
            self.es.delete(index=ES_INDEX, id=str(chunk_id), ignore=[404])
        except Exception:
            pass
