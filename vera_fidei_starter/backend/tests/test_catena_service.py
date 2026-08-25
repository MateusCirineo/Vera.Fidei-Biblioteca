import unittest

from services.catena_service import (
    BibleReferenceError,
    build_catena_es_query,
    parse_bible_reference,
    reference_in_bible_header,
    search_catena,
)


class FakeElasticsearch:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, *, index, body):
        self.calls.append({"index": index, "body": body})
        return {"hits": {"total": {"value": len(self.hits), "relation": "eq"}, "hits": self.hits}}


def es_hit(
    chunk_id,
    book_id,
    text,
    *,
    work="Obra patristica",
    author="Santo Agostinho",
    page=10,
    section="",
    score=10.0,
):
    return {
        "_score": score,
        "_source": {
            "chunk_id": chunk_id,
            "book_id": book_id,
            "text": text,
            "translation_text": None,
            "author": author,
            "work_title": work,
            "pdf_page": page,
            "chapter_or_section": section,
            "collection": "PT",
            "volume": None,
            "edition_label": "Edicao de teste",
            "language": "pt",
        },
    }


class BibleReferenceParserTests(unittest.TestCase):
    def test_accepts_documented_formats_case_insensitively(self):
        expected = "João 6,53"
        for raw in ("Jo 6,53", "Joao 6:53", "Ioh 6.53", "jo 6,53", "JO 6,53"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_bible_reference(raw).canonical, expected)

    def test_supports_numbered_book_with_or_without_space_and_ranges(self):
        self.assertEqual(parse_bible_reference("1Cor 13,4-7").canonical, "1 Corintios 13,4-7")
        self.assertEqual(parse_bible_reference("1 Cor 13:4–7").canonical, "1 Corintios 13,4-7")

    def test_requires_book_chapter_and_verse(self):
        for raw in ("Jo 6", "6,53", "Jo6,53", "Jo 6;53", "Jo 6,abc", "LivroFalso 6,53"):
            with self.subTest(raw=raw), self.assertRaises(BibleReferenceError):
                parse_bible_reference(raw)

    def test_validates_chapter_verse_and_range(self):
        cases = ("Jo 22,1", "Jo 6,999", "Mt 0,1", "Mt 5,9-3")
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(BibleReferenceError):
                parse_bible_reference(raw)

    def test_joao_and_jonas_have_distinct_abbreviations(self):
        self.assertEqual(parse_bible_reference("Jo 1,1").book.key, "john")
        self.assertEqual(parse_bible_reference("Jn 1,1").book.key, "jonah")
        self.assertEqual(parse_bible_reference("Jonas 1,1").book.key, "jonah")
        self.assertEqual(parse_bible_reference("Jó 1,1").book.key, "job")

    def test_header_range_contains_requested_verse(self):
        reference = parse_bible_reference("Jo 6,53")

        self.assertTrue(reference_in_bible_header("João 6: 52–54", reference))
        self.assertTrue(
            reference_in_bible_header(
                "[6:52-54]",
                reference,
                work_title="Catena Aurea - Evangelho de Sao Joao",
            )
        )
        self.assertFalse(reference_in_bible_header("João 6:55-59", reference))
        self.assertFalse(reference_in_bible_header("[6:52-54]", reference, work_title="Comentario a Mateus"))
        self.assertFalse(
            reference_in_bible_header(
                "Citação incidental João 6:52-54.",
                reference,
                work_title="Catena Aurea - Evangelho de Sao Lucas",
            )
        )


