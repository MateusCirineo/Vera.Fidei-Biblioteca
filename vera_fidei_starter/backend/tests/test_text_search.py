import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import search.semantic_search as semantic_search

from search.text_search import (
    AcervoSearchHit,
    AcervoSearchUnavailable,
    PATRISTIC_COLLECTIONS,
    TextSearchClient,
    expand_theological_query,
    source_page_key,
    theological_query_expansions,
)


def _hit(chunk_id: int, score: float, **overrides) -> AcervoSearchHit:
    values = {
        "chunk_id": chunk_id,
        "score": score,
        "text": f"texto {chunk_id}",
        "author": "Autor",
        "work_title": "Obra",
    }
    values.update(overrides)
    return AcervoSearchHit(**values)


class TheologicalExpansionTests(unittest.TestCase):
    def test_expansion_matches_whole_tokens_not_substrings(self) -> None:
        self.assertEqual(theological_query_expansions("afetos naturais"), [])
        self.assertEqual(expand_theological_query("café e afetos naturais"), "café e afetos naturais")

        expanded = theological_query_expansions("a fé dos apóstolos")
        self.assertIn("fides", expanded)
        self.assertIn("fidei", expanded)

    def test_multiword_term_accepts_punctuation_between_tokens(self) -> None:
        expanded = theological_query_expansions("a missão do Espírito-Santo")
        self.assertIn("spiritus sanctus", expanded)


class FlatSemanticIndexTests(unittest.TestCase):
    def test_flat_cosine_query_returns_the_nearest_public_chunk(self) -> None:
        previous_matrix = semantic_search._flat_matrix
        previous_ids = semantic_search._flat_chunk_ids
        try:
            semantic_search._flat_matrix = np.asarray(
                [[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]],
                dtype=np.float32,
            )
            semantic_search._flat_chunk_ids = np.asarray([10, 20, 30], dtype=np.int64)
            hits = semantic_search._flat_semantic_query(
                np.asarray([0.95, 0.05], dtype=np.float32),
                2,
            )
        finally:
            semantic_search._flat_matrix = previous_matrix
            semantic_search._flat_chunk_ids = previous_ids
        self.assertEqual([chunk_id for chunk_id, _score in hits], [10, 30])


class AcervoQueryBodyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = object.__new__(TextSearchClient)

    def test_patristic_filter_covers_real_collections_and_dynamic_book_ids(self) -> None:
        body = self.client._build_acervo_es_body(
            "martírio",
            ["text", "translation_text"],
            "",
            "patristica",
            50,
            patristic_book_ids=[2152, 2157, 2152],
            original_query="martírio",
        )

        serialized = json.dumps(body, ensure_ascii=False)
        for collection in PATRISTIC_COLLECTIONS:
            self.assertIn(collection, serialized)
        self.assertIn('"book_id": [2152, 2157]', serialized)

    def test_phrase_is_boosted_and_terms_have_minimum_match(self) -> None:
        body = self.client._build_acervo_es_body(
            "força interior do amor",
            ["text", "translation_text"],
            "",
            "",
            20,
            original_query="força interior do amor",
        )
        alternatives = body["query"]["bool"]["must"][0]["bool"]["should"]

        self.assertEqual(alternatives[0]["multi_match"]["type"], "phrase")
        self.assertEqual(alternatives[0]["multi_match"]["boost"], 6.0)
        self.assertEqual(alternatives[1]["multi_match"]["minimum_should_match"], "70%")
        self.assertGreater(body["min_score"], 0)

    def test_common_term_can_reserve_one_candidate_per_work(self) -> None:
        body = self.client._build_acervo_es_body(
            "scriptura",
            ["text", "translation_text"],
            "",
            "patristica",
            200,
            original_query="scriptura",
            collapse_by_book=True,
        )

        self.assertEqual(body["collapse"], {"field": "book_id"})

    def test_page_search_is_collapsed_counted_and_offset(self) -> None:
        body = self.client._build_acervo_es_body(
            "scriptura",
            ["text", "translation_text"],
            "",
            "patristica",
            36,
            original_query="scriptura",
            collapse_by_page=True,
            offset=72,
            source_fidelities=["source_text", "verified"],
            include_page_counts=True,
            literal_candidates_only=True,
        )

        self.assertEqual(body["collapse"], {"field": "source_page_key"})
        self.assertEqual(body["from"], 72)
        self.assertTrue(body["track_total_hits"])
        self.assertIn("matching_pages", body["aggs"])
        self.assertIn(
            {"terms": {"source_fidelity": ["source_text", "verified"]}},
            body["query"]["bool"]["filter"],
        )
        self.assertTrue(any(
            clause.get("bool", {}).get("minimum_should_match") == 1
            and {"term": {"is_quotable": True}} in clause["bool"].get("should", [])
            for clause in body["query"]["bool"]["filter"]
        ))
        alternatives = body["query"]["bool"]["must"][0]["bool"]["should"]
        # literal_candidates_only now emits a bool/should that covers both
        # literal_search_text (source_text/verified chunks) and text (OCR chunks).
        self.assertEqual(len(alternatives), 1)
        alt = alternatives[0]
        self.assertIn("bool", alt)
        should_clauses = alt["bool"]["should"]
        fields_hit = {
            list(clause.get("match", {}).keys())[0]
            for clause in should_clauses
            if "match" in clause
        }
        self.assertIn("literal_search_text", fields_hit)
        self.assertIn("text", fields_hit)

    def test_page_and_work_collapse_are_mutually_exclusive(self) -> None:
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            self.client._build_acervo_es_body(
                "scriptura",
                ["text"],
                "",
                "patristica",
                10,
                collapse_by_book=True,
                collapse_by_page=True,
            )

    def test_source_page_key_prefers_file_and_never_collapses_pageless_chunks(self) -> None:
        self.assertEqual(
            source_page_key({"book_id": 10, "book_file_id": 20, "pdf_page": 7}, 30),
            "file:20:page:7",
        )
        self.assertEqual(
            source_page_key({"book_id": 10, "pdf_page": 7}, 30),
            "book:10:page:7",
        )
        self.assertEqual(source_page_key({"book_id": 10, "pdf_page": None}, 30), "chunk:30")

    def test_paged_search_reads_unique_page_and_work_totals(self) -> None:
        self.client.es = Mock()
        self.client.es.search.return_value = {
            "hits": {
                "total": {"value": 8, "relation": "eq"},
                "hits": [{
                    "_id": "1",
                    "_score": 4.0,
                    "_source": {
                        "chunk_id": 1,
                        "text": "scriptura",
                        "author": "A",
                        "work_title": "B",
                        "book_id": 10,
                        "pdf_page": 3,
                    },
                }],
            },
            "aggregations": {
                "matching_pages": {"value": 7},
                "matching_works": {"value": 4},
            },
        }

        page = self.client.search_acervo_page("scriptura", limit=1, offset=2)

        self.assertEqual([hit.chunk_id for hit in page.hits], [1])
        self.assertEqual(page.total, 7)
        self.assertEqual(page.matching_works, 4)
        self.assertEqual(page.offset, 2)
        self.assertEqual(page.consumed, 1)

    def test_lexical_outage_is_not_reported_as_zero_results(self) -> None:
        self.client.es = Mock()
        self.client.es.search.side_effect = RuntimeError("elasticsearch offline")

        with self.assertRaises(AcervoSearchUnavailable):
            self.client.search_acervo("eucaristia", limit=5)

        with self.assertLogs("search.text_search", level="WARNING"):
            result = self.client.search_acervo(
                "eucaristia",
                limit=5,
                raise_on_error=False,
            )
        self.assertEqual(result, [])


class HybridAcervoSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = object.__new__(TextSearchClient)
        semantic_env = patch.dict("os.environ", {"VERA_ENABLE_SEMANTIC_SEARCH": "true"})
        semantic_env.start()
        self.addCleanup(semantic_env.stop)

    def test_semantic_failure_returns_lexical_results(self) -> None:
        lexical = [_hit(1, 12.0)]
        self.client.search_acervo = Mock(return_value=lexical)

        semantic = Mock()
        semantic.search.side_effect = RuntimeError("chroma offline")

        with self.assertLogs("search.text_search", level="WARNING") as captured:
            result = self.client.search_acervo_hybrid(
                "tema",
                limit=5,
                semantic_client=semantic,
            )

        self.assertEqual(result, lexical)
        self.assertIn("lexical fallback", captured.output[0])

    @patch.dict("os.environ", {"VERA_ENABLE_SEMANTIC_SEARCH": "false"})
    def test_semantic_search_can_be_disabled_without_delaying_lexical_results(self) -> None:
        lexical = [_hit(1, 12.0)]
        self.client.search_acervo = Mock(return_value=lexical)
        semantic = Mock()

        result = self.client.search_acervo_hybrid(
            "tema",
            limit=5,
            semantic_client=semantic,
        )

        self.assertEqual(result, lexical)
        semantic.search.assert_not_called()

    def test_hybrid_includes_semantic_only_hit_and_deduplicates(self) -> None:
        lexical = [_hit(1, 10.0, collection="PT", book_id=10)]
        self.client.search_acervo = Mock(return_value=lexical)
        self.client.es = Mock()
        self.client.es.mget.return_value = {
            "docs": [
                {
                    "_id": "2",
                    "found": True,
                    "_source": {
                        "chunk_id": 2,
                        "text": "somente semântico",
                        "author": "Autor",
                        "work_title": "Forty Gospel Homilies",
                        "collection": "Patrística EN",
                        "book_id": 2152,
                    },
                },
            ]
        }
        semantic = Mock()
        semantic.search.return_value = [
            SimpleNamespace(chunk_id=1, score=0.8),
            SimpleNamespace(chunk_id=2, score=0.9),
            SimpleNamespace(chunk_id=3, score=0.15),  # abaixo do limiar calibrado
        ]

        result = self.client.search_acervo_hybrid(
            "paráfrase",
            limit=5,
            collection_filter="patristica",
            patristic_book_ids=[2152],
            semantic_client=semantic,
        )

        self.assertEqual([hit.chunk_id for hit in result], [1, 2])
        self.assertEqual(len({hit.chunk_id for hit in result}), 2)
        self.assertTrue(all(0 <= hit.score <= 1 for hit in result))
        semantic.search.assert_called_once_with("paráfrase", limit=30, timeout=15.0)

    def test_calibrated_bge_m3_score_is_not_discarded(self) -> None:
        self.client.search_acervo = Mock(return_value=[])
        self.client.es = Mock()
        self.client.es.mget.return_value = {
            "docs": [{
                "_id": "9",
                "found": True,
                "_source": {
                    "chunk_id": 9,
                    "text": "Inquieto está o nosso coração enquanto não repousa em Deus.",
                    "author": "Santo Agostinho",
                    "work_title": "Confissões",
                    "collection": "PT",
                    "book_id": 9,
                },
            }]
        }
        semantic = Mock()
        semantic.search.return_value = [SimpleNamespace(chunk_id=9, score=0.23)]

        result = self.client.search_acervo_hybrid(
            "a alma procura descanso em Deus",
            limit=5,
            semantic_client=semantic,
        )

        self.assertEqual([hit.chunk_id for hit in result], [9])
        self.assertGreater(result[0].score, 0)


if __name__ == "__main__":
    unittest.main()
