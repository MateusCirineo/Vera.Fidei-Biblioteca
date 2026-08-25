import unittest
from dataclasses import replace

from search.content_quality import (
    assess_content,
    extract_query_passage,
    filter_quotable_hits,
)
from search.text_search import AcervoSearchHit


CIPRIAN_NOTES = """
[5] Dt 6,13. [6] Is 2,8ss. [7] Ex 22,19. [8] Isto é, o batismo, e – talvez –
também a Eucaristia (cf. parágrafo 25), cuja administração a criancinhas já seria
comum. [9] Is 52,11. [10] Ap 18,4. [11] Mt 19,21. [12] 1Tm 6,9.10.
[13] Lc 18,19ss. [14] Lc 6,22ss. [15] Alusão a dois momentos na perseguição.
[16] Is 3,12. [17] Ap 3,19. [18] Lv 7,19s. [19] 1Cor 10,20. [20] 1Cor 11,27.
[21] Ap 2,5. [22] Jr 17,5. [23] Ap 6,10. [24] Ex 32,31-33. [25] Jr 1,5.
[26] Jr 11,14. [27] Ez 14,13.14. [28] Mt 10,32.33. [29] Is 42,24.25.
[30] Is 59,1.2. [31] Isto é, tinha se servido de comida sacrificada aos deuses.
[32] A Eucaristia. [33] Celebrar a Eucaristia. [34] O pão eucarístico.
"""

JUSTIN_TOC = """
56 Outras lembranças pagãs 58 Fraternidade e eucaristia 58 Teologia da eucaristia
58 Liturgia dominical 59 Petição final 59 Introdução à II Apologia 63 II APOLOGIA
65 Um drama doméstico 65 O suicídio não é lícito 66 A obra dos demônios 67 Deus
não tem nome 67 Os cristãos conservam o mundo 68 A semente do Verbo 69
Pressentimento do martírio 69 Existe uma justiça eterna 70 Possuímos o Verbo inteiro
70 O mito de Héracles 71 O platônico se faz cristão 72 Sou cristão 73 Introdução ao
diálogo 75 DIÁLOGO DE JUSTINO, FILÓSOFO E MÁRTIR, COM O JUDEU TRIFÃO 77
"""

JUSTIN_TOC_FULL_SHAPE = JUSTIN_TOC + """
Primeiras objeções de Trifão 87 A lei antiga superada pela nova 87 Digressão sobre a
maldade dos judeus 91 Justino acusa os judeus 92 A não necessidade da circuncisão 93
As leis são devidas à dureza do coração 95 Leis sobre os sacrifícios 95 A circuncisão:
um sinal e não justificação 97 Convite à conversão 98 Os herdeiros do monte Sião 99
Digressão sobre a parusia 102 Objeção de Trifão 103 Interpretação cristológica dos
salmos 104 Digressão sobre os falsos cristãos 106 Cristo é o Rei das potências 107
As figuras do verdadeiro sacrifício 110 A eucaristia: verdadeiro sacrifício 111
Mistério no nascimento virginal 112 Quem ressuscitará? 114 Quem se salvará? 115
Preexistência e divindade de Cristo 117 Discussão em torno do primeiro salmo 118
Moisés anunciou o Cristo 120 A nova aliança 122 As profecias 124 O sinal de Jonas 127
A fé de Abraão 131 A descendência espiritual 136 A Igreja entre as nações 140
O povo cristão 145 A paixão anunciada 150 A ressurreição 156 A missão dos apóstolos 160
"""

DIDACHE_TOC = """
12 Capítulo V – O caminho da morte 13 Capítulo VI – Sobre os alimentos 14 PARTE II.
A CELEBRAÇÃO LITÚRGICA 15 Capítulo VII - Batismo 16 Capítulo VIII - Jejum 17
Capítulo IX - Eucaristia 18 Capítulo X – Ação de Graças 19 PARTE III. A VIDA EM
COMUNIDADE 20 Capítulo XI – Apóstolos e profetas na comunidade 21 Capítulo XII –
Sustento do ministro 22 Capítulo XIII – Ofertas de primícias 23 Capítulo XIV –
Preceito dominical 24 Capítulo XV - Bispos e diáconos 25 PARTE IV. O FIM DOS
TEMPOS 26 Capítulo XVI – A parusia do Senhor 27 39.
"""

