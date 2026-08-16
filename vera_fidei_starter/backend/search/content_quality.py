from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Protocol, TypeVar


_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", re.UNICODE)
_SENTENCE_MARK_RE = re.compile(r"[.!?…](?:[\"”’»\]]+)?(?=\s|$)")
_BRACKETED_NOTE_RE = re.compile(r"\[(?:\d{1,3}|[*†‡])\]")
_BARE_NOTE_MARKER_RE = re.compile(
    r"(?:^|\s)(?:\d{1,3}[.)]?|[a-z])\s+(?=(?:\([^)]+\)\s*[-–—]?|Cf\.|[A-ZÁÉÍÓÚÂÊÔÃÕÇ]))"
)
_NUMBERED_NOTE_MARKER_RE = re.compile(
    r"(?:^|\s)\d{1,3}[.)]?\s+(?=(?:\([^)]+\)\s*[-–—]?|Cf\.|[A-ZÁÉÍÓÚÂÊÔÃÕÇ]))"
)
_BIBLE_REFERENCE_RE = re.compile(
    r"(?<!\w)(?:Gn|Ex|Lv|Nm|Dt|Js|Jz|Rt|1Sm|2Sm|1Rs|2Rs|1Cr|2Cr|Esd|Ne|Tb|Jt|Est|"
    r"Jó|Sl|Pr|Ecl|Ct|Sb|Eclo|Is|Jr|Lm|Br|Ez|Dn|Os|Jl|Am|Ab|Jn|Mq|Na|Hab|Sf|Ag|"
    r"Zc|Ml|Mt|Mc|Lc|Jo|At|Rm|1Cor|2Cor|Gl|Ef|Fl|Cl|1Ts|2Ts|1Tm|2Tm|Tt|Fm|Hb|"
    r"Tg|1Pd|2Pd|1Jo|2Jo|3Jo|Jd|Ap)\s*\d{1,3}\s*[,.:]\s*\d{1,3}",
    re.IGNORECASE,
)
_INLINE_PAGE_RE = re.compile(r"(?:^|\s)p(?:p)?\.\s*\d{1,4}(?:\s*[-–—]\s*\d{1,4})?", re.I)
_ISBN_RE = re.compile(r"\bISBN(?:-1[03])?\b|\b97[89][ -]?\d{1,5}[ -]?\d", re.I)
_TOC_WORD_RE = re.compile(r"\b(?:índice|indice|index|sumário|sumario|table of contents|contents)\b", re.I)
_NOTES_WORD_RE = re.compile(r"\b(?:notas|notes|notas complementares|aparato crítico)\b", re.I)
_BIBLIOGRAPHY_RE = re.compile(r"\b(?:bibliografia|referências bibliográficas|bibliography)\b", re.I)
_SCHOLARLY_CITATION_RE = re.compile(
    r"\b(?:cf\.|ver tamb[eé]m)\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.!?]{0,100}?"
    r"(?:\(orgs?\.\)|\b(?:in|apud)\b|[\"“][^\"”]{2,80}[\"”])",
    re.I,
)
_APPENDIX_RE = re.compile(r"\b(?:apêndice|apendice|appendix|anexo|errata|glossário|glossario)\b", re.I)
_FRONT_MATTER_RE = re.compile(
    r"\b(?:apresentação|apresentacao|introdução|introducao|prefácio|prefacio|prólogo|prologo|"
    r"agradecimentos|cronologia|abreviaturas|ficha catalográfica|ficha catalografica)\b",
    re.I,
)
_PUBLISHER_RE = re.compile(
    r"\b(?:direção editorial|direcao editorial|coordenação editorial|coordenacao editorial|"
    r"coordenação de desenvolvimento|compre agora|loja virtual|e-?book|todos os direitos reservados|"
    r"conselho editorial|editora paulus)\b",
    re.I,
)
_DIGITIZATION_BOILERPLATE_RE = re.compile(
    r"\b(?:reproduction of a library book|digitized by google|books\.google\.com|google books)\b",
    re.I,
)
_INTRO_HEADING_RE = re.compile(
    r"^(?:\d+\s+)?(?:apresentação|apresentacao|introdução|introducao|prefácio|prefacio|prólogo|prologo)\b",
    re.I,
)
_BODY_SECTION_RE = re.compile(
    r"\b(?:texto|livro\s+[ivxlcdm]+|cap[ií]tulo\s+\d+|homilia\s+\d+|serm[aã]o\s+\d+|"
    r"i\s+apologia|ii\s+apologia|di[aá]logo\s+de|carta\s+\d+)\b",
    re.I,
)
_EDITORIAL_VERBS_RE = re.compile(
    r"\b(?:afirm\w*|apresent\w*|desenvolv\w*|deduz\w*|testemunh\w*|explic\w*|"
    r"ensin\w*|escrev\w*|comp[oô]s\w*|nasc\w*|morr\w*|defend\w*|insist\w*|"
    r"trat\w*|pens\w*|conclu\w*|aparec\w*|consagr\w*|estud\w*|abord\w*|"
    r"analis\w*|coment\w*|mostr\w*|cit\w*|finaliz\w*|consider\w*|mencion\w*|"
    r"descobr\w*|ocorr\w*|refer\w*|traduz\w*|interpret\w*|esclarec\w*)\b",
    re.I,
)
_EDITORIAL_NOTE_RE = re.compile(
    r"\b(?:cf\.|nota\s+\d+|em coment[aá]rio|a esta passagem|conv[eé]m ler|"
    r"conhecimento mais aprofundado|o v\.\s*\d+|se refere [àa]s?|faz supor|"
    r"a men[cç][aã]o de|aqui mencionad[oa]|isto significa|isso significa|"
    r"no par[aá]grafo seguinte|alguns v[eê]em|v[eê]em os especialistas|"
    r"chama a aten[cç][aã]o|pesquisas arqueol[oó]gicas|era cidade|"
    r"correspondem? a|[eé] a [uú]nica carta|n[aã]o indica|deixa entender|"
    r"outra vez [^.!?]{0,30} se refere)\b",
    re.I,
)
_OVERVIEW_RE = re.compile(
    r"\b(?:nesta obra|esta obra|a [uú]ltima parte|primeira parte|segunda parte|"
    r"cap[ií]tulos?\s+\d|originalidade de|pensamento de|nos escritos d[oa]|"
    r"conte[uú]do|manuscrito|c[oó]dice|descoberta d[eo]|introdu[cç][aã]o a|"
    r"p[aá]ginas seguintes|texto traduzido|instrumento editorial|original grego|"
    r"vers[ií]culo acima|ao ler (?:este|esse|o) [^.!?]{0,40}livro|faz refer[eê]ncia)\b",
    re.I,
)
_BIOGRAPHICAL_DATE_RE = re.compile(r"\b(?:s[eé]culo\s+[ivxlcdm]+|\d{3,4}\s*(?:[-–—]\s*\d{2,4})?\s*d\.?c\.?)\b", re.I)
_LIFE_DATE_RANGE_RE = re.compile(r"\(\s*\d{2,4}\s*[-–—]\s*\d{2,4}\s*\)")
_BIOGRAPHICAL_NOTE_RE = re.compile(
    r"\b(?:foi (?:um|uma)|nascid[oa]|estudou|escreveu|disc[ií]pul[oa]|fundador(?:a)?|"
    r"filh[oa] de|precursor(?:a)?|[eé] mais conhecid[oa]|dados biogr[aá]ficos|"
    r"segundo (?:pl[ií]nio|plutarco|higino))\b",
    re.I,
)
_BIBLIOGRAPHICAL_NOTE_RE = re.compile(
    r"\b(?:ibid\.|vita\s+[A-Z]|trecho em grego transliterado|"
    r"(?:virg[ií]lio|porf[ií]rio|pl[ií]nio|plutarco),\s+[A-Z])",
    re.I,
)
_EDITORIAL_BIOGRAPHY_RE = re.compile(
    r"\b(?:ainda segundo|sob o pontificado|por volta do ano|no tempo de|"
    r"empreendeu uma viagem|interv[eé]m relatando|esta carta [eé] (?:outro )?testemunho|"
    r"dados biogr[aá]ficos|segundo (?:a cr[oô]nica|o historiador|a tradi[cç][aã]o))\b",
    re.I,
)
_COMPLETE_SENTENCE_END_RE = re.compile(r"[.!?…](?:[\"”’»\]]+)?$")
_SECTION_HEADING_RE = re.compile(
    r"(?:^|(?<=[.!?…])\s+)"
    r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.!?…]{2,115}?"
    r"\s+(?:\d{1,2}\s+)?(?:[a-z]\s+)?\d{1,3}\."
    r"(?=\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ\"“«(])"
)
_OCR_MERGED_HEADING_RE = re.compile(
    r"(?:^|(?<=[.!?…])\s+)"
    r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.!?…]{2,100}?\s+\d{1,3}"
    r"(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])"
)
_NUMBERED_SECTION_HEADING_RE = re.compile(
    r"(?:^|(?<=[.!?…])\s+|(?<=[.!?…][\"”’»\]])\s+)"
    r"\d{1,4}\s+(?:cap[ií]tulo|livro|parte|homilia|serm[aã]o)\s+"
    r"[^.!?…]{1,100}?(?:\s+\d{1,3})?\."
    r"(?=\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ\"“«(])",
    re.I,
)
_STOP_WORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos", "e",
    "em", "esta", "este", "isso", "na", "nas", "no", "nos", "o", "os", "ou", "para",
    "pela", "pelas", "pelo", "pelos", "por", "que", "se", "sem", "sobre", "um", "uma",
}
_GENERIC_BOOK_AUTHORS = {
    "padres apostolicos",
    "padres apologistas",
    "varios padres latinos",
    "varios padres gregos",
    "varios padres orientais",
    "autor desconhecido",
}


