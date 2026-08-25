import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from services.catechism_concordance_service import (
    CatechismConcordanceService,
    CatechismSourceRef,
    CatechismUnit,
    _units_with_exact_pdf_pages,
    parse_catechism_units,
)
from services.ccc_commentary_service import CccArticleQuery, CccQueryMode


def context(article: int, text: str) -> CccArticleQuery:
    return CccArticleQuery(
        article=article,
        section_title="Seção",
        section_start=article,
        section_end=article,
        mode=CccQueryMode.EXACT_ARTICLE,
        query=text,
        article_text=text,
        article_fingerprint="fingerprint",
        key_terms=tuple(text.split()[:8]),
        quoted_phrases=(),
        scripture_references=(),
        patristic_mentions=(),
        source_book_id=1999,
        source_chunk_ids=(9000,),
        source_pages=(100,),
    )


def unit(
    source: str,
    number: int,
    question: str,
    answer: str,
    *,
    refs=(),
) -> CatechismUnit:
    book_id = 1996 if source == "compendium" else 1997
    return CatechismUnit(
        catechism=source,
        question_number=number,
        question=question,
        answer=answer,
        ccc_ranges=tuple(refs),
        source_title=(
            "Compêndio do Catecismo da Igreja Católica"
            if source == "compendium"
            else "Catecismo de São Pio X"
        ),
        source_author="Igreja Católica" if source == "compendium" else "São Pio X",
        source=CatechismSourceRef(
            book_id=book_id,
            book_file_id=book_id + 1000,
            chunk_ids=(number,),
            pages=(number // 5 + 1,),
            edition_label=None,
            language="pt",
        ),
    )


class FixedSource:
    def __init__(self, compendium=(), pio_x=()):
        self.values = {
            "compendium": tuple(compendium),
            "pio_x": tuple(pio_x),
        }

    def get_units(self, catechism):
        return self.values.get(catechism)

    def source_error(self, catechism):
        return None


class CatechismParserTests(unittest.TestCase):
    def test_pdf_question_marker_replaces_the_chunk_start_page(self):
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf

        source_unit = unit(
            "compendium",
            534,
            "O que é a oração?",
            "A oração consiste em elevar a alma a Deus.",
            refs=((2558, 2565),),
        )
        source_unit = CatechismUnit(
            **{
                **source_unit.__dict__,
                "source": CatechismSourceRef(
                    **{**source_unit.source.__dict__, "pages": (107,)}
                ),
            }
        )
        with TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "compendium.pdf"
            document = pymupdf.open()
            document.new_page().insert_text((72, 72), "Texto da pagina anterior.")
            document.new_page().insert_text(
                (72, 72),
                "534. O que e a oracao? 2558-2565 A oracao consiste em elevar a alma a Deus.",
            )
            document.save(pdf_path)
            document.close()

            resolved = _units_with_exact_pdf_pages("compendium", (source_unit,), str(pdf_path))

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].source.pages, (2,))

    def test_pdf_page_resolver_accepts_question_at_end_of_physical_page(self):
        """The final question line has no trailing whitespace in PDF text."""

        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf

        source_unit = unit(
            "pio_x",
            130,
            "Que nos ensina o oitavo artigo do Credo: creio no Espírito Santo?",
            "O oitavo artigo ensina-nos que existe o Espírito Santo.",
        )
        source_unit = CatechismUnit(
            **{
                **source_unit.__dict__,
                "source": CatechismSourceRef(
                    **{**source_unit.source.__dict__, "pages": (27,)}
                ),
            }
        )
        with TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "pio-x.pdf"
            document = pymupdf.open()
            document.new_page().insert_text((72, 72), "Texto da pagina anterior.")
            document.new_page().insert_text(
                (72, 72),
                "130) Que nos ensina o oitavo artigo do Credo: creio no Espirito Santo?",
            )
            document.save(pdf_path)
            document.close()

            resolved = _units_with_exact_pdf_pages("pio_x", (source_unit,), str(pdf_path))

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].source.pages, (2,))

    def test_pdf_page_resolver_includes_answer_continuing_on_next_page(self):
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf

        source_unit = unit(
            "pio_x",
            130,
            "Que nos ensina o oitavo artigo do Credo: creio no Espirito Santo?",
            "O oitavo artigo ensina-nos que existe o Espirito Santo, terceira Pessoa da Trindade.",
        )
        with TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "pio-x-split-answer.pdf"
            document = pymupdf.open()
            document.new_page().insert_text(
                (72, 72),
                "130) Que nos ensina o oitavo artigo do Credo: creio no Espirito Santo?",
            )
            document.new_page().insert_text(
                (72, 72),
                "O oitavo artigo ensina-nos que existe o Espirito Santo, terceira Pessoa "
                "da Trindade. 131) De quem procede o Espirito Santo? O Espirito Santo "
                "procede do Padre e do Filho.",
            )
            document.save(pdf_path)
            document.close()

            resolved = _units_with_exact_pdf_pages("pio_x", (source_unit,), str(pdf_path))

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].source.pages, (1, 2))

    def test_pdf_page_resolver_handles_question_itself_split_across_pages(self):
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf

        source_unit = unit(
            "compendium",
            534,
            "O que e a oracao?",
            "A oracao consiste em elevar a alma a Deus.",
            refs=((2558, 2565),),
        )
        with TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "compendium-split-question.pdf"
            document = pymupdf.open()
            document.new_page().insert_text((72, 72), "534. O que e a")
            document.new_page().insert_text(
                (72, 72),
                "oracao? 2558-2565 A oracao consiste em elevar a alma a Deus. "
                "535. Por que devemos rezar? Porque Deus nos chama a comunhao.",
            )
            document.save(pdf_path)
            document.close()

            resolved = _units_with_exact_pdf_pages("compendium", (source_unit,), str(pdf_path))

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].source.pages, (1, 2))

    def test_pdf_page_resolver_stops_last_question_before_appendix(self):
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf

        source_unit = unit(
            "compendium",
            598,
            "O que significa o Amen final?",
            "Acabada a oracao, dizemos Amen, que significa Assim seja.",
            refs=((2855, 2856), (2865, 2865)),
        )
        with TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "compendium-last-question.pdf"
            document = pymupdf.open()
            document.new_page().insert_text(
                (72, 72),
                "598. O que significa o Amen final? 2855-2856 2865 Acabada a "
                "oracao, dizemos Amen, que significa Assim seja. APENDICE "
                "ORACOES COMUNS Sinal da Cruz e outras oracoes.",
            )
            document.new_page().insert_text(
                (72, 72),
                "Pai nosso e outras oracoes. Assim seja. Amen.",
            )
            document.save(pdf_path)
            document.close()

            resolved = _units_with_exact_pdf_pages("compendium", (source_unit,), str(pdf_path))

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].source.pages, (1,))

    def test_pdf_page_resolver_does_not_extend_into_reading_before_next_question(self):
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf

        source_unit = unit(
            "pio_x",
            244,
            "Como serao os corpos dos condenados?",
            "Os corpos dos condenados trarao o estigma da reprovacao eterna.",
        )
        with TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "pio-x-reading.pdf"
            document = pymupdf.open()
            document.new_page().insert_text(
                (72, 72),
                "244) Como serao os corpos dos condenados? Os corpos dos condenados "
                "trarao o estigma da reprovacao eterna.",
            )
            document.new_page().insert_text(
                (72, 72),
                "CAPITULO XIII Leitura sobre corpos, condenados e vida eterna.",
            )
            document.new_page().insert_text(
                (72, 72),
                "245) Que nos ensina o ultimo artigo do Credo? Ele ensina a vida eterna.",
            )
            document.save(pdf_path)
            document.close()

            resolved = _units_with_exact_pdf_pages("pio_x", (source_unit,), str(pdf_path))

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].source.pages, (1,))

    def test_pio_parser_does_not_swallow_question_after_numbered_creed(self):
        row = SimpleNamespace(
            id=700,
            book_id=2000,
            book_file_id=4000,
            pdf_page=8,
            text=(
                "18) Dizei-os. 1) Creio em Deus Padre. 12) Na vida eterna. Amém. "
                "19) Que quer dizer a palavra Credo? Credo quer dizer que tenho por "
                "verdadeiro tudo o que Deus revelou. "
                "20) Quem revelou estas verdades? Deus revelou estas verdades à Igreja."
            ),
        )
        units = parse_catechism_units(
            "pio_x",
            [row],
            source_title="Catecismo de São Pio X",
            source_author="São Pio X",
            edition_label=None,
            language="pt",
            book_file_id=4000,
        )

        self.assertEqual([entry.question_number for entry in units], [19, 20])
        self.assertTrue(units[0].question.startswith("Que quer dizer"))

    def test_compendium_parser_accepts_quoted_question_and_scripture_citation(self):
        row = SimpleNamespace(
            id=701,
            book_id=1996,
            book_file_id=3960,
            pdf_page=89,
            text=(
                "434. «Mestre, que devo fazer de bom para alcançar a vida eterna?» "
                "(Mt 19,16) 2052-2054; 2075-2076 Jesus responde: observa os "
                "mandamentos e segue-me."
            ),
        )
        units = parse_catechism_units(
            "compendium",
            [row],
            source_title="Compêndio",
            source_author="Igreja Católica",
            edition_label=None,
            language="pt",
            book_file_id=3960,
        )

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].question_number, 434)
        self.assertEqual(units[0].ccc_ranges, ((2052, 2054), (2075, 2076)))

    def test_compendium_parser_separates_question_number_from_ccc_references(self):
        row = SimpleNamespace(
            id=62164,
            book_id=1996,
            book_file_id=3960,
            pdf_page=16,
            text=(
                "44. Qual é o mistério central da fé e da vida cristã? 232-237 "
                "O mistério central da fé e da vida cristã é a Santíssima Trindade. "
                "45. Pode a razão conhecer sozinha este mistério? 237 "
                "about:blank 16/142 09/02/25, 09:38 about:blank "
                "A Trindade só pode ser conhecida porque Deus a revelou. "
                "CAPÍTULO PRIMEIRO A REVELAÇÃO DIVINA"
            ),
        )
        units = parse_catechism_units(
            "compendium",
            [row],
            source_title="Compêndio",
            source_author="Igreja Católica",
            edition_label=None,
            language="pt",
            book_file_id=3960,
        )
        self.assertEqual([entry.question_number for entry in units], [44, 45])
        self.assertEqual(units[0].ccc_ranges, ((232, 237),))
        self.assertNotIn("232-237", units[0].answer)
        self.assertEqual(units[1].ccc_ranges, ((237, 237),))
        self.assertNotIn("about:blank", units[1].answer)
        self.assertNotIn("CAPÍTULO", units[1].answer)

    def test_compendium_parser_keeps_multiple_printed_ccc_references(self):
        row = SimpleNamespace(
            id=62164,
            book_id=1996,
            book_file_id=3960,
            pdf_page=16,
            text=(
                "48. Como exprime a Igreja a sua fé trinitária? 249-256 266 "
                "A Igreja confessa um só Deus em três Pessoas divinas."
            ),
        )
        units = parse_catechism_units(
            "compendium",
            [row],
            source_title="Compêndio",
            source_author="Igreja Católica",
            edition_label=None,
            language="pt",
            book_file_id=3960,
        )
        self.assertEqual(units[0].ccc_ranges, ((249, 256), (266, 266)))

    def test_compendium_parser_cuts_uppercase_heading_after_answer(self):
        row = SimpleNamespace(
            id=62157,
            book_id=1996,
            book_file_id=3960,
            pdf_page=8,
            text=(
                "10. Qual o valor das revelações privadas? 67 "
                "Elas podem ajudar a viver a fé, se forem orientadas para Cristo. "
                "A TRANSMISSÃO DA REVELAÇÃO DIVINA "
                "11. Porquê e como deve ser transmitida a Revelação? 74 "
                "Deus quer que todos os homens sejam salvos."
            ),
        )
        units = parse_catechism_units(
            "compendium",
            [row],
            source_title="Compêndio",
            source_author="Igreja Católica",
            edition_label=None,
            language="pt",
            book_file_id=3960,
        )
        self.assertEqual(units[0].answer, "Elas podem ajudar a viver a fé, se forem orientadas para Cristo.")

    def test_pio_x_parser_preserves_its_own_question_number(self):
        row = SimpleNamespace(
            id=63499,
            book_id=1997,
            book_file_id=3961,
            pdf_page=120,
            text=(
                "670) Que é a Penitência? A Penitência é o Sacramento instituído "
                "por Jesus Cristo para perdoar os pecados cometidos depois do Batismo. "
                "671) Quantas partes tem a Penitência? A Penitência tem as partes necessárias."
            ),
        )
        units = parse_catechism_units(
            "pio_x",
            [row],
            source_title="Catecismo de São Pio X",
            source_author="São Pio X",
            edition_label=None,
            language="pt",
            book_file_id=3961,
        )
        self.assertEqual([entry.question_number for entry in units], [670, 671])
        self.assertEqual(units[0].ccc_ranges, ())

    def test_parser_rejects_a_chunk_that_cuts_the_answer_mid_sentence(self):
        row = SimpleNamespace(
            id=999,
            book_id=1996,
            book_file_id=3960,
            pdf_page=88,
            text="349. Que significa esta doutrina? 1666 Esta situação perdura enquanto que",
        )
        units = parse_catechism_units(
            "compendium",
            [row],
            source_title="Compêndio",
            source_author="Igreja Católica",
            edition_label=None,
            language="pt",
            book_file_id=3960,
        )
        self.assertEqual(units, ())


