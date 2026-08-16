import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import PDFExtractor
from scripts.audit_source_fidelity import _exact_page_matches
from scripts.reindex_digital_source_text import _validate_source_chunks
from scripts.import_verified_pages import (
    parse_review_entry,
    rendered_page_fingerprint,
    transcription_sha256,
)
from scripts.prepare_visual_page_reviews import parse_pages
from scripts.ocr_reindex_books import _overlay_reviewed_pages
from scripts.audit_latin_visual_coverage import is_latin_work
from PIL import Image
from services.source_fidelity_service import (
    PUBLIC_SOURCE_FIDELITIES,
    VerifiedPassageCandidate,
    normalize_literal,
    select_verified_passage,
)
from services.page_verification_service import compare_page_transcriptions
from search.content_quality import assess_content, extract_semantic_passage
from search.text_search import AcervoSearchHit, theological_literal_variants
from app.agents.base import PipelineContext
from app.agents.translation_agent import TranslationAgent
from app.agents.citation_verifier import CitationVerifierAgent
from services.verification_service import _authoritative_source_text
from api.routes.search import (
    _allow_unverified_pdf_locators,
    _decode_search_cursor,
    _deduplicate_hits_by_page,
    _diversify_hits_by_book,
    _encode_search_cursor,
    _effective_collection_filter,
    _filter_quotable_hits_preserving_verified,
    _literal_query_supported,
    _merge_literal_and_semantic_hits,
    _scan_all_quotable_source_hits,
    _scan_quotable_source_hits,
    _semantic_quotable_source_hits,
    _search_cursor_context,
)