DIDACHE_INDEX_WITH_AD = """
Conheça outros materiais da Editora Família e visite nossa loja virtual para comprar
novos e-books. Index PARTE I. O CAMINHO DA VIDA 9 Capítulo I – Amor a Deus 9
Capítulo II – Os mandamentos 10 Capítulo III – A maldade 11 Capítulo IV – Comunidade
12 Capítulo V – Morte 13 Capítulo VI – Alimentos 14 PARTE II. A CELEBRAÇÃO
LITÚRGICA 15 Capítulo VII – Batismo 16 Capítulo VIII – Jejum 17 Capítulo IX –
Eucaristia 18 Capítulo X – Ação de Graças 19 PARTE III. A VIDA EM COMUNIDADE 20.
"""

JUSTIN_BODY = """
o primeiro pensamento; coisa que consideramos absolutamente ridícula, apresentar uma
mulher como imagem do pensamento. De modo semelhante, suas ações arguem os outros
chamados filhos de Zeus. Fraternidade e eucaristia 1 65. De nossa parte, depois que
assim foi lavado aquele que creu e aderiu a nós, nós o levamos aos que se chamam irmãos,
no lugar em que estão reunidos, a fim de elevar fervorosamente orações em comum.
Terminadas as orações, nos damos mutuamente o ósculo da paz. Depois, àquele que preside
aos irmãos é oferecido pão e uma vasilha com água e vinho; pegando-os, ele louva e
glorifica ao Pai do universo através do nome de seu Filho e do Espírito Santo. Quando o
presidente termina as orações e a ação de graças, todo o povo presente aclama, dizendo:
“Amém”. Depois, os ministros dão a cada um dos presentes parte do pão, do vinho e da
água sobre os quais se pronunciou a ação de graças e os levam aos ausentes. Teologia da
eucaristia 1 66. Este alimento se chama entre nós Eucaristia, da qual ninguém pode
participar, a não ser que creia serem verdadeiros nossos ensinamentos e viva conforme o
que Cristo nos ensinou. De fato, não tomamos essas coisas como pão comum ou bebida
ordinária, mas como a carne e o sangue daquele mesmo Jesus encarnado.
"""

CYPRIAN_BODY = """
caríssimos, entender esta petição assim: que supliquemos também por aqueles que ainda
são terra, para que sobre eles se realize a vontade de Deus. Com efeito, o Cristo é o pão
da vida, e esse pão não é de todos, mas é nosso. Também, como dissemos “Pai nosso”,
porque é Pai dos que entendem e creem, assim dizemos “pão nosso”, porque Cristo é pão
para aqueles que comem o seu corpo. Mas pedimos que este pão nos seja dado diariamente
a fim de que nós, que estamos no Cristo e recebemos diariamente a Eucaristia como
alimento de salvação, não venhamos a ser separados do Corpo do Cristo. Ele próprio o
adverte, dizendo: “Eu sou o pão vivo que desci do céu. Se alguém comer do meu pão viverá
eternamente”. Quando ele diz que viverá eternamente quem comer de seu pão, é evidente
que viverão os que pertencem ao seu corpo e recebem a Eucaristia em direito de comunhão.
"""

IRENAEUS_EDITORIAL = """
Irineu defendeu vigorosamente a unidade dos dois testamentos da Bíblia. É por isso que
Irineu encontra no Antigo Testamento textos que se referem ao Pai, ao Filho e ao Espírito
Santo. Trata-se da leitura tipológica da Escritura. Irineu testemunha a presença real do
Corpo e Sangue de Jesus na Eucaristia; testemunha o caráter sacrificial da Eucaristia,
recordando a profecia de Malaquias; deduz a ressurreição dos corpos e apresenta a
Eucaristia como sinal da salvação do homem na história. Nesta obra, o leitor encontrará
o pensamento de Irineu explicado em seus principais temas.
"""

GREGORY_OVERVIEW = """
Segundo S. Gregório de Nissa, o demônio tinha enganado o homem com a vaidade do prazer.
A última parte é consagrada aos sacramentos e conclui com um breve aceno aos fins últimos.
Os sacramentos do Batismo e da Eucaristia tornam possível a atualização do mistério.
A originalidade de S. Gregório de Nissa aparece nas páginas dedicadas à conduta moral.
"""

AUGUSTINE_EDITOR_NOTES = """
9. (4,10) - Alusão à Eucaristia. Eis aqui um parêntese em favor da presença real.
Cf. Luiz Arias, nota 4, p. 281. Em comentário a esta passagem, E. Millet diz que o
texto resume o ensino eucarístico de santo Agostinho. Para um conhecimento mais
aprofundado da doutrina convém ler os sermões indicados pelo editor. 10. (5,11) -
O significado dos milagres. Cf. a nota 26 e as referências bibliográficas seguintes.
"""

