from unittest.mock import patch

from search.semantic_search import SemanticSearchClient


def test_semantic_client_operates_without_chromadb_runtime_dependency() -> None:
    with patch("search.semantic_search.importlib.util.find_spec", return_value=None):
        client = SemanticSearchClient()

        assert client.collection is None
        assert client.delta_collection is None
        client.index_chunks([(1, "texto patrístico", {"book_id": 1})])
        client.index_translation(1, "tradução", {"book_id": 1})
        client.delete_chunk(1)
