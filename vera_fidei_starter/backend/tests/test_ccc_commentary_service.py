import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from services.ccc_commentary_service import (
    CccArticle,
    CccCommentaryService,
    CccCorpus,
    PdfCccCorpus,
    CccQueryMode,
    CccSourceChunk,
    clean_ccc_article_text,
    derive_query_from_exact_article,
)


class DictArticleSource:
    def __init__(self, articles):
        self.articles = articles

    def get_article(self, article):
        return self.articles.get(article)


class RecordingSearchClient:
    def __init__(self, hits=()):
        self.hits = list(hits)
        self.calls = []
        self.last_method = None

    def search_acervo(self, **kwargs):
        self.last_method = "lexical"
        self.calls.append(kwargs)
        return list(self.hits)

    def search_acervo_hybrid(self, **kwargs):
        self.last_method = "hybrid"
        self.calls.append(kwargs)
        return list(self.hits)


class FixedPatristicFilter:
    def __init__(self, allowed, book_ids=(7001, 7002)):
        self.allowed = set(allowed)
        self.book_ids = list(book_ids)
        self.calls = []

    def patristic_book_ids(self):
        return list(self.book_ids)

    def allowed_chunk_ids(self, chunk_ids):
        self.calls.append(tuple(chunk_ids))
        return set(chunk_ids) & self.allowed


@dataclass
class FakeHit:
    chunk_id: int
    collection: str
    author: str
    text: str = ""


def article(number, text, *, chunk_id=None, page=None):
    return CccArticle(
        number=number,
        text=text,
        source_book_id=1999,
        source_chunk_ids=(chunk_id or number,),
        source_pages=(page or number,),
    )