APOSTOLIC_LETTER_NOTES = """
w É um antigo ritual litúrgico, com instruções para a administração do batismo.
O v. 3 se refere às disposições do Concílio de Jerusalém. x Nesse tempo, a cerimônia
era realizada em comunidade. A menção das diversas possibilidades faz supor que o
mais usual era a imersão em água corrente. z A Eucaristia aqui mencionada diverge
do rito atual; isto significa que o editor está explicando o texto antigo.
"""

IRENAEUS_BARE_NOTES = """
2 Cf. Jo 1,18; Rm 11,34. 3 Apostasia é um termo abstrato. 4 Gn 1,26; Jo 1,13.
5 Cl 1,14. 6 Ef 5,30; Lc 24,39. 7 Tanto firme quanto impressionante é a teologia
de Ireneu sobre a Eucaristia. 8 2Cor 12,7-9. 9 Cf. Sl 23,6; Gn 5,24. 10 Gn 2,8.
11 Dn 3,91-92. 12 O homem é alma, corpo e espírito segundo esta nota editorial.
"""

DIDACHE_INTRODUCTION = """
Nos escritos do Didaquê, além da catequese e liturgia cristã, o evangelho é citado.
O texto foi mencionado por escritores do século III. A descoberta desse manuscrito
na íntegra, num códice do século XI, ocorreu em 1873 num mosteiro em Constantinopla.
O conteúdo dos capítulos apresenta a obra e finaliza esta introdução ao texto traduzido.
"""

GREGORY_SCHOLARLY_COMMENTARY = """
Gregório considera a Eucaristia como parte importante para atingir a finalidade da
Encarnação e mostra como ela conduz à divinização do homem. Gregório esclarece a
incorruptibilidade do corpo, interpreta a mudança do pão e apresenta sua doutrina.
Ver também Vita Moys. II,82,1-5. Cf. G. MASPERO, “Apocatastasi”, in MATEO-SECO,
L. F. & MASPERO, G. (orgs.). Gregorio di Nissa Dizionario, 91-93.
"""

IRENAEUS_DOCTRINAL_OVERVIEW = """
O pensamento ireneano é muito rico e fonte para a teologia. A presença real do corpo
e sangue de Cristo Senhor na Eucaristia garante a ressurreição dos corpos. A Tradição
ocupa na teologia do bispo de Lião lugar muito alto, porque os autores sacros pregaram
e depois escreveram. A escatologia ireneana não pode ser compreendida fora da teoria
da recapitulação, que interpreta e apresenta os principais temas do autor.
"""

MODERN_NUMBERED_BIOGRAPHICAL_NOTES = """
110 Em grego transliterado: chrysã paraggélmata. 111 Jâmblico foi um filósofo
neoplatônico assírio do século III e estudou a filosofia de Pitágoras e Platão.
112 Porfírio, Vita Pyth. 48.55.57-58. 113 Porfírio, ibid., 22. Trecho em grego
transliterado. 114 Porfírio, ibid., 33. 115 Nicômano de Gérasa (60-120) exerceu
influência sobre Anatólio de Laodiceia (240-325). 116 Porfírio (233-304) foi
considerado discípulo de Plotino (204-270), segundo a nota biográfica do editor.
"""

STALE_COLLECTIVE_BIOGRAPHY = """
Ainda segundo Ireneu, Policarpo empreendeu uma viagem a Roma sob o pontificado de
Aniceto, por volta do ano 155, para discutir a data da celebração da Páscoa. No tempo
de Ireneu, esta tornou-se uma questão aguda. Ireneu intervém relatando ao papa Vítor
a entrevista de Policarpo e Aniceto. Esta carta é outro testemunho de primeira grandeza.
"""


def hit(chunk_id: int, text: str, *, score: float = 1.0, book_id: int = 1) -> AcervoSearchHit:
    return AcervoSearchHit(
        chunk_id=chunk_id,
        score=score,
        text=text,
        author="São Justino Mártir",
        work_title="I e II Apologias — Diálogo com Trifão",
        collection="PT",
        book_id=book_id,
    )