@dataclass(frozen=True)
class ContentAssessment:
    role: str
    is_quotable: bool
    quality_score: float
    reasons: tuple[str, ...] = ()


class SearchHitLike(Protocol):
    chunk_id: int
    score: float
    text: str
    author: str
    chunk_author: str | None
    work_title: str
    translation_text: str | None
    chapter_or_section: str | None
    pdf_page: int | None
    book_id: int | None


TSearchHit = TypeVar("TSearchHit", bound=SearchHitLike)


def fold_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.casefold().replace("‐", "-").replace("‑", "-").replace("—", "-")
    return _SPACE_RE.sub(" ", normalized).strip()


def clean_ocr_text(value: str | None) -> str:
    text = (value or "").replace("\u00ad", "")
    text = re.sub(r"(?<=[A-Za-zÀ-ÿ])[-‐‑]\s+(?=[a-zà-ÿ])", "", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def _author_key(author: str | None) -> str:
    folded = fold_text(author)
    words = [
        word for word in _WORD_RE.findall(folded)
        if word not in {"sao", "santo", "santa", "de", "da", "do", "dos", "das", "martir"}
    ]
    return words[0] if words else ""


def _work_keys(work_title: str | None) -> list[str]:
    ignored = {
        "patristica", "volume", "vol", "obras", "completas", "obra", "livro",
        "texto", "traducao", "edicao", "portugues", "grego", "latim", "ingles",
        "santo", "santa", "sao", "dos", "das", "com", "para", "uma",
    }
    return [
        token
        for token in _WORD_RE.findall(fold_text(work_title))
        if len(token) >= 5 and token not in ignored and not token.isdigit()
    ][:4]


def _effective_author(
    author: str | None,
    chunk_author: str | None,
    work_title: str | None,
) -> str:
    if chunk_author and fold_text(chunk_author) not in {"", "autor desconhecido"}:
        return chunk_author
    if "didaque" in fold_text(work_title):
        return "Didaquê"
    return author or ""


def _chunk_attribution_is_specific(
    book_author: str | None,
    chunk_author: str | None,
    work_title: str | None,
) -> bool:
    """True only when a collective book names the author of this passage.

    A generic collective label is never a truthful citation attribution. A
    specific per-chunk author is accepted and the independent content-quality
    gate below still rejects introductions, notes and stale boundary prose.
    """
    book_key = fold_text(book_author)
    if "didaque" in fold_text(work_title):
        return True
    if book_key not in _GENERIC_BOOK_AUTHORS:
        return True
    if not chunk_author or fold_text(chunk_author) in _GENERIC_BOOK_AUTHORS:
        return False
    return True


def assess_content(
    text: str | None,
    *,
    section: str | None = None,
    author: str | None = None,
    work_title: str | None = None,
    pdf_page: int | None = None,
) -> ContentAssessment:
    clean = clean_ocr_text(text)
    folded = fold_text(clean)
    folded_section = fold_text(section)
    reasons: list[str] = []

    words = _WORD_RE.findall(clean)
    if (
        len(clean) < 35
        or len(words) < 5
        or (len(clean) < 120 and not _COMPLETE_SENTENCE_END_RE.search(clean))
    ):
        return ContentAssessment("ocr_noise", False, 0.0, ("texto_curto",))

    compact = "".join(ch for ch in clean if not ch.isspace())
    alpha_ratio = sum(ch.isalpha() for ch in compact) / max(1, len(compact))
    replacement_ratio = clean.count("�") / max(1, len(clean))
    if alpha_ratio < 0.48 or replacement_ratio > 0.02:
        return ContentAssessment("ocr_noise", False, 0.0, ("ocr_inadequado",))

    prefix = folded[:500]
    sentence_count = len(_SENTENCE_MARK_RE.findall(clean))
    numeric_tokens = len(re.findall(r"(?<!\w)\d{1,4}(?!\w)", clean))
    note_markers = len(_BRACKETED_NOTE_RE.findall(clean))
    bare_note_markers = len(_BARE_NOTE_MARKER_RE.findall(clean))
    numbered_note_markers = len(_NUMBERED_NOTE_MARKER_RE.findall(clean))
    bible_references = len(_BIBLE_REFERENCE_RE.findall(clean))
    inline_pages = len(_INLINE_PAGE_RE.findall(clean))
    editorial_note_signals = len(_EDITORIAL_NOTE_RE.findall(folded))
    biographical_signals = len(_BIOGRAPHICAL_DATE_RE.findall(folded))
    life_date_ranges = len(_LIFE_DATE_RANGE_RE.findall(clean))
    biographical_note_signals = len(_BIOGRAPHICAL_NOTE_RE.findall(clean))
    bibliographical_note_signals = len(_BIBLIOGRAPHICAL_NOTE_RE.findall(clean))
    editorial_biography_signals = len(_EDITORIAL_BIOGRAPHY_RE.findall(clean))

    if _PUBLISHER_RE.search(folded) or _ISBN_RE.search(clean):
        publisher_signals = len(_PUBLISHER_RE.findall(folded)) + len(_ISBN_RE.findall(clean))
        if publisher_signals >= 2 or sentence_count <= 4:
            return ContentAssessment("publisher_ad", False, 0.0, ("material_editorial",))
    if _DIGITIZATION_BOILERPLATE_RE.search(folded):
        return ContentAssessment("digitization_boilerplate", False, 0.0, ("material_de_digitalizacao",))

    if _BIBLIOGRAPHY_RE.search(folded_section) or (
        _BIBLIOGRAPHY_RE.search(prefix) and (inline_pages >= 3 or _ISBN_RE.search(clean))
    ):
        return ContentAssessment("bibliography", False, 0.0, ("bibliografia",))
    scholarly_citations = len(_SCHOLARLY_CITATION_RE.findall(clean))
    if scholarly_citations >= 1 and (
        editorial_note_signals >= 1
        or len(re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}(?:-[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,})?\b", clean)) >= 2
    ):
        return ContentAssessment("bibliography", False, 0.0, ("comentario_bibliografico",))
    if _APPENDIX_RE.search(folded_section) or _APPENDIX_RE.search(folded):
        return ContentAssessment("appendix", False, 0.0, ("apendice_ou_anexo",))

    if _NOTES_WORD_RE.search(folded_section):
        return ContentAssessment("notes", False, 0.0, ("secao_de_notas",))
    if re.match(r"^\s*\[\d{1,3}\]", clean) and note_markers >= 2:
        return ContentAssessment("notes", False, 0.0, ("notas_numeradas",))
    if note_markers >= 6 and (bible_references >= 3 or sentence_count <= note_markers // 2 + 3):
        return ContentAssessment("notes", False, 0.0, ("bloco_de_notas",))
    if bare_note_markers >= 6 and (
        bible_references >= 3
        or editorial_note_signals >= 2
        or biographical_signals >= 3
    ):
        return ContentAssessment("notes", False, 0.0, ("notas_sem_colchetes",))
    if numbered_note_markers >= 6 and (
        life_date_ranges >= 3
        or biographical_note_signals >= 3
        or bibliographical_note_signals >= 3
    ):
        return ContentAssessment("notes", False, 0.0, ("notas_biograficas_numeradas",))
    if editorial_biography_signals >= 2:
        return ContentAssessment("introduction", False, 0.0, ("biografia_editorial",))
    if editorial_note_signals >= 3 and (bare_note_markers >= 2 or bible_references >= 2):
        return ContentAssessment("notes", False, 0.0, ("comentario_de_notas",))
    letter_note_markers = len(re.findall(r"(?:^|\s)[a-z]\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", clean))
    if letter_note_markers >= 2 and editorial_note_signals >= 2:
        return ContentAssessment("notes", False, 0.0, ("notas_alfabeticas",))
    if bible_references >= 7 and bible_references * 7 >= max(1, len(_WORD_RE.findall(clean))):
        return ContentAssessment("notes", False, 0.0, ("lista_de_referencias",))

    toc_heading = bool(_TOC_WORD_RE.search(folded_section) or _TOC_WORD_RE.search(prefix[:120]))
    word_count = len(words)
    number_density = numeric_tokens / max(1, word_count)
    numbered_title_transitions = len(
        re.findall(r"(?<!\w)\d{1,4}[.)]?\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", clean)
    )
    dense_numbered_titles = (
        numeric_tokens >= 10
        and number_density >= 0.09
        and numbered_title_transitions >= 8
    )
    repeated_front_headings = len(_FRONT_MATTER_RE.findall(folded)) >= 2
    if toc_heading or dense_numbered_titles or (
        numeric_tokens >= 14 and sentence_count <= 4 and repeated_front_headings
    ):
        return ContentAssessment("toc", False, 0.0, ("sumario_ou_indice",))

    explicit_body_section = bool(_BODY_SECTION_RE.search(folded_section))
    if not explicit_body_section and (
        _FRONT_MATTER_RE.search(folded_section) or _INTRO_HEADING_RE.search(folded[:120])
    ):
        return ContentAssessment("introduction", False, 0.0, ("secao_introdutoria",))

    author_key = _author_key(author)
    overview_signals = len(_OVERVIEW_RE.findall(folded))
    work_mentions = max(
        (len(re.findall(rf"\b{re.escape(key)}\b", folded)) for key in _work_keys(work_title)),
        default=0,
    )
    if author_key:
        author_mentions = len(re.findall(rf"\b{re.escape(author_key)}\b", folded))
        editorial_verbs = len(_EDITORIAL_VERBS_RE.findall(folded))
        reader_signal = bool(re.search(r"\b(?:o leitor|nesta obra|nas obras que|pensamento de)\b", folded))
        early_page = pdf_page is not None and pdf_page <= 40
        if author_mentions >= 1 and editorial_verbs >= 2 and (
            reader_signal or overview_signals or editorial_note_signals or early_page
        ):
            return ContentAssessment("introduction", False, 0.0, ("comentario_editorial_em_terceira_pessoa",))
        if author_mentions >= 2 and editorial_verbs >= 3:
            return ContentAssessment("introduction", False, 0.0, ("comentario_editorial_em_terceira_pessoa",))
        if (
            reader_signal or overview_signals >= 2 or biographical_signals >= 2
        ) and editorial_verbs >= 2:
            return ContentAssessment("introduction", False, 0.0, ("resumo_editorial",))
        author_adjective = {
            "irineu": "irene",
        }.get(author_key, author_key)
        adjective_mentions = len(
            re.findall(rf"\b{re.escape(author_adjective)}\w{{2,8}}\b", folded)
        )
        if (
            author_mentions == 0
            and adjective_mentions >= 2
            and editorial_verbs >= 3
        ):
            return ContentAssessment("introduction", False, 0.0, ("sintese_editorial_da_doutrina",))
    if work_mentions >= 1 and overview_signals >= 2 and editorial_verbs >= 1:
        return ContentAssessment("introduction", False, 0.0, ("apresentacao_da_obra",))

    quality = 1.0
    if sentence_count < 2:
        quality -= 0.35
        reasons.append("poucas_frases_completas")
    if note_markers >= 3:
        quality -= 0.2
        reasons.append("muitas_notas_inline")
    if numeric_tokens >= 18:
        quality -= 0.15
        reasons.append("muitos_numeros")
    if _FRONT_MATTER_RE.search(prefix) and not explicit_body_section:
        quality -= 0.2
        reasons.append("sinal_editorial")

    is_quotable = quality >= 0.55
    return ContentAssessment(
        "body" if is_quotable else "ocr_noise",
        is_quotable,
        round(max(0.0, quality), 3),
        tuple(reasons),
    )


def _query_tokens(query: str) -> list[str]:
    terms = [
        token for token in _WORD_RE.findall(fold_text(query))
        if len(token) >= 3 and token not in _STOP_WORDS
    ]
    # Keep passage selection consistent with the multilingual expansion used
    # by Elasticsearch (e.g. Eucaristia -> Eucharistia).
    try:
        from search.text_search import theological_query_expansions
        expansions = theological_query_expansions(query)
    except Exception:
        expansions = []
    for equivalent in expansions:
        for token in _WORD_RE.findall(fold_text(equivalent)):
            if len(token) >= 3 and token not in _STOP_WORDS and token not in terms:
                terms.append(token)
    return terms


def _protect_abbreviations(text: str) -> str:
    return re.sub(
        r"\b(Cf|cf|cap|caps|p|pp|vol|n|nn|S|St|Sto|Sta)\.",
        lambda match: match.group(0).replace(".", "§"),
        text,
    )


def _sentences(text: str) -> list[str]:
    protected = _protect_abbreviations(text)
    parts = re.split(
        r"(?<=[.!?…])(?:[\"”’»\]]*)\s+(?=(?:[\"“«(\[]?[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9]))",
        protected,
    )
    return [part.replace("§", ".").strip() for part in parts if part.strip()]


def _strip_incomplete_prefix(text: str) -> str:
    if not text:
        return text
    # Chunks overlap and frequently start halfway through a sentence. A quoted
    # passage must begin at the next demonstrable sentence boundary.
    first = text.lstrip()[:1]
    if first and (first.islower() or first in ",;:)]"):
        boundary = re.search(r"[.!?…](?:[\"”’»\]]*)\s+(?=[\"“«(\[]?[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", text)
        if boundary:
            return text[boundary.end():].strip()
    return text


def _strip_leading_heading(text: str) -> str:
    # Common OCR form: "Teologia da eucaristia 1 66. Este alimento...".
    heading = re.match(r"^[^.!?]{3,120}\s+(?:\d{1,3}\s+)?\d{1,3}\.\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", text)
    if heading:
        return text[heading.end():].strip()
    return text


def _strip_section_headings(text: str) -> str:
    """Remove catalogue-like headings without touching the following prose.

    Legacy chunks flatten page layout, producing sequences such as
    ``A eucaristia: verdadeiro sacrifício 1 41. Continuei: ...``.  A query
    occurrence inside that heading is metadata, not evidence for a quotation.
    """

    previous = None
    cleaned = text
    while previous != cleaned:
        previous = cleaned
        cleaned = _SECTION_HEADING_RE.sub(" ", cleaned)
        cleaned = _OCR_MERGED_HEADING_RE.sub(" ", cleaned)
        cleaned = _NUMBERED_SECTION_HEADING_RE.sub(" ", cleaned)
    return _SPACE_RE.sub(" ", cleaned).strip()


def _section_segments(text: str) -> list[str]:
    marker = " \u241e "
    marked = text
    for pattern in (
        _SECTION_HEADING_RE,
        _OCR_MERGED_HEADING_RE,
        _NUMBERED_SECTION_HEADING_RE,
    ):
        marked = pattern.sub(marker, marked)
    return [
        _strip_leading_heading(_strip_incomplete_prefix(part.strip()))
        for part in marked.split("\u241e")
        if part.strip()
    ]


def _truncate_before_following_heading(text: str) -> str:
    """Do not let a quotation leak into the heading of the next section."""
    boundary = re.search(
        r"\s+\d{1,4}\s+(?:cap[ií]tulo|livro|parte|homilia|serm[aã]o)\b",
        text,
        re.I,
    )
    if boundary and boundary.start() >= 35:
        return text[:boundary.start()].rstrip()
    return text


def extract_semantic_passage(
    text: str | None,
    *,
    section: str | None = None,
    author: str | None = None,
    work_title: str | None = None,
    pdf_page: int | None = None,
    min_chars: int = 120,
    max_chars: int = 700,
) -> str:
    """Return a coherent body passage for a multilingual semantic hit.

    Semantic retrieval supplies the topical anchor when the user's wording is
    in another language. This extractor never translates or repairs source
    words; it only selects complete sentences from source-faithful body text.
    """
    assessment = assess_content(
        text,
        section=section,
        author=author,
        work_title=work_title,
        pdf_page=pdf_page,
    )
    if not assessment.is_quotable:
        return ""
    clean = clean_ocr_text(text)
    segments = _section_segments(clean)
    best = ""
    best_score = float("-inf")
    for segment in segments:
        sentences = _sentences(segment)
        for start in range(len(sentences)):
            parts: list[str] = []
            for sentence in sentences[start:start + 6]:
                candidate = _strip_leading_heading(" ".join(parts + [sentence]).strip())
                if len(candidate) > max_chars:
                    break
                parts.append(sentence)
                if len(candidate) < min(min_chars, max(35, len(segment))):
                    continue
                if not _COMPLETE_SENTENCE_END_RE.search(candidate):
                    continue
                candidate = _truncate_before_following_heading(candidate)
                candidate_assessment = assess_content(
                    candidate,
                    section=section,
                    author=author,
                    work_title=work_title,
                    pdf_page=pdf_page,
                )
                if not candidate_assessment.is_quotable:
                    continue
                score = candidate_assessment.quality_score * 10
                score -= abs(len(candidate) - 430) / 60
                if score > best_score:
                    best = candidate
                    best_score = score
    return _SPACE_RE.sub(" ", best).strip()


def extract_query_passage(
    text: str | None,
    query: str,
    *,
    section: str | None = None,
    author: str | None = None,
    work_title: str | None = None,
    pdf_page: int | None = None,
    min_chars: int = 160,
    max_chars: int = 700,
) -> str:
    assessment = assess_content(
        text,
        section=section,
        author=author,
        work_title=work_title,
        pdf_page=pdf_page,
    )
    if not assessment.is_quotable:
        return ""

    clean = clean_ocr_text(text)
    segments = _section_segments(clean)
    if not segments:
        return ""

    # A short, self-contained patristic sentence is still a valid quotation.
    # Lower the requested window only when the whole source chunk is shorter;
    # the content assessment above still rejects labels and OCR fragments.
    tokens = _query_tokens(query)
    folded_query = fold_text(query)
    best = ""
    best_score = float("-inf")

    for segment in segments:
        sentences = _sentences(segment)
        for start in range(len(sentences)):
            folded_anchor_sentence = fold_text(sentences[start])
            anchor_token_hits = sum(
                folded_anchor_sentence.count(token) for token in tokens
            )
            anchor_exact_hit = bool(folded_query and folded_query in folded_anchor_sentence)
            if tokens:
                if anchor_token_hits == 0:
                    continue
            elif folded_query and not anchor_exact_hit:
                continue

            available_tail = " ".join(sentences[start:start + 6])[:max_chars]
            effective_min_chars = min(min_chars, max(35, len(available_tail)))
            parts: list[str] = []
            for sentence in sentences[start:start + 6]:
                candidate = _strip_leading_heading(" ".join(parts + [sentence]).strip())
                if len(candidate) > max_chars:
                    break
                parts.append(sentence)
                if len(candidate) < effective_min_chars:
                    continue
                if not _COMPLETE_SENTENCE_END_RE.search(candidate):
                    continue
                candidate_assessment = assess_content(
                    candidate,
                    section=section,
                    author=author,
                    work_title=work_title,
                    pdf_page=pdf_page,
                )
                if not candidate_assessment.is_quotable:
                    continue

                folded_candidate = fold_text(candidate)
                token_hits = sum(folded_candidate.count(token) for token in tokens)
                exact_hit = bool(folded_query and folded_query in folded_candidate)
                if tokens:
                    if token_hits == 0:
                        continue
                elif folded_query and not exact_hit:
                    continue
                score = token_hits * 14 + (45 if exact_hit else 0)
                score += candidate_assessment.quality_score * 10
                score -= abs(len(candidate) - 430) / 45
                first_query_position = min(
                    (folded_candidate.find(token) for token in tokens if token in folded_candidate),
                    default=0,
                )
                score -= first_query_position / 18
                if score > best_score:
                    best = candidate
                    best_score = score

    # A chunk can be semantically relevant while its opening paragraph is not.
    # Without a textual anchor we cannot truthfully label any sentence as the
    # requested quotation, so return no card instead of guessing a passage.
    if not best:
        return ""

    best = _truncate_before_following_heading(best)
    best = _BRACKETED_NOTE_RE.sub("", best)
    best = re.sub(r"(?<=[.!?])\d{1,3}(?=\s|$)", "", best)
    return _SPACE_RE.sub(" ", best).strip()


def _dedupe_signature(hit: SearchHitLike) -> tuple[int | None, set[tuple[str, ...]], str]:
    normalized = fold_text(hit.translation_text or hit.text)
    tokens = [token for token in _WORD_RE.findall(normalized) if len(token) >= 2]
    width = 4
    shingles = {
        tuple(tokens[index:index + width])
        for index in range(max(0, len(tokens) - width + 1))
    }
    return hit.book_id, shingles, normalized


def _near_duplicate(
    left: tuple[int | None, set[tuple[str, ...]], str],
    right: tuple[int | None, set[tuple[str, ...]], str],
) -> bool:
    left_book_id, left_shingles, left_text = left
    right_book_id, right_shingles, right_text = right
    if left_book_id is not None and right_book_id is not None and left_book_id != right_book_id:
        return False
    if not left_text or not right_text:
        return False
    if left_text in right_text or right_text in left_text:
        return min(len(left_text), len(right_text)) >= 90
    if not left_shingles or not right_shingles:
        return False
    shared = len(left_shingles.intersection(right_shingles))
    containment = shared / max(1, min(len(left_shingles), len(right_shingles)))
    return containment >= 0.72


def filter_quotable_hits(
    hits: Iterable[TSearchHit],
    query: str,
    *,
    limit: int,
    replace_hit,
) -> list[TSearchHit]:
    """Return ranked body-text passages and discard editorial/index noise.

    ``replace_hit`` is injected to keep this module independent from the
    concrete search dataclass (normally ``dataclasses.replace``).
    """

    accepted: list[TSearchHit] = []
    accepted_signatures: list[tuple[int | None, set[tuple[str, ...]], str]] = []
    for hit in hits:
        original = hit.text or ""
        translation = hit.translation_text or ""
        chunk_author = getattr(hit, "chunk_author", None)
        if not _chunk_attribution_is_specific(hit.author, chunk_author, hit.work_title):
            continue
        effective_author = _effective_author(hit.author, chunk_author, hit.work_title)
        if fold_text(effective_author) in _GENERIC_BOOK_AUTHORS:
            # A collective volume without per-chunk attribution cannot be
            # presented truthfully as a quotation of a specific Father. Some
            # legacy PL/PG imports repeat the same generic label in
            # ``chunk_author``; that does not turn the apparatus into an
            # attributable primary-source passage.
            continue
        original_assessment = assess_content(
            original,
            section=hit.chapter_or_section,
            author=effective_author,
            work_title=hit.work_title,
            pdf_page=hit.pdf_page,
        )
        translation_assessment = assess_content(
            translation,
            section=hit.chapter_or_section,
            author=effective_author,
            work_title=hit.work_title,
            pdf_page=hit.pdf_page,
        ) if translation else ContentAssessment("missing", False, 0.0)

        original_folded = fold_text(original)
        translation_folded = fold_text(translation)
        query_tokens = _query_tokens(query)
        original_matches = sum(original_folded.count(token) for token in query_tokens)
        translation_matches = sum(translation_folded.count(token) for token in query_tokens)
        use_translation = (
            translation_assessment.is_quotable
            and (not original_assessment.is_quotable or translation_matches > original_matches)
        )

        if use_translation:
            passage = extract_query_passage(
                translation,
                query,
                section=hit.chapter_or_section,
                author=effective_author,
                work_title=hit.work_title,
                pdf_page=hit.pdf_page,
            )
            if not passage:
                continue
            candidate = replace_hit(
                hit,
                author=effective_author,
                text="",
                translation_text=passage,
            )
        else:
            if not original_assessment.is_quotable:
                continue
            passage = extract_query_passage(
                original,
                query,
                section=hit.chapter_or_section,
                author=effective_author,
                work_title=hit.work_title,
                pdf_page=hit.pdf_page,
            )
            if not passage:
                continue
            candidate = replace_hit(
                hit,
                author=effective_author,
                text=passage,
                translation_text=None,
            )

        signature = _dedupe_signature(candidate)
        if any(_near_duplicate(signature, existing) for existing in accepted_signatures):
            continue
        accepted.append(candidate)
        accepted_signatures.append(signature)
        if len(accepted) >= max(0, limit):
            break
    return accepted
