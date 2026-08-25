import unittest
from types import SimpleNamespace
from unittest.mock import patch

from confidence.classifier import DeterministicClassifier
from confidence.explainer import ResultExplainer
from confidence.scorer import CombinedScorer
from models.database import Book, Chunk, Translation
from schemas.citation import VerifyCitationRequest
from services.verification_service import (
    VerificationService,
    _extract_matching_excerpt,
    _is_exact_text_match,
    _normalize_for_search,
    _normalize_for_search_with_offsets,
)


IRENAEUS_QUOTE = (
    "Mas visto que seria coisa bastante longa elencar, numa obra como esta, as "
    "sucessões de todas as igrejas, limitar-nos-emos à maior e mais antiga e "
    "conhecida por todos, à igreja fundada e constituída em Roma, pelos dois "
    "gloriosíssimos apóstolos, Pedro e Paulo, e, indicando a sua tradição"
)


class MatchingExcerptTests(unittest.TestCase):
    def test_pdf_line_wrap_hyphens_do_not_downgrade_an_exact_quote(self) -> None:
        copied_pdf_text = IRENAEUS_QUOTE.replace("homens", "ho-mens").replace(
            "enfatua\u00e7\u00e3o", "enfa-tua\u00e7\u00e3o"
        )

        self.assertTrue(_is_exact_text_match(IRENAEUS_QUOTE, copied_pdf_text))
        self.assertEqual(
            _normalize_for_search(IRENAEUS_QUOTE),
            _normalize_for_search(copied_pdf_text),
        )

    def test_verifier_uses_the_full_indexed_window_again(self) -> None:
        author = "Santo Irineu de Li\u00e3o"
        book = SimpleNamespace(
            id=20,
            author=author,
            canonical_author=author,
            title="Contra as Heresias",
            collection="Patristica PT",
            language="Portuguese",
            edition_label="Edicao em portugues",
            source_label="PDF indexado",
            is_primary_source=True,
        )
        chunk = SimpleNamespace(
            id=10,
            book_id=book.id,
            book_file_id=None,
            chunk_author=None,
            text="parte interna do trecho",
            source_fidelity="unverified_ocr",
            sequence_index=41,
            volume=4,
            column_start=None,
            column_end=None,
            chapter_or_section="III, 3, 2",
            pdf_page=147,
            visual_anchor=None,
        )
        db = _FakeDb(chunk, book)
        service = _verification_service_with_hit(chunk.id)

        with (
            patch("services.verification_service.SessionLocal", return_value=db),
            patch("services.verification_service._chunk_window_text", return_value=IRENAEUS_QUOTE),
        ):
            result = service.verify(
                VerifyCitationRequest(quote=IRENAEUS_QUOTE, attributed_to=author)
            )

        self.assertEqual(result.status_code, "CONFIRMADA_EXATA")
        self.assertEqual(result.confidence, "Alta")
        self.assertEqual(result.work, "Contra as Heresias")
        self.assertEqual(result.reference.pdf_page, 147)
        self.assertEqual(
            _normalize_for_search(result.matched_excerpt),
            _normalize_for_search(IRENAEUS_QUOTE),
        )

    def test_verifier_uses_indexed_portuguese_translation_again(self) -> None:
        author = "Santo Irineu de Li\u00e3o"
        book = SimpleNamespace(
            id=20,
            author=author,
            canonical_author=author,
            title="Adversus Haereses",
            collection="PG",
            language="Latin",
            edition_label="Edicao latina",
            source_label="PDF indexado",
            is_primary_source=True,
        )
        chunk = SimpleNamespace(
            id=10,
            book_id=book.id,
            book_file_id=None,
            chunk_author=None,
            text="Hanc traditionem ab apostolis.",
            source_fidelity="unverified_ocr",
            sequence_index=41,
            volume=7,
            column_start=848,
            column_end=849,
            chapter_or_section="III, 3, 2",
            pdf_page=147,
            visual_anchor=None,
        )
        translation = SimpleNamespace(
            chunk_id=chunk.id,
            language="pt",
            text=IRENAEUS_QUOTE,
            translator="Tradutor da edicao",
            edition_label="Edicao em portugues",
        )
        db = _FakeDb(chunk, book, translation=translation)
        service = _verification_service_with_hit(chunk.id)

        with (
            patch("services.verification_service.SessionLocal", return_value=db),
            patch("services.verification_service._chunk_window_text", return_value=chunk.text),
        ):
            result = service.verify(
                VerifyCitationRequest(quote=IRENAEUS_QUOTE, attributed_to=author)
            )

        self.assertEqual(result.status_code, "TRADUCAO_FIEL")
        self.assertEqual(result.matched_translation, IRENAEUS_QUOTE)