class ContentAssessmentTests(unittest.TestCase):
    def test_real_cyprian_notes_are_not_quotable(self) -> None:
        assessment = assess_content(CIPRIAN_NOTES, author="São Cipriano de Cartago", pdf_page=209)
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "notes")

    def test_real_justin_repeated_index_is_not_quotable(self) -> None:
        assessment = assess_content(JUSTIN_TOC, author="São Justino Mártir", pdf_page=223)
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "toc")

    def test_full_shape_justin_index_is_rejected_for_any_query(self) -> None:
        assessment = assess_content(JUSTIN_TOC_FULL_SHAPE, author="São Justino Mártir", pdf_page=223)
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "toc")
        for query in ("filosofia", "Trifão", "Quem ressuscitará"):
            with self.subTest(query=query):
                self.assertEqual(
                    extract_query_passage(JUSTIN_TOC_FULL_SHAPE, query, author="São Justino Mártir"),
                    "",
                )

    def test_short_didache_table_of_contents_is_rejected(self) -> None:
        assessment = assess_content(DIDACHE_TOC, work_title="Didaquê Bilíngue")
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "toc")

    def test_index_after_publisher_ad_is_rejected(self) -> None:
        assessment = assess_content(DIDACHE_INDEX_WITH_AD, work_title="Didaquê Bilíngue")
        self.assertFalse(assessment.is_quotable)
        self.assertIn(assessment.role, {"toc", "publisher_ad"})

    def test_editorial_third_person_summary_is_not_a_father_quote(self) -> None:
        assessment = assess_content(
            IRENAEUS_EDITORIAL,
            author="Santo Irineu de Lião",
            pdf_page=29,
        )
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "introduction")

    def test_substantive_father_texts_are_quotable(self) -> None:
        self.assertTrue(assess_content(JUSTIN_BODY, author="São Justino Mártir").is_quotable)
        self.assertTrue(assess_content(CYPRIAN_BODY, author="São Cipriano de Cartago").is_quotable)

    def test_appendix_heading_is_not_quotable(self) -> None:
        appendix = (
            "Apêndice. Relação complementar preparada pelos editores para consulta. "
            "Este catálogo enumera variantes, remissões e materiais externos da edição. "
            "As informações abaixo não pertencem ao corpo da obra antiga e servem apenas "
            "como instrumento editorial de apoio ao leitor."
        )
        assessment = assess_content(appendix, author="Autor patrístico")
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "appendix")

    def test_short_complete_patristic_sentence_is_quotable(self) -> None:
        quotation = "A Eucaristia confirma nossa doutrina e alimenta a esperança da ressurreição."
        assessment = assess_content(quotation, author="Santo Irineu de Lião")
        self.assertTrue(assessment.is_quotable)
        self.assertEqual(assessment.role, "body")

    def test_legitimate_quote_under_fifty_five_characters_is_quotable(self) -> None:
        quotation = "O sangue dos mártires é semente de cristãos."
        assessment = assess_content(quotation, author="Tertuliano")
        self.assertTrue(assessment.is_quotable)

    def test_short_numbered_editorial_note_is_not_quotable(self) -> None:
        note = "[12] Cf. Jo 6,53. [13] Ver também 1Cor 11,27 e a nota editorial da página anterior."
        assessment = assess_content(note, author="Santo Irineu de Lião")
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "notes")

    def test_generic_early_editorial_summary_is_not_quotable(self) -> None:
        summary = (
            "Nesta obra, o leitor encontra a doutrina eucarística apresentada em seus temas. "
            "O estudo explica a controvérsia, apresenta os capítulos e trata da recepção posterior. "
            "As páginas seguintes oferecem o texto traduzido e notas para consulta."
        )
        assessment = assess_content(summary, author="Santo Irineu de Lião", pdf_page=12)
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "introduction")

    def test_real_editorial_variants_from_live_corpus_are_rejected(self) -> None:
        cases = [
            (GREGORY_OVERVIEW, "São Gregório de Nissa", 21, "introduction"),
            (AUGUSTINE_EDITOR_NOTES, "Santo Agostinho", 350, "notes"),
            (APOSTOLIC_LETTER_NOTES, "Padres Apostólicos", 184, "notes"),
            (IRENAEUS_BARE_NOTES, "Santo Irineu de Lião", 4, "notes"),
            (DIDACHE_INTRODUCTION, "Autor desconhecido", 6, "introduction"),
            (GREGORY_SCHOLARLY_COMMENTARY, "São Gregório de Nissa", 170, "introduction"),
            (IRENAEUS_DOCTRINAL_OVERVIEW, "Santo Irineu de Lião", 21, "introduction"),
        ]
        for text, author, page, expected_role in cases:
            with self.subTest(author=author, expected_role=expected_role):
                assessment = assess_content(text, author=author, pdf_page=page)
                self.assertFalse(assessment.is_quotable)
                self.assertEqual(assessment.role, expected_role)

    def test_modern_numbered_biographical_notes_are_not_quotable(self) -> None:
        assessment = assess_content(
            MODERN_NUMBERED_BIOGRAPHICAL_NOTES,
            author="São Jerônimo",
            work_title="Patrística Vol. 31 — Apologia contra os Livros de Rufino",
            pdf_page=122,
        )
        self.assertFalse(assessment.is_quotable)
        self.assertIn(assessment.role, {"notes", "toc"})

    def test_stale_collective_author_tag_does_not_turn_biography_into_quote(self) -> None:
        assessment = assess_content(
            STALE_COLLECTIVE_BIOGRAPHY,
            author="Santo Inácio de Antioquia",
            pdf_page=80,
        )
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "introduction")

    def test_appendix_heading_after_body_prose_is_rejected(self) -> None:
        text = (
            "O autor antigo conclui a exposição com uma oração dirigida a Deus. "
            "Os fiéis recebem a paz e perseveram unidos na esperança. "
            "Apêndice I. Estudo do editor sobre a doutrina e suas fontes modernas. "
            "Este material foi preparado apenas para consulta acadêmica da edição."
        )
        assessment = assess_content(text, author="São Justino Mártir", pdf_page=120)
        self.assertFalse(assessment.is_quotable)
        self.assertEqual(assessment.role, "appendix")