class SourceFidelityTests(unittest.TestCase):
    def test_only_native_or_visually_verified_chunks_are_public(self) -> None:
        self.assertEqual(PUBLIC_SOURCE_FIDELITIES, frozenset({"source_text", "verified"}))

    def test_normalization_changes_layout_not_source_words(self) -> None:
        self.assertEqual(normalize_literal("Ver-\u00adbum   caro\nfactum"), "Ver-bum caro factum")

    def test_page_consensus_requires_every_visible_character_to_agree(self) -> None:
        result = compare_page_transcriptions(
            "Nazaræi Judæi sunt, Christum honorantes.",
            "Nazaræi Judæi sunt, Christum honorantes.",
        )
        self.assertTrue(result.exact)
        self.assertEqual(result.status, "independent_ocr_consensus")
        self.assertEqual(result.agreement_ratio, 1.0)

        changed = compare_page_transcriptions(
            "Nazaræi Judæi sunt, Christum honorantes.",
            "Nazarei Judei sunt, Christum honorantes.",
        )
        self.assertFalse(changed.exact)
        self.assertEqual(changed.status, "needs_visual_review")
        self.assertTrue(changed.differences)

    def test_page_consensus_normalizes_layout_only(self) -> None:
        result = compare_page_transcriptions(
            "Verbum   caro\nfactum est.",
            "Verbum caro factum est.",
        )
        self.assertTrue(result.exact)

    def test_visual_page_manifest_requires_explicit_human_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "page.txt").write_text("Verbum caro factum est.", encoding="utf-8")
            raw = {
                "book_id": 32,
                "book_file_id": 32,
                "pdf_page": 12,
                "language": "la",
                "reviewer": "visual-reviewer",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "render_dpi": 300,
                "pdf_sha256": "a" * 64,
                "render_pixel_sha256": "b" * 64,
                "transcription_sha256": transcription_sha256("Verbum caro factum est."),
                "transcription_file": "page.txt",
                "verification_method": "visual_pdf",
                "visual_confirmation": False,
            }
            with self.assertRaisesRegex(ValueError, "visual_confirmation"):
                parse_review_entry(raw, root)
            raw["visual_confirmation"] = True
            parsed = parse_review_entry(raw, root)
            self.assertEqual(parsed.book_id, 32)
            self.assertEqual(parsed.pdf_page, 12)

    def test_visual_page_manifest_rejects_transcription_outside_review_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = {
                "book_id": 32,
                "book_file_id": 32,
                "pdf_page": 12,
                "language": "la",
                "reviewer": "visual-reviewer",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "render_dpi": 300,
                "pdf_sha256": "a" * 64,
                "render_pixel_sha256": "b" * 64,
                "transcription_sha256": "c" * 64,
                "transcription_file": "../outside.txt",
                "verification_method": "visual_pdf",
                "visual_confirmation": True,
            }
            with self.assertRaisesRegex(ValueError, "inside the manifest directory"):
                parse_review_entry(raw, root)

    def test_render_fingerprint_uses_pixels_and_geometry(self) -> None:
        first = Image.new("RGB", (2, 2), "white")
        second = Image.new("RGB", (2, 2), "white")
        changed = Image.new("RGB", (2, 2), "black")
        resized = Image.new("RGB", (1, 4), "white")
        self.assertEqual(rendered_page_fingerprint(first), rendered_page_fingerprint(second))
        self.assertNotEqual(rendered_page_fingerprint(first), rendered_page_fingerprint(changed))
        self.assertNotEqual(rendered_page_fingerprint(first), rendered_page_fingerprint(resized))
        self.assertEqual(
            transcription_sha256("Verbum   caro\nfactum"),
            hashlib.sha256("Verbum caro factum".encode("utf-8")).hexdigest(),
        )

    def test_visual_review_page_ranges_are_explicit_and_deduplicated(self) -> None:
        self.assertEqual(parse_pages(["3-5", "5,7"]), [3, 4, 5, 7])
        with self.assertRaisesRegex(ValueError, "invalid page range"):
            parse_pages(["5-3"])

    def test_reocr_cannot_overwrite_a_visually_reviewed_page(self) -> None:
        pages = [
            {
                "page_number": 1,
                "text": "OCR incorreto",
                "extraction_method": "ocr",
                "source_fidelity": "unverified_ocr",
            },
            {
                "page_number": 2,
                "text": "Ainda pendente",
                "extraction_method": "ocr",
                "source_fidelity": "unverified_ocr",
            },
        ]
        updated = _overlay_reviewed_pages(pages, {1: "Verbum caro factum est."})
        self.assertEqual(updated[0]["text"], "Verbum caro factum est.")
        self.assertEqual(updated[0]["source_fidelity"], "verified")
        self.assertEqual(updated[1]["text"], "Ainda pendente")
        self.assertEqual(updated[1]["source_fidelity"], "unverified_ocr")

    def test_latin_scope_includes_multilingual_catalog_records(self) -> None:
        self.assertTrue(is_latin_work("la"))
        self.assertTrue(is_latin_work("latim/grego"))
        self.assertTrue(is_latin_work("frances/latim/grego/oriental"))
        self.assertTrue(is_latin_work("la+pt"))
        self.assertFalse(is_latin_work("italiano"))

    def test_verified_passage_bypasses_unrelated_ocr_quality_noise(self) -> None:
        hits = [SimpleNamespace(chunk_id=10), SimpleNamespace(chunk_id=20)]
        verified = SimpleNamespace(
            chunk_id=10,
            source_fidelity="verified_transcription",
        )
        with (
            patch("api.routes.search._hit_ids_supported_by_verified_passage", return_value={10}),
            patch("api.routes.search.filter_quotable_hits", return_value=[]),
        ):
            kept = _filter_quotable_hits_preserving_verified(
                hits,
                "Habere jam non potest",
                limit=10,
            )
        self.assertEqual([hit.chunk_id for hit in kept], [10])

    def test_verified_full_page_does_not_make_cover_quotable(self) -> None:
        hits = [SimpleNamespace(chunk_id=10)]
        with (
            patch("api.routes.search._hit_ids_supported_by_verified_passage", return_value=set()),
            patch("api.routes.search.filter_quotable_hits", return_value=[]),
        ):
            kept = _filter_quotable_hits_preserving_verified(hits, "digitized by Google", limit=10)
        self.assertEqual(kept, [])

    def test_verified_text_cannot_correct_a_wrong_literal_query_silently(self) -> None:
        self.assertTrue(_literal_query_supported("Habere jam non potest", "Habere jam non potest"))
        self.assertFalse(_literal_query_supported("Habere jam non potest", "Habere jam nom potest"))
        self.assertTrue(_literal_query_supported("de Maria Virgine", "Maria"))
        self.assertFalse(_literal_query_supported("Marianus", "Maria"))
        self.assertTrue(_literal_query_supported("A ressurreição dos mortos", "ressurreicao"))

        hits = [SimpleNamespace(chunk_id=10)]
        corrected = SimpleNamespace(
            chunk_id=10,
            text="Habere jam non potest",
            source_fidelity="verified_transcription",
        )
        with (
            patch("api.routes.search._hit_ids_supported_by_verified_passage", return_value=set()),
            patch("api.routes.search.filter_quotable_hits", return_value=hits),
            patch("api.routes.search._enrich_with_db", return_value=[corrected]),
        ):
            kept = _filter_quotable_hits_preserving_verified(
                hits,
                "Habere jam nom potest",
                limit=10,
            )
        self.assertEqual(kept, [])

    def test_curated_whole_query_equivalent_can_find_verified_latin(self) -> None:
        self.assertIn("eucharistia", theological_literal_variants("Eucaristia"))
        self.assertTrue(
            _literal_query_supported(
                "Haec Eucharistia corpus Christi est.",
                "Eucaristia",
            )
        )
        self.assertFalse(
            _literal_query_supported(
                "Haec Eucharistia corpus Christi est.",
                "Eucaristia corrupta",
            )
        )

    def test_curated_whole_query_equivalent_covers_english_greek_and_oriental(self) -> None:
        variants = theological_literal_variants("Eucaristia")
        self.assertIn("eucharist", variants)
        self.assertIn("εὐχαριστία", variants)
        self.assertIn("ܩܘܪܒܢܐ", variants)
        self.assertTrue(_literal_query_supported("The Eucharist is celebrated.", "Eucaristia"))
        self.assertTrue(_literal_query_supported("περὶ τῆς εὐχαριστίας", "Eucaristia"))

    def test_quote_scope_can_cover_the_complete_collection(self) -> None:
        self.assertEqual(_effective_collection_filter("all", quotes_only=True), "")
        self.assertEqual(_effective_collection_filter("patristica", quotes_only=True), "patristica")
        self.assertEqual(_effective_collection_filter("MAG", quotes_only=False), "MAG")

    def test_curated_language_variant_survives_the_body_text_gate(self) -> None:
        hit = SimpleNamespace(
            chunk_id=10,
            book_id=20,
            text="Haec Eucharistia corpus Christi est.",
            translation_text=None,
        )
        source_checked = SimpleNamespace(
            chunk_id=10,
            text="Haec Eucharistia corpus Christi est.",
        )
        with (
            patch("api.routes.search._hit_ids_supported_by_verified_passage", return_value=set()),
            patch(
                "api.routes.search.filter_quotable_hits",
                side_effect=lambda _hits, literal_query, **_kwargs: (
                    [hit] if literal_query == "eucharistia" else []
                ),
            ),
            patch("api.routes.search._enrich_with_db", return_value=[source_checked]),
        ):
            kept = _filter_quotable_hits_preserving_verified([hit], "Eucaristia", limit=10)
        self.assertEqual([item.chunk_id for item in kept], [10])

    def test_unverified_locator_is_single_term_only(self) -> None:
        self.assertTrue(_allow_unverified_pdf_locators("Eucaristia"))
        self.assertTrue(_allow_unverified_pdf_locators("scriptura"))
        self.assertFalse(_allow_unverified_pdf_locators("Habere jam nom potest"))

        hit = SimpleNamespace(
            chunk_id=10,
            book_id=20,
            text="scriptura",
            translation_text=None,
        )
        with (
            patch("api.routes.search._hit_ids_supported_by_verified_passage", return_value=set()),
            patch("api.routes.search.filter_quotable_hits", side_effect=[[], [], [], []]),
            patch("api.routes.search._enrich_with_db", return_value=[]),
            patch("api.routes.search._unverified_ocr_chunk_ids", return_value={10}),
        ):
            kept = _filter_quotable_hits_preserving_verified(
                [hit],
                "scriptura",
                limit=10,
                include_unverified_locators=True,
            )
        self.assertEqual([item.chunk_id for item in kept], [10])

    def test_locator_path_cannot_bypass_quality_gate_for_source_text(self) -> None:
        hit = SimpleNamespace(
            chunk_id=10,
            book_id=20,
            text="scriptura",
            translation_text=None,
        )
        with (
            patch("api.routes.search._hit_ids_supported_by_verified_passage", return_value=set()),
            patch("api.routes.search.filter_quotable_hits", side_effect=[[hit], [], [], []]),
            patch("api.routes.search._enrich_with_db", return_value=[]),
            patch("api.routes.search._unverified_ocr_chunk_ids", return_value=set()),
        ):
            kept = _filter_quotable_hits_preserving_verified(
                [hit],
                "scriptura",
                limit=10,
                include_unverified_locators=True,
            )
        self.assertEqual(kept, [])

    def test_corpus_search_keeps_source_faithful_prose_occurrence(self) -> None:
        hit = AcervoSearchHit(
            chunk_id=10,
            book_id=20,
            book_file_id=30,
            score=1.0,
            text=(
                "Alusão à Eucaristia. Eis aqui um parêntese em favor da presença real. "
                "Em comentário a esta passagem, o editor explica o ensino eucarístico."
            ),
            translation_text=None,
            author="Santo Agostinho",
            chunk_author=None,
            work_title="A Trindade",
            chapter_or_section=None,
            pdf_page=350,
        )
        with (
            patch("api.routes.search._hit_ids_supported_by_verified_passage", return_value=set()),
            patch("api.routes.search.filter_quotable_hits", return_value=[]),
            patch("api.routes.search._enrich_with_db", return_value=[]),
            patch("api.routes.search._public_source_chunk_ids", return_value={10}),
            patch("api.routes.search._unverified_ocr_chunk_ids", return_value=set()),
        ):
            kept = _filter_quotable_hits_preserving_verified(
                [hit],
                "Eucaristia",
                limit=10,
                include_source_occurrences=True,
            )
        self.assertEqual([item.chunk_id for item in kept], [10])
        self.assertIn("Eucaristia", kept[0].text)

    def test_corpus_search_never_presents_table_of_contents_as_a_quote(self) -> None:
        hit = AcervoSearchHit(
            chunk_id=10,
            book_id=20,
            book_file_id=30,
            score=1.0,
            text=(
                "Índice. Capítulo I Vida cristã 10 Capítulo II Eucaristia 18 "
                "Capítulo III Batismo 24 Capítulo IV Penitência 31 Capítulo V Oração 39 "
                "Capítulo VI Comunidade 47 Capítulo VII Ressurreição 56."
            ),
            translation_text=None,
            author="Autor desconhecido",
            chunk_author=None,
            work_title="Obra antiga",
            chapter_or_section="Índice",
            pdf_page=4,
        )
        with (
            patch("api.routes.search._hit_ids_supported_by_verified_passage", return_value=set()),
            patch("api.routes.search.filter_quotable_hits", return_value=[]),
            patch("api.routes.search._enrich_with_db", return_value=[]),
            patch("api.routes.search._public_source_chunk_ids", return_value={10}),
            patch("api.routes.search._unverified_ocr_chunk_ids", return_value=set()),
        ):
            kept = _filter_quotable_hits_preserving_verified(
                [hit],
                "Eucaristia",
                limit=10,
                include_source_occurrences=True,
            )
        self.assertEqual(kept, [])

    def test_body_match_is_not_hidden_by_a_google_footer(self) -> None:
        hit = AcervoSearchHit(
            chunk_id=11,
            book_id=20,
            score=1.0,
            text=(
                "Minucii locum oculos mentemque glaucoma præstrinxit, quo significatu "
                "verua antiquis linguæ latinæ auctoribus accepta fuerint. Tautologiam "
                "accurato scriptori tribui non posse demonstrat. "
                + "Doctrina diligenter exponitur. " * 10
                + "Digitized by Google"
            ),
            author="Lucas Holstenius",
            work_title="Epistola",
            pdf_page=232,
        )
        with (
            patch("api.routes.search._hit_ids_supported_by_verified_passage", return_value=set()),
            patch("api.routes.search._public_source_chunk_ids", return_value={11}),
            patch("api.routes.search._enrich_with_db", return_value=[]),
            patch("api.routes.search._unverified_ocr_chunk_ids", return_value=set()),
        ):
            kept = _filter_quotable_hits_preserving_verified(
                [hit],
                "tautologiam",
                limit=10,
                include_source_occurrences=True,
            )
        self.assertEqual([item.chunk_id for item in kept], [11])
        self.assertNotIn("Digitized by Google", kept[0].text)

    def test_semantic_passage_is_complete_source_body_text(self) -> None:
        passage = extract_semantic_passage(
            "The Eucharist is the sacrament of unity. The faithful receive it with reverence. "
            "This teaching belongs to the body of the work.",
            author="Saint Augustine",
            work_title="Sermon",
            pdf_page=20,
            min_chars=60,
        )
        self.assertIn("The Eucharist is the sacrament of unity.", passage)
        self.assertTrue(passage.endswith("."))

    def test_semantic_rag_keeps_only_public_body_passages(self) -> None:
        hit = AcervoSearchHit(
            chunk_id=10,
            book_id=20,
            score=0.72,
            text="The Eucharist is the sacrament of unity. The faithful receive it with reverence.",
            author="Saint Augustine",
            work_title="Sermon",
            pdf_page=20,
            match_type="semantic",
        )
        client = SimpleNamespace(search_acervo_semantic=Mock(return_value=[hit]))
        with (
            patch("api.routes.search._hydrate_quote_hit_authors", side_effect=lambda hits: hits),
            patch("api.routes.search._public_source_chunk_ids", return_value={10}),
            patch("api.routes.search.extract_semantic_passage", return_value=hit.text),
        ):
            kept = _semantic_quotable_source_hits(
                client,
                query="unidade sacramental",
                author_filter="",
                collection_filter="",
                patristic_book_ids=[],
            )
        self.assertEqual([item.chunk_id for item in kept], [10])
        self.assertEqual(kept[0].match_type, "semantic")

    def test_literal_and_semantic_results_are_interleaved_and_deduplicated(self) -> None:
        literal = [
            SimpleNamespace(chunk_id=1, book_id=10, book_file_id=100, pdf_page=1),
            SimpleNamespace(chunk_id=2, book_id=20, book_file_id=200, pdf_page=2),
        ]
        semantic = [
            SimpleNamespace(chunk_id=3, book_id=30, book_file_id=300, pdf_page=3),
            SimpleNamespace(chunk_id=4, book_id=10, book_file_id=100, pdf_page=1),
        ]
        merged = _merge_literal_and_semantic_hits(literal, semantic)
        self.assertEqual([item.chunk_id for item in merged], [1, 3, 2])

    def test_public_results_show_each_matching_work_before_repetitions(self) -> None:
        hits = [
            SimpleNamespace(chunk_id=1, book_id=10),
            SimpleNamespace(chunk_id=2, book_id=10),
            SimpleNamespace(chunk_id=3, book_id=20),
            SimpleNamespace(chunk_id=4, book_id=30),
        ]
        diversified = _diversify_hits_by_book(hits, limit=4)
        self.assertEqual([hit.chunk_id for hit in diversified], [1, 3, 4, 2])

    def test_public_results_deduplicate_chunks_from_the_same_pdf_page(self) -> None:
        hits = [
            SimpleNamespace(chunk_id=1, book_id=10, book_file_id=20, pdf_page=7),
            SimpleNamespace(chunk_id=2, book_id=10, book_file_id=20, pdf_page=7),
            SimpleNamespace(chunk_id=3, book_id=10, book_file_id=20, pdf_page=8),
        ]
        unique = _deduplicate_hits_by_page(hits)
        self.assertEqual([hit.chunk_id for hit in unique], [1, 3])

    def test_quote_scan_filters_every_ranked_batch_before_public_pagination(self) -> None:
        first = [
            SimpleNamespace(chunk_id=1, book_id=10, book_file_id=20, pdf_page=1),
            SimpleNamespace(chunk_id=2, book_id=10, book_file_id=20, pdf_page=2),
        ]
        second = [
            SimpleNamespace(chunk_id=3, book_id=30, book_file_id=40, pdf_page=7),
        ]
        client = SimpleNamespace(
            search_acervo_page=Mock(side_effect=[
                SimpleNamespace(hits=first, total=3, consumed=2, matching_works=0),
                SimpleNamespace(hits=second, total=3, consumed=1, matching_works=0),
            ])
        )

        with (
            patch("api.routes.search._hydrate_quote_hit_authors", side_effect=lambda hits: hits),
            patch(
                "api.routes.search._filter_quotable_hits_preserving_verified",
                side_effect=[[first[1]], second],
            ),
        ):
            kept = _scan_all_quotable_source_hits(
                client,
                query="Eucaristia",
                author_filter="",
                collection_filter="patristica",
                patristic_book_ids=[10, 30],
            )

        self.assertEqual([hit.chunk_id for hit in kept], [2, 3])
        self.assertEqual(
            [call.kwargs["offset"] for call in client.search_acervo_page.call_args_list],
            [0, 2],
        )
        self.assertEqual(
            client.search_acervo_page.call_args_list[0].kwargs["source_fidelities"],
            ["source_text", "verified"],
        )

    def test_quote_scan_stops_after_one_safe_mobile_page(self) -> None:
        first = [
            SimpleNamespace(chunk_id=1, book_id=10, book_file_id=20, pdf_page=1),
            SimpleNamespace(chunk_id=2, book_id=30, book_file_id=40, pdf_page=2),
        ]
        client = SimpleNamespace(
            search_acervo_page=Mock(return_value=SimpleNamespace(
                hits=first, total=200, consumed=2, matching_works=0,
            ))
        )
        with (
            patch("api.routes.search._hydrate_quote_hit_authors", side_effect=lambda hits: hits),
            patch(
                "api.routes.search._filter_quotable_hits_preserving_verified",
                side_effect=lambda hits, *_args, **_kwargs: hits,
            ),
        ):
            scan = _scan_quotable_source_hits(
                client,
                query="qualquer termo",
                author_filter="",
                collection_filter="",
                patristic_book_ids=[],
                max_accepted=2,
            )

        self.assertEqual([hit.chunk_id for hit in scan.hits], [1, 2])
        self.assertFalse(scan.exhausted)
        self.assertEqual(scan.next_offset, 2)
        self.assertEqual(scan.candidate_total, 200)
        self.assertEqual(client.search_acervo_page.call_count, 1)

    def test_quote_scan_never_overfills_the_requested_mobile_page(self) -> None:
        first = [
            SimpleNamespace(chunk_id=index, book_id=index, book_file_id=index, pdf_page=1)
            for index in range(1, 4)
        ]
        second = [
            SimpleNamespace(chunk_id=index, book_id=index, book_file_id=index, pdf_page=1)
            for index in range(4, 6)
        ]
        client = SimpleNamespace(search_acervo_page=Mock(side_effect=[
            SimpleNamespace(hits=first, total=20, consumed=3, matching_works=0),
            SimpleNamespace(hits=second, total=20, consumed=2, matching_works=0),
        ]))
        with (
            patch("api.routes.search._hydrate_quote_hit_authors", side_effect=lambda hits: hits),
            patch(
                "api.routes.search._filter_quotable_hits_preserving_verified",
                side_effect=lambda hits, *_args, **_kwargs: hits,
            ),
        ):
            scan = _scan_quotable_source_hits(
                client,
                query="scriptura",
                author_filter="",
                collection_filter="",
                patristic_book_ids=[],
                max_accepted=5,
            )

        self.assertEqual(len(scan.hits), 5)
        self.assertEqual(
            [call.kwargs["limit"] for call in client.search_acervo_page.call_args_list],
            [5, 2],
        )

    def test_search_cursor_is_bound_to_user_query_and_expiration(self) -> None:
        context = _search_cursor_context(
            query="scriptura",
            author="",
            collection="patristica",
            quotes_only=True,
            user_id=123,
        )
        cursor = _encode_search_cursor(offset=36, context=context, now=1_000)
        self.assertEqual(
            _decode_search_cursor(cursor, expected_context=context, now=1_001),
            36,
        )
        other_user = {**context, "sub": "456"}
        with self.assertRaisesRegex(Exception, "422"):
            _decode_search_cursor(cursor, expected_context=other_user, now=1_001)
        with self.assertRaisesRegex(Exception, "422"):
            _decode_search_cursor(cursor, expected_context=context, now=10_000)

    def test_google_books_digitization_page_is_not_quotable(self) -> None:
        assessment = assess_content(
            "This is a reproduction of a library book that was digitized by Google "
            "as part of an ongoing effort to preserve the information in books and "
            "make it universally accessible. Google books https://books.google.com"
        )
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "digitization_boilerplate")

    def test_verified_store_replaces_ocr_candidate(self) -> None:
        literal = "Utrum vero ipsis et cum Cerinthianis eodem modo convenerit."
        passage = select_verified_passage(
            "Utrum vero ipsis et cum Cerinthianis eodem modo convenerit. OCR lixo",
            "Cerinthianis",
            [VerifiedPassageCandidate(literal, "la")],
        )
        self.assertIsNotNone(passage)
        self.assertEqual(passage.text, literal)

    def test_unrelated_verified_page_cannot_authorize_ocr(self) -> None:
        passage = select_verified_passage(
            "Veruin tenebre contra spir sanctum",
            "tenebre contra",
            [VerifiedPassageCandidate("Utrum vero ipsis et cum Cerinthianis", "la")],
        )
        self.assertIsNone(passage)

    def test_unrelated_query_does_not_inherit_verified_text_inside_large_chunk(self) -> None:
        literal = "Utrum vero ipsis et cum Cerinthianis eodem modo convenerit."
        passage = select_verified_passage(
            "Veruin tenebre contra spir sanctum. " + literal,
            "Veruin tenebre contra spir sanctum",
            [VerifiedPassageCandidate(literal, "la")],
        )
        self.assertIsNone(passage)

    def test_chunker_never_crosses_a_pdf_page(self) -> None:
        pages = [
            {
                "page_number": 10,
                "text": "prima " * 700,
                "extraction_method": "ocr",
                "source_fidelity": "unverified_ocr",
            },
            {
                "page_number": 11,
                "text": "secunda " * 700,
                "extraction_method": "digital_text",
                "source_fidelity": "source_text",
            },
        ]
        chunks = Chunker().chunk(pages, {})
        self.assertTrue(chunks)
        self.assertFalse(any("prima" in row["text"] and "secunda" in row["text"] for row in chunks))
        self.assertEqual(
            {row["source_fidelity"] for row in chunks if row["pdf_page"] == 10},
            {"unverified_ocr"},
        )
        self.assertEqual(
            {row["source_fidelity"] for row in chunks if row["pdf_page"] == 11},
            {"source_text"},
        )

    def test_audit_promotes_only_complete_same_page_literal_match(self) -> None:
        chunks = [
            SimpleNamespace(id=1, pdf_page=4, text="Deus caritas est."),
            SimpleNamespace(id=2, pdf_page=5, text="Deus caritas est."),
            SimpleNamespace(id=3, pdf_page=4, text="Deus charitas est."),
        ]
        matched, reasons = _exact_page_matches(
            chunks,
            [{"page_number": 4, "text": "Initium. Deus caritas est. Finis."}],
        )
        self.assertEqual(matched, [1])
        self.assertEqual(reasons["empty_source_page"], 1)
        self.assertEqual(reasons["wording_differs_from_pdf_text_layer"], 1)

    def test_digital_candidate_accepts_only_exact_same_page_text_layer(self) -> None:
        pages = [
            {"page_number": 1, "text": "Verbum caro factum est. Et habitavit in nobis."},
            {"page_number": 2, "text": "Gratia Domini nostri Iesu Christi."},
        ]
        chunks = Chunker().chunk(pages, {})
        report = _validate_source_chunks(chunks, pages)
        self.assertEqual(report["chunks"], len(chunks))
        self.assertEqual(report["same_page_exact_chunks"], len(chunks))

        chunks[0]["text"] = "Veruin caro factum est."
        with self.assertRaisesRegex(RuntimeError, "not exact same-page PDF text"):
            _validate_source_chunks(chunks, pages)

    def test_full_page_images_make_hidden_text_layer_untrusted(self) -> None:
        pages = [
            SimpleNamespace(
                width=100,
                height=200,
                images=[{"x0": 0, "x1": 100, "top": 0, "bottom": 200}],
            )
            for _ in range(4)
        ]
        self.assertTrue(PDFExtractor()._looks_scanned(pages))

    def test_agent_does_not_publish_legacy_translation(self) -> None:
        context = PipelineContext(user_task="Confira esta citação")
        context.findings["source"] = {
            "status": "found",
            "chunk_id": 123,
            "located_excerpt": "Verbum caro factum est.",
        }
        result = TranslationAgent().run(context)
        self.assertFalse(result.data["translation_found"])
        self.assertIsNone(result.data["translation_text"])
        self.assertIn("ainda não verificadas", result.data["fidelity_verdict"])

    def test_verified_chunk_does_not_authorize_neighbor_window(self) -> None:
        chunk = SimpleNamespace(
            source_fidelity="verified",
            text="Verbum caro factum est.",
        )
        authoritative = _authoritative_source_text(
            None,
            chunk,
            "OCR corruptum",
            "Verbum caro factum est. OCR corruptum",
        )
        self.assertEqual(authoritative, ("Verbum caro factum est.", "verified"))

    def test_agent_recognizes_exact_quote_inside_verified_passage(self) -> None:
        context = PipelineContext(user_task="Confira esta citação")
        context.findings.update({
            "quote": "sanctum de Maria Virgine genitum esse fateantur",
            "source": {
                "status": "found",
                "located_excerpt": (
                    "Utrum vero ipsis et cum Cerinthianis. Per Spiritum "
                    "sanctum de Maria Virgine genitum esse fateantur."
                ),
                "confidence": 1.0,
                "author_match": True,
                "match_strategy": "user_query",
                "language": "la",
                "source_fidelity": "verified_transcription",
            },
            "search_candidates": [{"text_score": 1.0, "semantic_score": 0.0}],
        })
        result = CitationVerifierAgent().run(context)
        self.assertTrue(result.data["exact_match"])
        self.assertEqual(result.data["similarity"], 1.0)



if __name__ == "__main__":
    unittest.main()