class CccCorpusTests(unittest.TestCase):
    def test_pdf_corpus_uses_typography_to_exclude_headings_pages_and_tables(self):
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf

        with TemporaryDirectory() as directory:
            path = Path(directory) / "ccc.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text((40, 50), "ARTIGO 1: A REVELAÇÃO DE DEUS", fontsize=14, fontname="hebo")
            page.insert_text((40, 80), "1. O homem é capaz de Deus e responde pela fé.", fontsize=12)
            page.insert_text((40, 100), "Esta continuação pertence ao mesmo parágrafo.", fontsize=12)
            page.insert_text((40, 120), "(Parágrafos relacionados: 2,3)", fontsize=12)
            page.insert_text((40, 140), "TÍTULO EDITORIAL", fontsize=12, fontname="hebo")
            page.insert_text((40, 160), "Epígrafe que não pertence ao parágrafo.", fontsize=10)
            page.insert_text((40, 180), "2. O segundo parágrafo permanece íntegro.", fontsize=12)
            page.insert_text((40, 200), "1", fontsize=12)
            document.save(path)
            document.close()

            corpus = PdfCccCorpus(str(path), book_id=1999, chunk_ids=(1, 2))

        first = corpus.get_article(1)
        second = corpus.get_article(2)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(
            first.text,
            "O homem é capaz de Deus e responde pela fé. "
            "Esta continuação pertence ao mesmo parágrafo.",
        )
        self.assertEqual(second.text, "O segundo parágrafo permanece íntegro.")
        self.assertEqual(first.source_pages, (1,))
        self.assertEqual(first.source_chunk_ids, ())

    def test_pdf_corpus_keeps_cross_page_continuation_after_terminal_punctuation(self):
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf

        with TemporaryDirectory() as directory:
            path = Path(directory) / "ccc-cross-page.pdf"
            document = pymupdf.open()
            first_page = document.new_page()
            first_page.insert_text((40, 60), "1. A primeira frase termina nesta página.", fontsize=12)
            first_page.insert_text((280, 800), "1", fontsize=12)
            second_page = document.new_page()
            second_page.insert_text(
                (40, 60),
                "A segunda frase ainda pertence ao mesmo parágrafo.",
                fontsize=12,
            )
            second_page.insert_text((40, 90), "2. O próximo parágrafo começa aqui.", fontsize=12)
            document.save(path)
            document.close()

            corpus = PdfCccCorpus(str(path), book_id=1999)

        self.assertEqual(
            corpus.get_article(1).text,
            "A primeira frase termina nesta página. "
            "A segunda frase ainda pertence ao mesmo parágrafo.",
        )
        self.assertEqual(corpus.get_article(1).source_pages, (1, 2))

    def test_pdf_corpus_embedded_heading_allow_list_is_source_specific(self):
        self.assertTrue(PdfCccCorpus._is_inline_heading(205, '"Eu sou AQUELE QUE É"'))
        self.assertTrue(PdfCccCorpus._is_inline_heading(1471, "QUE É A INDULGÊNCIA?"))
        self.assertFalse(PdfCccCorpus._is_inline_heading(2558, "O QUE É A ORAÇÃO?"))

    def test_cleans_navigation_matter_without_removing_paragraph_content(self):
        text = clean_ccc_article_text(
            'O Verbo se fez carne. (Parágrafos relacionados: 1265,1391) '
            '"O Filho de Deus se fez homem para nos fazer Deus." II. A Encarnação'
        )
        self.assertEqual(
            text,
            'O Verbo se fez carne. "O Filho de Deus se fez homem para nos fazer Deus."',
        )

    def test_cleans_page_footer_and_following_section_heading(self):
        text = clean_ccc_article_text(
            'São reconciliados com a Igreja. 201 I. Como se chama este sacramento?'
        )
        self.assertEqual(text, 'São reconciliados com a Igreja.')

    def test_cleans_all_caps_heading_and_its_epigraph(self):
        text = clean_ccc_article_text(
            'Essa relação é a oração. O QUE É A ORAÇÃO? '
            'Para mim, a oração é um impulso do coração. A oração como dom de Deus'
        )
        self.assertEqual(text, 'Essa relação é a oração.')

    def test_preserves_a_question_that_belongs_to_the_same_ccc_paragraph(self):
        text = (
            'A doutrina e a prática das indulgências estão ligadas ao sacramento. '
            'QUE É A INDULGÊNCIA? A indulgência é a remissão, diante de Deus, '
            'da pena temporal devida aos pecados já perdoados quanto à culpa.'
        )
        self.assertEqual(clean_ccc_article_text(text), text)

    def test_cleans_only_a_trailing_page_number(self):
        self.assertEqual(clean_ccc_article_text('Que assim seja! 367'), 'Que assim seja!')

    def test_cleans_real_structural_suffixes_from_the_indexed_ccc(self):
        cases = (
            (
                24,
                'As palavras devem ser adaptadas à inteligência dos ouvintes. '
                'ACIMA DE TUDO A CARIDADE 8',
                'As palavras devem ser adaptadas à inteligência dos ouvintes.',
            ),
            (
                49,
                'Os crentes levam a luz do Deus vivo àqueles que o recusam. '
                '14 CAPÍTULO II - DEUS VEM AO ENCONTRO DO HOMEM',
                'Os crentes levam a luz do Deus vivo àqueles que o recusam.',
            ),
            (
                50,
                'Deus revela plenamente seu projeto enviando seu Filho e o Espírito Santo '
                '(Parágrafos relacionados: 36, 1066) '
                'ARTIGO 1: A REVELAÇÃO DE DEUS I. Deus revela seu "projeto benevolente"',
                'Deus revela plenamente seu projeto enviando seu Filho e o Espírito Santo',
            ),
            (
                73,
                'O Filho é a Palavra definitiva do Pai. '
                'ARTIGO 2: A TRANSMISSÃO DA REVELAÇÃO DIVINA',
                'O Filho é a Palavra definitiva do Pai.',
            ),
            (
                100,
                'A interpretação foi confiada ao Papa e aos bispos em comunhão com ele. '
                'ARTIGO 3: A SAGRADA ESCRITURA I. Cristo - Palavra única da Sagrada Escritura',
                'A interpretação foi confiada ao Papa e aos bispos em comunhão com ele.',
            ),
            (
                198,
                'A criação é o começo e o fundamento de todas as obras de Deus. '
                'ARTIGO 1 : "CREIO EM DEUS PAI TODO-PODEROSO, CRIADOR DO CÉU E DA TERRA" '
                'PARÁGRAFO 1 - CREIO EM DEUS',
                'A criação é o começo e o fundamento de todas as obras de Deus.',
            ),
            (
                421,
                'Cristo crucificado e ressuscitado quebrou o poder do Maligno. '
                '65 CAPITULO II - CREIO EM JESUS CRISTO, FILHO ÚNICO DE DEUS '
                'A BOA NOVA: DEUS ENVIOU SEU FILHO',
                'Cristo crucificado e ressuscitado quebrou o poder do Maligno.',
            ),
            (
                1135,
                'A catequese responderá às questões primordiais dos fiéis. '
                'ARTIGO 1: CELEBRAR A LITURGIA DA IGREJA I. Quem celebra?',
                'A catequese responderá às questões primordiais dos fiéis.',
            ),
            (
                667,
                'Cristo intercede sem cessar por nós como mediador '
                'ARTIGO 7: "DONDE VIRÁ JULGAR OS VIVOS E OS MORTOS" '
                'I. Ele voltará na glória',
                'Cristo intercede sem cessar por nós como mediador',
            ),
            (
                750,
                'Atribuímos à bondade de Deus os dons que pôs em sua Igreja. '
                '(Parágrafos relacionados 811, 169) '
                'PARÁGRAFO I - A IGREJA NO DESÍGNIO DE DEUS I. As denominações da Igreja',
                'Atribuímos à bondade de Deus os dons que pôs em sua Igreja.',
            ),
            (
                1699,
                'A vida no Espírito realiza a vocação do homem '
                'CAPÍTULO I- A DIGNIDADE DA PESSOA HUMANA',
                'A vida no Espírito realiza a vocação do homem',
            ),
            (
                2776,
                'A oração manifesta a esperança do Senhor, até que Ele venha: '
                'ARTIGO 2: "PAI NOSSO QUE ESTAIS NO CÉU" '
                'I. "Ousar aproximar-nos com toda a confiança"',
                'A oração manifesta a esperança do Senhor, até que Ele venha:',
            ),
            (
                43,
                'Deus revela ao homem o mistério de sua vontade. RESUMINDO',
                'Deus revela ao homem o mistério de sua vontade.',
            ),
            (
                55,
                'A história da salvação começa no seio da humanidade. A ALIANÇA COM NOÉ',
                'A história da salvação começa no seio da humanidade.',
            ),
        )

        for paragraph, raw, expected in cases:
            with self.subTest(paragraph=paragraph):
                self.assertEqual(clean_ccc_article_text(raw), expected)

    def test_cleans_part_and_section_headings_only_in_the_flattened_tail(self):
        cases = (
            'A fé procura compreender. PRIMEIRA PARTE — A PROFISSÃO DA FÉ',
            'A fé procura compreender. PARTE II - A CELEBRAÇÃO DO MISTÉRIO CRISTÃO',
            'A fé procura compreender. SEGUNDA SEÇÃO — A PROFISSÃO DA FÉ CRISTÃ',
            'A fé procura compreender. SEÇÃO I - A VOCAÇÃO DO HOMEM',
        )
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertEqual(clean_ccc_article_text(raw), 'A fé procura compreender.')

    def test_cleans_real_page_overlap_before_paragraph_2565_heading(self):
        repeated = (
            'viva dos filhos de Deus com seu Pai infinitamente bom, com seu Filho, '
            'Jesus Cristo, e com o Espírito Santo. A vida de oração consiste em estar '
            'habitualmente na presença do Deus três vezes Santo e em comunhão com Ele.'
        )
        body = 'Na Nova Aliança, a oração é a relação ' + repeated
        raw = (
            body
            + ' 332 '
            + repeated
            + ' 332 CAPÍTULO I- A REVELAÇÃO DA ORAÇÃO. VOCAÇÃO UNIVERSAL À ORAÇÃO'
        )

        self.assertEqual(clean_ccc_article_text(raw), body)

    def test_cleans_real_roman_mixed_case_and_bare_heading_suffixes(self):
        cases = (
            (79, 'A palavra de Cristo permanece na Igreja" II. A relação entre a Tradição e a Escritura UMA FONTE COMUM...'),
            (483, 'A união das naturezas realiza-se no Verbo. 74 PARÁGRAFO 2- "...CONCEBIDO PELO ESPÍRITO SANTO"'),
            (598, 'Continuas a crucificá-lo nos pecados. (Parágrafo Relacionado 1851) II. A morte redentora de Cristo'),
            (686, 'A Igreja aguarda a Vida Eterna. (Parágrafo Relacionado 258) Artigo 8: "CREIO NO ESPÍRITO SANTO"'),
            (963, 'Maria é Mãe da Igreja. (Parágrafos relacionados 484-507,721-726) I. A maternidade de Maria'),
            (1083, 'Estas bênçãos produzem frutos de vida (Ef 1,6). II. A obra de Cristo na liturgia'),
            (1513, 'O Senhor alivie teus sofrimentos". II. Quem recebe e quem administra este sacramento?'),
            (2005, 'Se estou, que Deus nela me conserve". III. O mérito'),
            (2173, 'Exultemos e alegremo-nos nele (Sl 117,24). II. O dia do Senhor'),
            (2606, 'Tornou-se princípio de salvação eterna (Hb 5,7-9) JESUS ENSINA A ORAR'),
        )
        for paragraph, raw in cases:
            with self.subTest(paragraph=paragraph):
                cleaned = clean_ccc_article_text(raw)
                self.assertNotRegex(
                    cleaned,
                    r'(?i)\b(?:artigo|capítulo|parágrafo)\s+[IVXLCDM0-9]+|'
                    r'\s[IVXLCDM]+\.\s|JESUS ENSINA A ORAR',
                )

    def test_cleans_complete_heading_prefix_instead_of_only_caps_tail(self):
        raw = (
            'O Espírito habita no coração dos fiéis. '
            '118 As Características do POVO DE DEUS'
        )
        self.assertEqual(
            clean_ccc_article_text(raw),
            'O Espírito habita no coração dos fiéis.',
        )

    def test_real_inline_mentions_survive_while_following_heading_is_removed(self):
        cases = (
            (
                26,
                'Consideraremos a busca (capítulo 1), a Revelação (capítulo II) '
                'e a resposta da fé (capítulo III). CAPÍTULO I - O HOMEM É CAPAZ DE DEUS',
                'Consideraremos a busca (capítulo 1), a Revelação (capítulo II) '
                'e a resposta da fé (capítulo III).',
            ),
            (
                429,
                'Jesus é apresentado no artigo 2; sua Páscoa, nos artigos 4 e 5. '
                '(Parágrafo relacionado: 851) '
                'ARTIGO 2: "E EM JESUS CRISTO, SEU FILHO ÚNICO"',
                'Jesus é apresentado no artigo 2; sua Páscoa, nos artigos 4 e 5.',
            ),
            (
                1700,
                'A dignidade realiza-se na vocação (artigo 2), na liberdade '
                '(artigo 3) e na caridade. ARTIGO 1: O HOMEM IMAGEM DE DEUS',
                'A dignidade realiza-se na vocação (artigo 2), na liberdade '
                '(artigo 3) e na caridade.',
            ),
        )
        for paragraph, raw, expected in cases:
            with self.subTest(paragraph=paragraph):
                self.assertEqual(clean_ccc_article_text(raw), expected)

    def test_cleans_exact_mixed_case_heading_after_navigation(self):
        raw = (
            'O Criador da humanidade nos doou sua própria divindade! '
            '(Parágrafo relacionado: 460) Os MISTÉRIOS DA INFÂNCIA DE JESUS'
        )
        self.assertEqual(
            clean_ccc_article_text(raw),
            'O Criador da humanidade nos doou sua própria divindade!',
        )

        faith = (
            'A Igreja venera em Maria a realização mais pura da fé. '
            '(Parágrafos relacionados: 969,507,829) '
            'II. "Sei em quem pus minha fé" (2Tm 1,12) CRER SOMENTE EM DEUS 26'
        )
        self.assertEqual(
            clean_ccc_article_text(faith),
            'A Igreja venera em Maria a realização mais pura da fé.',
        )

    def test_preserves_parenthetical_prose_and_emphatic_quote(self):
        parenthetical = (
            'Cristo conferiu o poder de perdoar os pecados. '
            '(A Segunda Parte do Catecismo tratará explicitamente deste perdão.) '
            'I. Um só Batismo para o perdão dos pecados'
        )
        self.assertEqual(
            clean_ccc_article_text(parenthetical),
            'Cristo conferiu o poder de perdoar os pecados. '
            '(A Segunda Parte do Catecismo tratará explicitamente deste perdão.)',
        )
        quote = (
            'Compreendi que só o amor fazia os membros da Igreja agirem... '
            'Compreendi que O AMOR ENCERRAVA TODAS AS VOCAÇÕES, QUE O AMOR ERA TUDO!"'
        )
        self.assertEqual(clean_ccc_article_text(quote), quote)

    def test_page_overlap_keeps_the_new_continuation(self):
        repeated = (
            'isto é, de resgate que liberta os homens da escravidão do pecado. '
            'São Paulo, em sua confissão de fé '
        )
        raw = (
            'O projeto de salvação é redenção universal, '
            + repeated
            + '91 '
            + repeated
            + 'professa que Cristo morreu por nossos pecados segundo as Escrituras.'
        )
        cleaned = clean_ccc_article_text(raw)
        self.assertEqual(cleaned.count('isto é, de resgate'), 1)
        self.assertTrue(cleaned.endswith('professa que Cristo morreu por nossos pecados segundo as Escrituras.'))

    def test_century_in_prose_survives_while_terminal_caps_heading_is_removed(self):
        raw = (
            'A prática é atestada explicitamente desde o século II. Mas pode '
            'remontar ao início da pregação apostólica. FÉ E BATISMO'
        )
        self.assertEqual(
            clean_ccc_article_text(raw),
            'A prática é atestada explicitamente desde o século II. Mas pode '
            'remontar ao início da pregação apostólica.',
        )

    def test_removes_quoted_roman_section_heading_without_eating_century_prose(self):
        article = (
            'A fé cristã confessa que Deus é um só. '
            'I. "Creio em um só Deus"'
        )
        self.assertEqual(
            clean_ccc_article_text(article),
            'A fé cristã confessa que Deus é um só.',
        )

        century = (
            'A prática é atestada desde o século II. Mas permaneceu viva '
            'na tradição da Igreja.'
        )
        self.assertEqual(clean_ccc_article_text(century), century)

    def test_preserves_legitimate_inline_structure_mentions_and_century(self):
        samples = (
            'A prática é atestada desde o século II. Mas pode remontar aos Apóstolos.',
            'Consideraremos a busca do homem (capítulo 1) e depois a resposta (capítulo III).',
            'O Símbolo apresenta Jesus (artigo 2), a Encarnação (artigo 3) e a Páscoa (artigos 4 e 5).',
            'A dignidade realiza-se na vocação (artigo 2) e na liberdade (artigo 3).',
            'A profissão conclui: GLÓRIA AO PAI E AO FILHO',
        )
        for text in samples:
            with self.subTest(text=text):
                self.assertEqual(clean_ccc_article_text(text), text)

    def test_preserves_legitimate_uppercase_prose_and_non_page_numbers(self):
        samples = (
            'A profissão proclama: "DEUS É AMOR." E essa verdade permanece.',
            'A profissão conclui. "DEUS É AMOR"',
            'A profissão proclama: DEUS É AMOR',
            'A expressão ACIMA DE TUDO A CARIDADE integra esta frase.',
            'O ARTIGO 1: A REGRA afirma este princípio no meio da argumentação.',
            'A referência ao "ARTIGO 1: A REGRA" permanece no argumento.',
            'A tradição enumera 12',
        )

        for text in samples:
            with self.subTest(text=text):
                self.assertEqual(clean_ccc_article_text(text), text)

    def test_extracts_only_the_requested_article_and_keeps_source_coordinates(self):
        corpus = CccCorpus(
            [
                CccSourceChunk(
                    book_id=1999,
                    chunk_id=64236,
                    sequence_index=45,
                    pdf_page=38,
                    text=(
                        'Contexto. 233.Os cristãos são baptizados "em nome" do Pai, '
                        "do Filho e do Espírito Santo, pois só existe um Deus: a "
                        "Santíssima Trindade. 234.O mistério da Santíssima Trindade "
                        "é central para a fé cristã. 235.Este parágrafo expõe a doutrina."
                    ),
                )
            ]
        )

        extracted = corpus.get_article(233)

        self.assertIsNotNone(extracted)
        self.assertIn("só existe um Deus", extracted.text)
        self.assertNotIn("234.", extracted.text)
        self.assertNotIn("mistério da Santíssima Trindade é central", extracted.text)
        self.assertEqual(extracted.source_chunk_ids, (64236,))
        self.assertEqual(extracted.source_pages, (38,))

    def test_prefers_complete_restarted_marker_at_overlapping_page_boundary(self):
        corpus = CccCorpus(
            [
                CccSourceChunk(
                    1999,
                    64478,
                    287,
                    'ARTIGO 4 1422."Aqueles que se aproximam do sacramento da Penitência',
                    201,
                ),
                CccSourceChunk(
                    1999,
                    64479,
                    288,
                    (
                        'ARTIGO 4 1422."Aqueles que se aproximam do sacramento da '
                        "Penitência obtêm da misericórdia divina o perdão e são "
                        'reconciliados com a Igreja." 1423.Chama-se sacramento da Conversão.'
                    ),
                    201,
                ),
            ]
        )

        extracted = corpus.get_article(1422)

        self.assertIsNotNone(extracted)
        self.assertIn("obtêm da misericórdia divina", extracted.text)
        self.assertIn("reconciliados com a Igreja", extracted.text)
        self.assertEqual(extracted.text.count("Aqueles que se aproximam"), 1)
        self.assertEqual(extracted.source_chunk_ids, (64479,))

    def test_corpus_collapses_the_ingestion_window_before_indexing_articles(self):
        overlap = " ".join(f"palavra{i}" for i in range(1, 101))
        corpus = CccCorpus(
            [
                CccSourceChunk(
                    1999,
                    70001,
                    10,
                    f"64. O início do parágrafo permanece. {overlap}",
                    12,
                ),
                CccSourceChunk(
                    1999,
                    70002,
                    11,
                    f"{overlap} A continuação também permanece. 65. Próximo parágrafo.",
                    13,
                ),
            ]
        )

        extracted = corpus.get_article(64)

        self.assertIsNotNone(extracted)
        self.assertEqual(extracted.text.split().count("palavra1"), 1)
        self.assertIn("O início do parágrafo permanece", extracted.text)
        self.assertTrue(extracted.text.endswith("A continuação também permanece."))
        self.assertEqual(extracted.source_chunk_ids, (70001, 70002))

    def test_understands_article_marker_followed_by_numbered_subcriterion(self):
        corpus = CccCorpus(
            [
                CccSourceChunk(
                    1999,
                    64200,
                    20,
                    (
                        '111.A Escritura deve ser interpretada no Espírito. '
                        '112.1. Prestar atenção "ao conteúdo e à unidade da Escritura inteira". '
                        '113.2. Ler a Escritura dentro da Tradição viva da Igreja.'
                    ),
                    21,
                )
            ]
        )

        extracted = corpus.get_article(112)

        self.assertIsNotNone(extracted)
        self.assertTrue(extracted.text.startswith("1. Prestar atenção"))
        self.assertNotIn("113.", extracted.text)