class PassageExtractionTests(unittest.TestCase):
    def test_excerpt_uses_complete_sentences_around_query(self) -> None:
        passage = extract_query_passage(
            JUSTIN_BODY,
            "Eucaristia",
            author="São Justino Mártir",
            min_chars=150,
            max_chars=620,
        )
        self.assertIn("Este alimento se chama entre nós Eucaristia", passage)
        self.assertIn("pão comum ou bebida ordinária", passage)
        self.assertFalse(passage.startswith("o primeiro pensamento"))
        self.assertTrue(passage.endswith("."))

    def test_noise_never_becomes_a_blockquote_excerpt(self) -> None:
        self.assertEqual(
            extract_query_passage(CIPRIAN_NOTES, "Eucaristia", author="São Cipriano de Cartago"),
            "",
        )

    def test_short_complete_quote_is_returned(self) -> None:
        quotation = "A Eucaristia confirma nossa doutrina e alimenta a esperança da ressurreição."
        self.assertEqual(
            extract_query_passage(quotation, "Eucaristia", author="Santo Irineu de Lião"),
            quotation,
        )

    def test_semantic_hit_without_textual_anchor_is_not_guessed(self) -> None:
        text = (
            "O jejum disciplina o corpo e prepara a alma para a oração. "
            "Os fiéis perseveram com humildade durante os dias de penitência. "
            "A comunidade também socorre os pobres e visita os enfermos."
        )
        self.assertEqual(
            extract_query_passage(text, "presença real", author="São Cipriano de Cartago"),
            "",
        )

    def test_query_in_section_heading_is_not_used_as_quote_anchor(self) -> None:
        text = (
            "O cordeiro era figura da paixão que Cristo devia sofrer na cruz. "
            "A eucaristia: verdadeiro sacrifício 1 41. "
            "Continuei: A oferta de farinha era figura do pão da Eucaristia que nosso Senhor "
            "mandou oferecer em memória da paixão padecida por todos os homens."
        )
        passage = extract_query_passage(text, "Eucaristia", author="São Justino Mártir")
        self.assertTrue(passage.startswith("Continuei:"), passage)
        self.assertNotIn("A eucaristia: verdadeiro sacrifício", passage)

    def test_excerpt_stops_before_next_numbered_chapter_heading(self) -> None:
        text = (
            "Ninguém coma nem beba da Eucaristia se não estiver batizado em nome do Senhor. "
            "Pois a respeito dela disse o Senhor: “Não deis as coisas santas aos cães!” "
            "18 Capítulo X – Ação de Graças 1. Nós te bendizemos, Pai santo."
        )
        passage = extract_query_passage(text, "Eucaristia", author="Didaquê")
        self.assertIn("Ninguém coma nem beba da Eucaristia", passage)
        self.assertNotIn("Capítulo X", passage)

    def test_latin_theological_equivalent_can_anchor_a_quote(self) -> None:
        quotation = (
            "Haec Eucharistia corpus Christi est, quod pro salute mundi traditum est. "
            "Qui digne accipit, in communione Ecclesiae permanet."
        )
        passage = extract_query_passage(quotation, "Eucaristia", author="Autor latino")
        self.assertIn("Eucharistia corpus Christi", passage)

    def test_heading_only_query_does_not_return_previous_paragraph(self) -> None:
        text = (
            "Os demônios imitaram as profecias e enganaram muitos homens. "
            "Fraternidade e eucaristia 1 65. "
            "Depois que foi lavado aquele que creu, nós o levamos aos irmãos para orar."
        )
        self.assertEqual(
            extract_query_passage(text, "Eucaristia", author="São Justino Mártir"),
            "",
        )
        self.assertEqual(
            extract_query_passage(JUSTIN_TOC, "Eucaristia", author="São Justino Mártir"),
            "",
        )

    def test_ranked_filter_replaces_noise_and_deduplicates_overlap(self) -> None:
        duplicate = JUSTIN_BODY.replace("Este alimento", "Este alimento", 1)
        results = filter_quotable_hits(
            [
                hit(74494, CIPRIAN_NOTES, score=10.0, book_id=2038),
                hit(2112, JUSTIN_TOC, score=9.0, book_id=10),
                hit(1926, JUSTIN_BODY, score=8.0, book_id=10),
                hit(1925, duplicate, score=7.5, book_id=10),
                hit(74402, CYPRIAN_BODY, score=7.0, book_id=2038),
            ],
            "Eucaristia",
            limit=10,
            replace_hit=replace,
        )

        self.assertEqual([item.chunk_id for item in results], [1926, 74402])
        self.assertNotIn("[5] Dt 6,13", " ".join(item.text for item in results))
        self.assertNotIn("Outras lembranças pagãs", " ".join(item.text for item in results))

    def test_collective_volume_requires_and_uses_the_chunk_author(self) -> None:
        quotation = (
            "Não me comprazo no alimento corruptível nem nos prazeres desta vida. "
            "Quero o pão de Deus, que é a carne de Jesus Cristo, e por bebida quero o seu "
            "sangue, que é amor incorruptível e verdadeira Eucaristia para os fiéis."
        )
        generic = replace(
            hit(1700, quotation),
            author="Padres Apostólicos",
            work_title="Patrística Vol. 1 — Padres Apostólicos",
            chunk_author=None,
        )
        repeated_generic = replace(generic, chunk_id=1701, chunk_author="Padres Apostólicos")
        attributed = replace(
            generic,
            chunk_id=1705,
            work_title="Cartas de Santo Inácio de Antioquia",
            chunk_author="Santo Inácio de Antioquia",
        )

        results = filter_quotable_hits(
            [generic, repeated_generic, attributed],
            "Eucaristia",
            limit=10,
            replace_hit=replace,
        )

        self.assertEqual([item.chunk_id for item in results], [1705])
        self.assertEqual(results[0].author, "Santo Inácio de Antioquia")

    def test_oriental_collective_label_is_never_presented_as_an_author(self) -> None:
        quotation = (
            "Severo expõe esta doutrina e o aparato reúne testemunhos orientais. "
            "A passagem menciona a Eucaristia, mas não identifica o autor antigo desta coluna."
        )
        collective = replace(
            hit(107542, quotation),
            author="Varios Padres Orientais",
            chunk_author="Varios Padres Orientais",
            work_title="Patrologia Orientalis PO001",
            collection="PO",
        )
        self.assertEqual(
            filter_quotable_hits(
                [collective],
                "Eucaristia",
                limit=10,
                replace_hit=replace,
            ),
            [],
        )

    def test_standalone_didache_can_be_safely_attributed_from_its_title(self) -> None:
        quotation = (
            "Ninguém coma nem beba de vossa Eucaristia se não estiver batizado em nome "
            "do Senhor. Pois a respeito dela disse o Senhor: não deis as coisas santas aos cães."
        )
        standalone = replace(
            hit(65663, quotation),
            author="Autor desconhecido",
            chunk_author=None,
            work_title="Didaquê Bilíngue Grego-Português",
            collection="DIDAQUE",
        )
        results = filter_quotable_hits(
            [standalone],
            "Eucaristia",
            limit=10,
            replace_hit=replace,
        )
        self.assertEqual([item.chunk_id for item in results], [65663])
        self.assertEqual(results[0].author, "Didaquê")


if __name__ == "__main__":
    unittest.main()