class _FakeQuery:
    def __init__(self, first_value=None) -> None:
        self.first_value = first_value

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.first_value

    def all(self):
        return []


class _FakeDb:
    def __init__(self, chunk, book, *, translation=None) -> None:
        self.chunk = chunk
        self.book = book
        self.translation = translation

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, model, object_id):
        if model is Chunk and object_id == self.chunk.id:
            return self.chunk
        if model is Book and object_id == self.book.id:
            return self.book
        return None

    def query(self, model):
        if model is Translation:
            return _FakeQuery(self.translation)
        return _FakeQuery()


def _verification_service_with_hit(chunk_id: int) -> VerificationService:
    service = object.__new__(VerificationService)
    service.text_search = SimpleNamespace(
        search=lambda *_args, **_kwargs: [
            SimpleNamespace(chunk_id=chunk_id, score=1.0, excerpt="")
        ]
    )
    service.semantic_search = SimpleNamespace(search=lambda *_args, **_kwargs: [])
    service.scorer = CombinedScorer()
    service.classifier = DeterministicClassifier()
    service.explainer = ResultExplainer()
    return service


class ExistingMatchingExcerptTests(unittest.TestCase):
    def test_normalization_with_offsets_matches_canonical_normalization(self) -> None:
        source = "fé.3 — À Igreja\n147\nPedro e Paulo; tradição. ΟΣ"

        normalized, offsets = _normalize_for_search_with_offsets(source)

        self.assertEqual(normalized, _normalize_for_search(source))
        self.assertEqual(len(offsets), len(normalized))
        self.assertEqual(source[offsets[normalized.index("igreja")]], "I")
        self.assertTrue(normalized.endswith("ος"))

    def test_exact_excerpt_uses_source_offsets_instead_of_global_ratio(self) -> None:
        # PDF layout noise collapses almost completely during normalization. The
        # old global ratio mapped the valid match back into this earlier passage.
        earlier_passage = (
            "2,3. Nossa batalha, caríssimo, é contra estes, que escorregadios "
            "como serpentes, tentam se esgueirar de todos os lados. Por isso, "
            "de todos os lados lhes devemos resistir. "
        )
        layout_noise = ("[147] • — \n" * 700) + earlier_passage
        trailing_layout_noise = ("\n— [148] • seção —" * 900) + " fim da página."
        source = (
            layout_noise
            + "3,2. "
            + IRENAEUS_QUOTE
            + " recebida dos apóstolos."
            + trailing_layout_noise
        )

        excerpt = _extract_matching_excerpt(IRENAEUS_QUOTE, source)

        self.assertEqual(
            _normalize_for_search(excerpt),
            _normalize_for_search(IRENAEUS_QUOTE),
        )
        self.assertNotIn("Nossa batalha", excerpt)
        self.assertNotIn("escorregadios como serpentes", excerpt)
        self.assertTrue(excerpt.startswith("Mas visto que"))
        self.assertTrue(excerpt.endswith("sua tradição"))

    def test_exact_excerpt_preserves_pdf_page_number_inside_match(self) -> None:
        query = "a igreja fundada e constituída em Roma pelos apóstolos"
        source = (
            "Contexto anterior. a igreja fundada e 147 constituída em Roma "
            "pelos apóstolos. Depois."
        )

        excerpt = _extract_matching_excerpt(query, source)

        self.assertEqual(
            excerpt,
            "a igreja fundada e 147 constituída em Roma pelos apóstolos",
        )
        self.assertEqual(_normalize_for_search(excerpt), _normalize_for_search(query))

    def test_punctuation_only_query_does_not_crash(self) -> None:
        source = "Texto da fonte sem uma correspondência utilizável."

        excerpt = _extract_matching_excerpt("...", source)

        self.assertEqual(excerpt, source)


if __name__ == "__main__":
    unittest.main()