class ExactArticleQueryTests(unittest.TestCase):
    def test_extracts_quotes_scripture_and_patristic_mentions(self):
        text = (
            'Santo Ireneu ensina: "o Verbo se fez homem para que o homem entre '
            'em comunhão com o Verbo" e participe da natureza divina (2Pd 1,4).'
        )

        query, terms, quotes, scripture, mentions = derive_query_from_exact_article(text)

        self.assertIn("natureza", query)
        self.assertIn("divina", terms)
        self.assertIn("o Verbo se fez homem para que o homem entre em comunhão com o Verbo", quotes)
        self.assertEqual(scripture, ("2Pd 1,4",))
        self.assertTrue(any("Irineu" in name or "Ireneu" in name for name in mentions))

    def test_articles_in_same_old_range_generate_distinct_queries(self):
        source = DictArticleSource(
            {
                1324: article(
                    1324,
                    "A Eucaristia é fonte e ápice de toda a vida cristã e contém "
                    "o próprio Cristo, nossa Páscoa.",
                ),
                1419: article(
                    1419,
                    "Cristo passou deste mundo ao Pai e na Eucaristia nos dá o "
                    "penhor da glória futura e da ressurreição.",
                ),
                1422: article(
                    1422,
                    "Na Penitência recebemos o perdão da ofensa feita a Deus e "
                    "somos reconciliados com a Igreja.",
                ),
                1498: article(
                    1498,
                    "As indulgências podem ser aplicadas aos vivos e aos defuntos "
                    "pela comunhão dos santos.",
                ),
            }
        )
        service = CccCommentaryService(source, RecordingSearchClient(), FixedPatristicFilter(set()))

        pairs = ((1324, 1419), (1422, 1498))
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                left_context = service.build_context(left)
                right_context = service.build_context(right)
                self.assertEqual(left_context.section_title, right_context.section_title)
                self.assertNotEqual(left_context.query, right_context.query)
                self.assertNotEqual(left_context.article_fingerprint, right_context.article_fingerprint)
                self.assertEqual(left_context.mode, CccQueryMode.EXACT_ARTICLE)
                self.assertEqual(right_context.mode, CccQueryMode.EXACT_ARTICLE)