class ConcordanceTests(unittest.TestCase):
    def setUp(self):
        self.compendium = (
            unit("compendium", 44, "Qual é o mistério central da fé?", "É o mistério da Santíssima Trindade.", refs=((232, 237),)),
            unit("compendium", 85, "Porque o Filho de Deus se fez homem?", "O Filho de Deus encarnou para nos tornar participantes da natureza divina.", refs=((456, 460),)),
            unit("compendium", 233, "Quem actua na liturgia?", "Na liturgia actua Cristo total.", refs=((1135, 1186),)),
            unit("compendium", 274, "O que significa a Eucaristia?", "É fonte e cume da vida cristã.", refs=((1324, 1327), (1407, 1407))),
            unit("compendium", 296, "Como é chamado este sacramento?", "É chamado Penitência, Reconciliação, Perdão e Confissão.", refs=((1422, 1424),)),
            unit("compendium", 534, "O que é a oração?", "A oração consiste em elevar a alma a Deus.", refs=((2558, 2565), (2590, 2590))),
        )
        self.pio = (
            unit("pio_x", 68, "Que nos ensina o segundo artigo do Credo?", "O Filho de Deus se fez homem para nos salvar."),
            unit("pio_x", 130, "Que nos ensina o oitavo artigo do Credo?", "O Espírito Santo é a terceira Pessoa da Santíssima Trindade."),
            unit("pio_x", 253, "Que é a oração?", "A oração é uma elevação da alma a Deus."),
            unit("pio_x", 594, "Que é o Sacramento da Eucaristia?", "A Eucaristia contém verdadeira e substancialmente o Corpo e Sangue de Jesus Cristo."),
            unit("pio_x", 670, "Que é a Penitência?", "É o Sacramento instituído para o perdão dos pecados e a reconciliação."),
            unit("pio_x", 983, "Como podemos rezar durante o dia?", "Podemos elevar o coração a Deus com orações breves."),
        )
        self.service = CatechismConcordanceService(FixedSource(self.compendium, self.pio))

    def test_explicit_compendium_links_cover_representative_ccc_paragraphs(self):
        samples = {
            233: ("Santíssima Trindade", 44),
            460: ("natureza divina", 85),
            1324: ("Eucaristia fonte e ápice da vida cristã", 274),
            1422: ("Penitência, perdão, reconciliação e confissão", 296),
            2558: ("A relação viva com Deus é a oração", 534),
        }
        for article, (text, expected_question) in samples.items():
            with self.subTest(article=article):
                comparison = self.service.find_comparisons(context(article, text))[0]
                self.assertEqual(comparison.status, "matched")
                self.assertEqual(comparison.match.kind, "explicit_cross_reference")
                self.assertEqual(comparison.passage.locator, f"Pergunta {expected_question}")

    def test_ccc_233_never_uses_compendium_question_233_by_number_coincidence(self):
        comparison = self.service.find_comparisons(
            context(233, "Pai, Filho e Espírito Santo: a Santíssima Trindade")
        )[0]
        self.assertEqual(comparison.passage.locator, "Pergunta 44")
        self.assertNotEqual(comparison.passage.locator, "Pergunta 233")

    def test_pio_x_is_labeled_thematic_and_keeps_its_number(self):
        comparison = self.service.find_comparisons(
            context(1422, "sacramento da Penitência, perdão, reconciliação e conversão")
        )[1]
        self.assertEqual(comparison.status, "matched")
        self.assertEqual(comparison.match.kind, "thematic")
        self.assertEqual(comparison.passage.locator, "Pergunta 670")

    def test_verified_pio_x_crosswalk_covers_only_reviewed_ranges(self):
        expected = {
            233: 130,
            460: 68,
            1324: 594,
            1422: 670,
            2558: 253,
        }
        for article, question in expected.items():
            with self.subTest(article=article):
                comparison = self.service.find_comparisons(
                    context(article, f"Doutrina católica do parágrafo {article}")
                )[1]
                self.assertEqual(comparison.status, "matched")
                self.assertEqual(comparison.passage.locator, f"Pergunta {question}")

        for article in (1, 50, 455, 461, 2566, 2865):
            with self.subTest(unlisted_article=article):
                comparison = self.service.find_comparisons(
                    context(article, "Texto sem correspondência manual verificada")
                )[1]
                self.assertEqual(comparison.status, "no_reliable_match")
                self.assertIsNone(comparison.passage)

    def test_roman_catechism_fails_closed_until_reocr(self):
        comparison = self.service.find_comparisons(context(1324, "Eucaristia"))[-1]
        self.assertEqual(comparison.source, "roman")
        self.assertEqual(comparison.status, "source_unavailable")
        self.assertIn("OCR", comparison.message)

    def test_missing_exact_ccc_context_is_rejected(self):
        broken = context(1422, "")
        broken = CccArticleQuery(**{**broken.__dict__, "mode": CccQueryMode.SOURCE_UNAVAILABLE})
        with self.assertRaises(ValueError):
            self.service.find_comparisons(broken)


if __name__ == "__main__":
    unittest.main()