class CatenaSearchTests(unittest.TestCase):
    def test_query_is_hard_filtered_to_supplied_patristic_books(self):
        ref = parse_bible_reference("Mt 16,18")
        body = build_catena_es_query(ref, [9, 3, 9], catena_book_ids=[2105], candidate_limit=100)

        self.assertEqual(body["query"]["bool"]["filter"], [{"terms": {"book_id": [3, 9, 2105]}}])
        self.assertEqual(body["query"]["bool"]["minimum_should_match"], 1)
        self.assertEqual(body["size"], 100)

    def test_empty_allow_list_returns_without_unfiltered_search(self):
        es = FakeElasticsearch([])

        result = search_catena(es, "Jo 6,53", [], limit=20)

        self.assertEqual(result.hit_ids, ())
        self.assertEqual(es.calls, [])

    def test_substantive_scoped_commentary_outranks_and_excludes_reference_dump(self):
        substantive = es_hit(
            87743,
            2108,
            (
                "[6:53] Entao Jesus lhes disse que era necessario comer sua carne. "
                "SANTO AGOSTINHO: Isto significa que o fiel recebe a vida em Cristo, "
                "porque este alimento e espiritual e comunica a unidade da Igreja. "
                "SÃO BEDA ensina, portanto, que a promessa se dirige a todos e deve "
                "ser entendida no misterio do corpo e do sangue do Senhor."
            ),
            work="Catena Aurea Vol 4 - Evangelho de Sao Joao",
            page=251,
            score=2.0,
        )
        explanatory = es_hit(
            10723,
            300,
            (
                "Santo Agostinho recorda Jo 6,53 e explica que o sacramento conduz "
                "o fiel a Cristo, porque nele se encontra a vida prometida pelo Senhor. "
                "Portanto, o sentido da passagem nao e uma simples figura sem efeito."
            ),
            work="Comentario aos Salmos",
            page=266,
            score=20.0,
        )
        footnote_dump = es_hit(
            74498,
            301,
            (
                "[37] Mt 5,13. [38] 1Cor 15,47. [39] Mt 5,45. [40] Jo 6,51. "
                "[41] Jo 6,53. [42] Lc 14,33. [43] Mt 6,34. [44] 1Tm 6,7."
            ),
            work="Obras completas",
            page=216,
            score=50.0,
        )
        non_patristic = es_hit(
            64472,
            999,
            "O Catecismo cita Jo 6,53 e explica o sacramento da Eucaristia.",
            work="Catecismo da Igreja Catolica",
            author="Igreja Catolica",
            score=100.0,
        )
        es = FakeElasticsearch([footnote_dump, non_patristic, explanatory, substantive])

        result = search_catena(es, "Jo 6,53", [300, 301], catena_book_ids=[2108], limit=10)

        self.assertEqual(result.hit_ids, (87743, 10723))
        self.assertEqual(result.hits[0].evidence_kind, "scoped_verse")
        self.assertIn("linguagem_exegetica", result.hits[0].reasons)
        self.assertNotIn(74498, result.hit_ids)
        self.assertNotIn(64472, result.hit_ids)

    def test_catena_header_fetches_and_boosts_following_commentary_chunk(self):
        header = es_hit(
            87742,
            2108,
            "João 6: 52–54",
            work="Catena Aurea Vol 4 - Evangelho de Sao Joao",
            page=250,
            score=1.0,
        )
        commentary = es_hit(
            87743,
            2108,
            (
                "SANTO AGOSTINHO: Isto significa que o fiel recebe a vida de Cristo, "
                "porque o corpo do Senhor comunica a unidade da Igreja. SÃO BEDA "
                "ensina, portanto, que este misterio deve ser entendido espiritualmente "
                "e acolhido na fé pelos membros do corpo de Cristo."
            ),
            work="Catena Aurea Vol 4 - Evangelho de Sao Joao",
            page=251,
            score=0.0,
        )

        class HeaderElasticsearch(FakeElasticsearch):
            def search(self, *, index, body):
                self.calls.append({"index": index, "body": body})
                filters = body.get("query", {}).get("bool", {}).get("filter", [])
                if any("chunk_id" in item.get("terms", {}) for item in filters):
                    return {"hits": {"hits": [commentary]}}
                return {"hits": {"hits": [header]}}

        result = search_catena(
            HeaderElasticsearch([]),
            "Jo 6,53",
            [],
            catena_book_ids=[2108],
        )

        self.assertEqual(result.hit_ids[0], 87743)
        self.assertEqual(result.hits[0].evidence_kind, "catena_header_context")
        self.assertIn(87742, result.hit_ids)

    def test_cross_reference_in_other_catena_volume_does_not_outrank_target_volume(self):
        target = es_hit(
            87743,
            2108,
            (
                "[6:53] SANTO AGOSTINHO explica que isto significa receber a vida "
                "de Cristo, porque o fiel participa do corpo do Senhor e, portanto, "
                "permanece na unidade espiritual da Igreja."
            ),
            work="Catena Aurea Vol 4 - Evangelho de Sao Joao",
            page=251,
            score=1,
        )
        cross_reference = es_hit(
            86764,
            2107,
            (
                "SÃO GREGÓRIO comenta o nascimento em Belem e menciona Jo 6,53. "
                "Portanto, a casa do pao recorda de modo figurado o alimento celeste."
            ),
            work="Catena Aurea Vol 3 - Evangelho de Sao Lucas",
            page=142,
            score=50,
        )

        result = search_catena(
            FakeElasticsearch([cross_reference, target]),
            "Jo 6,53",
            [],
            catena_book_ids=[2107, 2108],
        )

        self.assertEqual(result.hit_ids[:2], (87743, 86764))

    def test_neighbor_expansion_stops_before_next_header(self):
        header = es_hit(
            100,
            2105,
            "Mateus 16:13-20",
            work="Catena Aurea - Evangelho de Sao Mateus",
            page=550,
        )
        commentary = es_hit(
            101,
            2105,
            (
                "SÃO JERÔNIMO explica que a pedra indica a firmeza da confissão, "
                "porque Cristo edifica sua Igreja sobre a fé verdadeira. Portanto, "
                "esta promessa manifesta a autoridade e a unidade dos discípulos."
            ),
            work="Catena Aurea - Evangelho de Sao Mateus",
            page=556,
        )
        next_header = es_hit(
            102,
            2105,
            "Mateus 17:1-8",
            work="Catena Aurea - Evangelho de Sao Mateus",
            page=560,
        )
        after_next_header = es_hit(
            103,
            2105,
            (
                "SANTO AGOSTINHO explica a transfiguracao, porque a gloria de Cristo "
                "foi manifestada aos discipulos e, portanto, confirma a esperanca."
            ),
            work="Catena Aurea - Evangelho de Sao Mateus",
            page=561,
        )

        class BoundaryElasticsearch(FakeElasticsearch):
            def search(self, *, index, body):
                self.calls.append({"index": index, "body": body})
                filters = body.get("query", {}).get("bool", {}).get("filter", [])
                if any("chunk_id" in item.get("terms", {}) for item in filters):
                    return {"hits": {"hits": [commentary, next_header, after_next_header]}}
                return {"hits": {"hits": [header]}}

        result = search_catena(
            BoundaryElasticsearch([]),
            "Mt 16,18",
            [],
            catena_book_ids=[2105],
        )

        self.assertIn(101, result.hit_ids)
        self.assertNotIn(102, result.hit_ids)
        self.assertNotIn(103, result.hit_ids)
        comment_hit = next(hit for hit in result.hits if hit.chunk_id == 101)
        self.assertIn("pedra indica a firmeza", comment_hit.excerpt)
        self.assertLessEqual(len(comment_hit.excerpt), 720)

    def test_overlapping_chunks_are_deduplicated(self):
        common = (
            "Jo 6,53. Santo Agostinho explica que o fiel recebe a vida em Cristo, "
            "porque o alimento prometido une os membros ao corpo do Senhor. Portanto, "
            "o sentido deste misterio deve ser compreendido na comunhao da Igreja."
        )
        first = es_hit(100, 8, common + " Contexto posterior.", page=266, score=10)
        second = es_hit(101, 8, "Contexto anterior. " + common, page=266, score=9)
        es = FakeElasticsearch([first, second])

        result = search_catena(es, "Jo 6,53", [8])

        self.assertEqual(result.hit_ids, (100,))

    def test_result_exposes_simple_ids_for_route_integration(self):
        hit = es_hit(
            42,
            7,
            (
                "Mt 16,18. Santo Agostinho explica que a pedra significa a firmeza "
                "da fe confessada por Pedro, porque Cristo edifica a Igreja e, portanto, "
                "as portas do inferno nao prevalecem contra ela."
            ),
            work="Tratado sobre o Evangelho de Mateus",
        )
        result = search_catena(FakeElasticsearch([hit]), "Mt 16,18", [7])

        self.assertEqual(result.reference.canonical, "Mateus 16,18")
        self.assertEqual(result.hit_ids, (42,))
        self.assertEqual(result.hits[0].chunk_id, 42)


if __name__ == "__main__":
    unittest.main()