class CccCommentarySearchTests(unittest.TestCase):
    def test_search_uses_exact_query_and_two_layers_of_patristic_filtering(self):
        source = DictArticleSource(
            {
                1324: article(
                    1324,
                    "A Eucaristia é fonte e ápice da vida cristã; contém Cristo, "
                    "nossa Páscoa, e ordena os sacramentos à comunhão.",
                    chunk_id=64458,
                    page=189,
                )
            }
        )
        hits = [
            FakeHit(103044, "TEO", "Santo Tomás de Aquino"),
            FakeHit(51386, "PL", "São Cipriano de Cartago"),
            FakeHit(43660, "PG", "Santo Inácio de Antioquia"),
            FakeHit(51386, "PL", "São Cipriano de Cartago"),
        ]
        search = RecordingSearchClient(hits)
        allow_list = FixedPatristicFilter({51386, 43660})
        service = CccCommentaryService(source, search, allow_list)

        result = service.search(1324, limit=12)

        self.assertEqual(result.hit_ids, (51386, 43660))
        self.assertIn(103044, result.rejected_chunk_ids)
        self.assertEqual(search.calls[0]["collection_filter"], "patristica")
        self.assertEqual(search.calls[0]["query_language"], "pt")
        self.assertEqual(search.calls[0]["patristic_book_ids"], [7001, 7002])
        self.assertEqual(search.last_method, "hybrid")
        self.assertIn("eucaristia", search.calls[0]["query"].casefold())
        self.assertNotIn("transubstanciação", search.calls[0]["query"].casefold())
        self.assertEqual(allow_list.calls, [(103044, 51386, 43660)])
        self.assertEqual(result.context.source_chunk_ids, (64458,))

    def test_route_can_supply_cached_patristic_book_ids_provider(self):
        source = DictArticleSource({233: article(233, "Um só Deus, Pai, Filho e Espírito Santo.")})
        search = RecordingSearchClient([FakeHit(77, "Patrística EN", "Santo Agostinho")])
        allow_list = FixedPatristicFilter({77}, book_ids=())
        service = CccCommentaryService(
            source,
            search,
            allow_list,
            patristic_book_ids_provider=lambda: [9002, 9001, 9002],
        )

        result = service.search(233)

        self.assertEqual(result.hit_ids, (77,))
        self.assertEqual(search.calls[0]["patristic_book_ids"], [9001, 9002])

    def test_context_exposes_article_text_and_terms_for_ui(self):
        service = CccCommentaryService(
            DictArticleSource({1324: article(1324, "A Eucaristia é fonte e ápice da vida cristã.")}),
            RecordingSearchClient(),
            FixedPatristicFilter(set()),
        )

        metadata = service.build_context(1324).response_metadata()

        self.assertEqual(metadata["article_text"], "A Eucaristia é fonte e ápice da vida cristã.")
        self.assertIn("eucaristia", metadata["query_terms"])
        self.assertEqual(metadata["query_mode"], "exact_article")

    def test_missing_exact_source_fails_closed_without_search(self):
        search = RecordingSearchClient([FakeHit(1, "PT", "Santo Agostinho")])
        service = CccCommentaryService(
            DictArticleSource({}),
            search,
            FixedPatristicFilter({1}),
        )

        result = service.search(233)

        self.assertEqual(result.context.mode, CccQueryMode.SOURCE_UNAVAILABLE)
        self.assertEqual(result.hit_ids, ())
        self.assertEqual(search.calls, [])
        self.assertIn("busca aproximada", result.warning)

    def test_filter_failure_also_fails_closed(self):
        class BrokenFilter:
            def patristic_book_ids(self):
                return [9]

            def allowed_chunk_ids(self, chunk_ids):
                raise RuntimeError("database unavailable")

        service = CccCommentaryService(
            DictArticleSource({233: article(233, "Um só Deus em três pessoas divinas.")}),
            RecordingSearchClient([FakeHit(9, "PT", "Santo Agostinho")]),
            BrokenFilter(),
        )

        result = service.search(233)

        self.assertEqual(result.hit_ids, ())
        self.assertEqual(result.rejected_chunk_ids, (9,))
        self.assertIn("bloqueados", result.warning)

    def test_validates_article_and_limit_boundaries(self):
        service = CccCommentaryService(
            DictArticleSource({}),
            RecordingSearchClient(),
            FixedPatristicFilter(set()),
        )

        for invalid in (0, 2866, True, 1.5, "233"):
            with self.subTest(article=invalid), self.assertRaises(ValueError):
                service.build_context(invalid)
        for invalid_limit in (0, 31):
            with self.subTest(limit=invalid_limit), self.assertRaises(ValueError):
                service.search(233, limit=invalid_limit)


if __name__ == "__main__":
    unittest.main()
