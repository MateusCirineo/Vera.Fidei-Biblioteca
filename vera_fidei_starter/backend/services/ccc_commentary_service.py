"""Exact-article retrieval for patristic commentary on the Catechism.

The public CCC feature used to turn an article number into one of a handful of
section-wide keyword lists.  That makes every article inside a large interval
return the same search.  This module deliberately keeps the replacement
isolated from the HTTP route:

* read the authoritative ``Catecismo da Igreja Catolica`` book (collection
  ``CIC``) already ingested in PostgreSQL;
* extract the requested numbered article, including its source chunk/page;
* derive the search query only from that exact article;
* ask Elasticsearch for patristic collections and then enforce the allowed
  chunk IDs again against PostgreSQL;
* fail closed when either the exact CCC source or the patristic allow-list is
  unavailable.

The route can integrate this service later without changing the data model.
Until then, importing this module has no database or Elasticsearch side effect.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Protocol, Sequence

from data.ccc_structure import find_ccc_section


CCC_MIN_ARTICLE = 1
CCC_MAX_ARTICLE = 2865
STRICT_PATRISTIC_COLLECTIONS = (
    "PL",
    "PG",
    "PO",
    "PT",
    "Patrística EN",
    "Patrística LA",
    "Patrística PT",
    "DIDAQUE",
)


class CccQueryMode(str, Enum):
    EXACT_ARTICLE = "exact_article"
    SOURCE_UNAVAILABLE = "source_unavailable"


@dataclass(frozen=True)
class CccSourceChunk:
    book_id: int
    chunk_id: int
    sequence_index: int | None
    text: str
    pdf_page: int | None = None


@dataclass(frozen=True)
class CccArticle:
    number: int
    text: str
    source_book_id: int
    source_chunk_ids: tuple[int, ...]
    source_pages: tuple[int, ...]

    @property
    def fingerprint(self) -> str:
        clean = re.sub(r"\s+", " ", self.text).strip()
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()


class PdfCccCorpus:
    """Article index built from the typography of the indexed CCC PDF.

    The database chunks are rolling search windows and therefore repeat one
    hundred words.  They also flatten bold section headings, page numbers and
    tables into prose.  The source PDF preserves paragraph markers as regular
    body lines and navigation as bold lines.  Reading those lines directly is
    the only reliable way to honor the UI promise of one exact paragraph.
    """

    _ARTICLE_LINE_RE = re.compile(r"^\s*([1-9]\d{0,3})\s*\.\s*(.*)$")
    _BODY_FONT_MAX = 12.6
    # These captions are printed *inside* their numbered paragraph. The
    # definition/quotation that follows is therefore paragraph content, unlike
    # normal section headings, which close the preceding paragraph. Keeping a
    # tiny source-audited allow-list is safer than guessing from punctuation or
    # page breaks (both occur inside legitimate CCC text).
    _INLINE_HEADINGS = {
        205: frozenset({'"eu sou aquele que e"'}),
        1471: frozenset({"que e a indulgencia?"}),
    }
    _HEADING_PREFIX_RE = re.compile(
        r"^(?:(?:ARTIGO|CAP[IÍ]TULO|PAR[AÁ]GRAFO)\b|"
        r"(?:PRIMEIR[AO]|SEGUND[AO]|TERCEIR[AO]|QUART[AO])\s+(?:PARTE|SE[CÇ][AÃ]O)\b|"
        r"(?:PARTE|SE[CÇ][AÃ]O)\s+(?:[IVXLCDM]+|\d+)\b|"
        r"[IVXLCDM]+\.\s)",
        re.IGNORECASE,
    )

    def __init__(self, pdf_path: str, *, book_id: int, chunk_ids: Sequence[int] = ()) -> None:
        self._articles: dict[int, CccArticle] = {}
        self._build(pdf_path, book_id=book_id, chunk_ids=chunk_ids)

    @staticmethod
    def _line_style(line: dict[str, Any]) -> tuple[bool, float, str]:
        spans = [span for span in line.get("spans", ()) if (span.get("text") or "").strip()]
        if not spans:
            return False, 0.0, ""
        first = spans[0]
        total_characters = sum(len(str(span.get("text") or "").strip()) for span in spans)
        bold_characters = sum(
            len(str(span.get("text") or "").strip())
            for span in spans
            if int(span.get("flags") or 0) & 16
        )
        return (
            bool(total_characters and bold_characters / total_characters >= 0.75),
            float(first.get("size") or 0.0),
            str(first.get("font") or ""),
        )

    @classmethod
    def _is_inline_heading(cls, article: int, text: str) -> bool:
        folded = unicodedata.normalize("NFKD", text.casefold())
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
        folded = re.sub(r"\s+", " ", folded).strip()
        return folded in cls._INLINE_HEADINGS.get(article, ())

    @classmethod
    def _is_body_marker(cls, line: dict[str, Any]) -> bool:
        bold, size, _font = cls._line_style(line)
        return size <= cls._BODY_FONT_MAX and not bold

    @classmethod
    def _is_body_continuation(cls, line: dict[str, Any], text: str) -> bool:
        bold, size, _font = cls._line_style(line)
        if size <= 0 or size > cls._BODY_FONT_MAX:
            return False
        if not bold:
            return True
        # Some source quotations and bullet lists are intentionally bold in
        # this edition (CCC 76). Editorial headings, by contrast, are compact
        # title lines. Accept bold lines only when they read like continuing
        # prose: a bullet or a line ending in normal sentence punctuation.
        stripped = text.strip()
        if cls._HEADING_PREFIX_RE.match(stripped):
            return False
        words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}", stripped)
        all_caps = bool(words) and all(word == word.upper() for word in words)
        if all_caps and len(words) <= 12 and not stripped.startswith(("- ", "• ")):
            return False
        # A fully-bold compact line is a caption/heading in this edition. Long
        # prose and list items may legitimately be bold; wrapped short tails
        # are handled with their preceding line in ``_build``.
        return stripped.startswith(("- ", "• ")) or (len(words) >= 9 and not all_caps)

    def _build(self, pdf_path: str, *, book_id: int, chunk_ids: Sequence[int]) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - production dependency is pinned.
            import fitz as pymupdf  # type: ignore

        collected: dict[int, list[str]] = {}
        pages: dict[int, list[int]] = defaultdict(list)
        current: int | None = None
        expected = CCC_MIN_ARTICLE
        body_closed = False

        with pymupdf.open(pdf_path) as document:
            for page_index, page in enumerate(document):
                page_number = page_index + 1
                # Paragraphs can cross a physical page; page numbers are merely
                # skipped and do not clear ``current``.
                for block_index, block in enumerate(page.get_text("dict").get("blocks", ())):
                    for line in block.get("lines", ()):
                        text = re.sub(
                            r"\s+",
                            " ",
                            "".join(span.get("text") or "" for span in line.get("spans", ())),
                        ).strip()
                        if not text:
                            continue
                        marker = self._ARTICLE_LINE_RE.match(text)
                        if marker is not None:
                            number = int(marker.group(1))
                            # The source body is a strict 1..2865 sequence. This
                            # rejects footnote/list numbers and the final index,
                            # both of which otherwise look like paragraph marks.
                            if number == expected and self._is_body_marker(line):
                                current = number
                                expected += 1
                                body_closed = False
                                collected.setdefault(number, [])
                                pages[number].append(page_number)
                                remainder = marker.group(2).strip()
                                if remainder:
                                    collected[number].append(remainder)
                                continue

                        # The next sequential marker is the hard boundary. A
                        # compact heading closes public paragraph content while
                        # page numbers/navigation are ignored and cross-page
                        # prose, quotations and lists continue normally.
                        if current is None:
                            continue
                        if re.fullmatch(r"\d{1,4}", text):
                            if current == CCC_MAX_ARTICLE:
                                current = None
                            continue
                        if text.casefold().startswith("(parágrafo") or text.casefold().startswith("(parágrafos"):
                            continue
                        if body_closed:
                            continue
                        if self._is_inline_heading(current, text):
                            continue
                        if not self._is_body_continuation(line, text):
                            bold, _size, _font = self._line_style(line)
                            previous = collected.get(current, [])[-1] if collected.get(current) else ""
                            first_letter = next((char for char in text if char.isalpha()), "")
                            wrapped_bold_tail = (
                                bold
                                and bool(previous)
                                and not previous.rstrip().endswith((".", "!", "?", '"', "”", "»", ")"))
                                and first_letter.islower()
                            )
                            if wrapped_bold_tail:
                                collected[current].append(text)
                                pages[current].append(page_number)
                                continue
                            # A compact typographic heading normally starts the
                            # next section, so neither it nor an intervening
                            # epigraph/table belongs to paragraph N. Two source-
                            # audited captions are embedded in their paragraph.
                            body_closed = True
                            continue
                        collected[current].append(text)
                        pages[current].append(page_number)

        for number in range(CCC_MIN_ARTICLE, CCC_MAX_ARTICLE + 1):
            text = re.sub(r"\s+", " ", " ".join(collected.get(number, ()))).strip()
            if len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}", text)) < 4:
                continue
            self._articles[number] = CccArticle(
                number=number,
                text=text,
                source_book_id=book_id,
                # The paragraph is sourced directly from the PDF.  Chunk IDs
                # would be misleading here (all 653 rolling windows previously
                # leaked into every response), so coordinates are page-based.
                source_chunk_ids=(),
                source_pages=tuple(dict.fromkeys(pages.get(number, ()))),
            )

    def get_article(self, article: int) -> CccArticle | None:
        _validate_article_number(article)
        return self._articles.get(article)


@dataclass(frozen=True)
class CccArticleQuery:
    article: int
    section_title: str
    section_start: int
    section_end: int
    mode: CccQueryMode
    query: str
    article_text: str | None
    article_fingerprint: str | None
    key_terms: tuple[str, ...]
    quoted_phrases: tuple[str, ...]
    scripture_references: tuple[str, ...]
    patristic_mentions: tuple[str, ...]
    source_book_id: int | None
    source_chunk_ids: tuple[int, ...]
    source_pages: tuple[int, ...]
    warning: str | None = None

    @property
    def is_exact(self) -> bool:
        return self.mode is CccQueryMode.EXACT_ARTICLE

    def response_metadata(self) -> dict[str, Any]:
        """Stable fields a route should expose so the UI can explain/highlight.

        ``article_text`` is the actual CCC paragraph, never a section summary.
        ``query_terms`` contains the normalized, article-specific vocabulary
        sent to retrieval.  These fields make it possible for the UI to label
        exact versus unavailable-source results without guessing.
        """

        return {
            "article": self.article,
            "section_title": self.section_title,
            "article_text": self.article_text,
            "query_terms": list(self.key_terms),
            "quoted_phrases": list(self.quoted_phrases),
            "scripture_references": list(self.scripture_references),
            "patristic_mentions": list(self.patristic_mentions),
            "query_mode": self.mode.value,
            "article_fingerprint": self.article_fingerprint,
            "source_book_id": self.source_book_id,
            "source_chunk_ids": list(self.source_chunk_ids),
            "source_pages": list(self.source_pages),
            "warning": self.warning,
        }


@dataclass(frozen=True)
class CccCommentarySearchResult:
    context: CccArticleQuery
    hits: tuple[Any, ...]
    candidate_count: int
    rejected_chunk_ids: tuple[int, ...]
    warning: str | None = None

    @property
    def hit_ids(self) -> tuple[int, ...]:
        return tuple(int(hit.chunk_id) for hit in self.hits)


class CccArticleSource(Protocol):
    def get_article(self, article: int) -> CccArticle | None: ...


class PatristicChunkFilter(Protocol):
    def patristic_book_ids(self) -> list[int]: ...

    def allowed_chunk_ids(self, chunk_ids: Sequence[int]) -> set[int]: ...


class AcervoSearchClient(Protocol):
    def search_acervo(
        self,
        query: str,
        limit: int = 20,
        author_filter: str = "",
        query_language: str = "unknown",
        collection_filter: str = "",
        patristic_book_ids: list[int] | None = None,
    ) -> list[Any]: ...

    def search_acervo_hybrid(
        self,
        query: str,
        limit: int = 20,
        author_filter: str = "",
        query_language: str = "unknown",
        collection_filter: str = "",
        patristic_book_ids: list[int] | None = None,
    ) -> list[Any]: ...


@dataclass(frozen=True)
class _ChunkSpan:
    chunk: CccSourceChunk
    start: int
    end: int


@dataclass(frozen=True)
class _MarkerState:
    start: int
    end: int
    chain_length: int
    next_start: int | None


_BODY_ANCHOR_RE = re.compile(
    r"I\.\s*A\s+vida\s+do\s+homem\s+conhecer\s+e\s+amar\s+a\s+Deus",
    re.IGNORECASE,
)
_INDEX_AFTER_BODY_RE = re.compile(
    r"Catecismo\s+da\s+Igreja\s+Cat[oó]lica\s+[ÍI]ndice\s+Geral",
    re.IGNORECASE,
)
_GENERIC_ARTICLE_MARKER_RE = re.compile(r"(?<![\d,])([1-9]\d{0,3})\s*\.")


_RELATED_PARAGRAPHS_RE = re.compile(
    r"\s*\(Par[aá]grafos?\s+relacionados?\s*:?[  ]*[^)]*\)",
    re.IGNORECASE,
)
_TRAILING_PAGE_RE = re.compile(r"(?<=[.!?…»”\"')\]])\s+\d{1,4}\s*$")
_STRUCTURAL_HEADING_RE = re.compile(
    r"\s+(?:(?P<page>\d{1,4})\s+)?(?:"
    r"(?:ARTIGO|CAP[IÍ]TULO|PAR[AÁ]GRAFO)\s+"
    r"(?:\d{1,4}|[IVXLCDM]+)\s*(?::|[.\-–—])\s*"
    r"(?=[\"“«]?(?:\.\.\.)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ])"
    r"|(?:PRIMEIR[AO]|SEGUND[AO]|TERCEIR[AO]|QUART[AO]|QUINT[AO])\s+"
    r"(?:PARTE|SE[CÇ][AÃ]O)\b"
    r"|(?:PARTE|SE[CÇ][AÃ]O)\s+"
    r"(?:\d{1,4}|[IVXLCDM]+|PRIMEIR[AO]|SEGUND[AO]|TERCEIR[AO]|QUART[AO]|QUINT[AO])\b"
    r")",
    re.IGNORECASE,
)
_ROMAN_SECTION_HEADING_RE = re.compile(
    r"\s+(?P<roman>[IVXLCDM]{1,8})\.\s+(?=[\"“«]?[A-ZÁÉÍÓÚÂÊÔÃÕÇ])"
)
_TRAILING_ROMAN_HEADING_RE = re.compile(
    r"\s+(?:\d{1,3}\s+)?[IVXLCDM]+\.\s+"
    r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.!?]{2,100}\??\s*$",
)
_INLINE_PAGE_ROMAN_HEADING_RE = re.compile(
    r"\s+\d{1,3}\s+[IVXLCDM]+\.\s+"
    r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.!?]{2,120}\?",
)
# This exact heading is flattened after CCC 2558 together with the epigraph of
# the following section.  A generic all-caps-question rule is unsafe: CCC 1471
# itself contains ``QUE É A INDULGÊNCIA?`` followed by the definition that the
# user explicitly asked to read.
_AUDITED_QUESTION_BOUNDARY_RE = re.compile(
    r"\s+O\s+QUE\s+É\s+A\s+ORAÇÃO\?",
    re.IGNORECASE,
)
_TRAILING_ALL_CAPS_WITH_PAGE_RE = re.compile(
    r"\s+(?P<title>[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇÀÈÌÒÙÜ\s'’\-–—:]{4,120})"
    r"\s+(?P<page>\d{1,4})\s*$"
)
_TRAILING_ALL_CAPS_HEADING_RE = re.compile(
    r"(?<=[.!?…»”\"])\s+"
    r"(?P<title>[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇÀÈÌÒÙÜ\s'’\-–—:]{4,160})\s*$"
)
_TRAILING_BARE_ALL_CAPS_HEADING_RE = re.compile(
    r"\s+(?P<title>[\"“«]?[A-ZÁÉÍÓÚÂÊÔÃÕÇ]"
    r"[A-ZÁÉÍÓÚÂÊÔÃÕÇÀÈÌÒÙÜ\s'’\-–—:,.;!?…\"”»]{12,200})\s*$"
)
_INLINE_PAGE_RE = re.compile(r"\s+\d{1,4}\s+")

# The indexed CCC edition flattens a finite set of printed navigation headings
# between paragraph N and marker N+1.  These phrases were audited across all
# 2,865 paragraphs.  Matching the exact suffix (instead of arbitrary capitals)
# lets us remove headings even when OCR lost the preceding punctuation, while
# preserving legitimate emphatic prose such as ``DEUS É AMOR`` inside a quote.
_CCC_NAVIGATION_SUFFIXES = tuple(
    sorted(
        {
            "A ABERTURA - FECUNDIDADE",
            "A ABERTURA · FECUNDIDADE",
            "A ALIANÇA COM NOÉ",
            "A IDOLATRIA",
            "A IGREJA É A ESPOSA DE CRISTO",
            '"EM NOME DE TODA A IGREJA"',
            "EM NOME DE TODA A IGREJA",
            '"CURAI OS ENFERMOS..."',
            "CURAI OS ENFERMOS",
            'MARIA - "SEMPRE VIRGEM"',
            "MARIA - SEMPRE VIRGEM",
            "OS INSTITUTOS SECULARES",
            "A MORTE",
            "A ORDENAÇÃO EPISCOPAL - PLENITUDE DO SACRAMENTO DA ORDEM",
            "AS CARACTERÍSTICAS DO POVO DE DEUS",
            "ACIMA DE TUDO A CARIDADE",
            "À ESPERA DE QUE TUDO LHE SEJA SUBMETIDO",
            "CONSELHOS EVANGÉLICOS, VIDA CONSAGRADA",
            "CRER EM JESUS CRISTO, O FILHO DE DEUS",
            "CRER SOMENTE EM DEUS",
            'II. "SEI EM QUEM PUS MINHA FÉ" (2TM 1,12) CRER SOMENTE EM DEUS',
            "DEUS É AMOR",
            "DEUS FORMA SEU POVO ISRAEL",
            "DISTINÇÃO DAS VIRTUDES CARDEAIS",
            "EM CASO DE DOENÇA GRAVE",
            "EVITAR A GUERRA",
            "FAÇA-SE EM MIM SEGUNDO A TUA PALAVRA",
            "INCORPORADOS À IGREJA, CORPO DE CRISTO",
            "JESUS ENSINA A ORAR",
            "NA CEIA, JESUS ANTECIPOU A OFERTA LIVRE DE SUA VIDA",
            "NOSSA COMUNHÃO NOS MISTÉRIOS DE JESUS",
            "O ADVENTO GLORIOSO DE CRISTO, ESPERANÇA DE ISRAEL",
            "O BATISMO DOS ADULTOS",
            "O COLÉGIO EPISCOPAL E SEU CHEFE, O PAPA",
            "O MEMORIAL SACRIFICAL DE CRISTO E DE SEU CORPO, A IGREJA",
            "OS MISTÉRIOS DA INFÂNCIA E DA VIDA OCULTA DE JESUS",
            "OS MISTÉRIOS DA INFÂNCIA DE JESUS",
            "OS SÍMBOLOS DA IGREJA",
            "OS SENTIDOS DA ESCRITURA",
            "OS SINAIS DO REINO DE DEUS",
            "PARA A REMISSÃO DOS PECADOS",
            "POVO DE DEUS",
            "RESUMINDO",
            "SEPULTADOS COM CRISTO",
            "TOTALMENTE UNIDA A SEU FILHO",
            "UM DURO COMBATE",
            "UMA CRIATURA NOVA",
            "UMA FONTE COMUM",
            "UMA GRANDE ÁRVORE COM MUITOS RAMOS",
            "... ASSIM COMO NÓS PERDOAMOS A QUEM NOS TEM OFENDIDO",
            "ASSIM",
            "... ESTÁ PRESENTE NA LITURGIA TERRESTRE",
            "... QUE PARTICIPA DA LITURGIA CELESTE",
        },
        key=len,
        reverse=True,
    )
)


def _strip_audited_navigation_suffix(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).casefold()
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    for suffix in _CCC_NAVIGATION_SUFFIXES:
        normalized = unicodedata.normalize("NFKD", suffix).casefold()
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        # Printed page numbers may sit before or after the heading. Ellipses
        # and quote marks are edition decoration, not paragraph content.
        pattern = re.compile(
            rf"(?:\s+\d{{1,4}})?\s+[.\"'«»“”]*{re.escape(normalized)}"
            rf"[.\"'«»“”…]*(?:\s+\d{{1,4}})?\s*$"
        )
        match = pattern.search(folded)
        if match is not None:
            matched_source = text[match.start():]
            before = text[:match.start()].rstrip()
            has_printed_page = re.search(r"\b\d{1,4}\b", matched_source) is not None
            # The short formula can also be legitimate emphatic prose. Keep
            # quoted/colon-introduced uses; the audited heading carries a page.
            if suffix == "DEUS É AMOR" and not has_printed_page and (
                before.endswith(":")
                or re.fullmatch(r'\s*["“«]DEUS É AMOR["”»]\s*', matched_source)
            ):
                continue
            return text[:match.start()].rstrip()
    return text


def _strip_truncated_structural_suffix(text: str) -> str:
    """Remove a structural heading even when the N+1 marker cut its tail.

    A few OCR chunks place the next numbered paragraph marker inside a heading;
    marker extraction therefore hands this cleaner only a prefix such as
    ``74 PARÁGRAFO 2- \"...CONCEBIDO``.  The numbered structural token is
    already authoritative, so the incomplete title must not leak into §N.
    """

    match = re.search(
        r"\s+(?:\d{1,4}\s+)?(?:ARTIGO|CAP[IÍ]TULO|PAR[AÁ]GRAFO)\s+"
        r"(?:\d{1,4}|[IVXLCDM]+)\s*(?::|[.\-–—])",
        text,
        re.IGNORECASE,
    )
    if match is None or len(text) - match.start() > 900:
        return text
    before = text[:match.start()].rstrip()
    if not before:
        return text
    tail = text[match.end():].strip()
    tail_words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}", tail)
    uppercase_words = [word for word in tail_words if word == word.upper()]
    # An inline reference such as ``O ARTIGO 1: A REGRA afirma...`` continues
    # as ordinary prose. Truncated source headings end in capitals/decoration
    # because marker N+1 cut their title before its next lowercase sentence.
    if tail_words and len(uppercase_words) * 2 < len(tail_words):
        return text
    return before


def _first_tail_boundary(text: str, pattern: re.Pattern[str], *, max_tail: int = 900) -> int | None:
    """Return the first heading match that belongs to the flattened tail."""

    for match in pattern.finditer(text):
        if match.start() > 0 and len(text) - match.start() <= max_tail:
            return match.start()
    return None


def _looks_like_structural_tail(text: str, match: re.Match[str]) -> bool:
    """Distinguish a bare source heading from an inline mention of an article."""

    tail = text[match.end():].strip()
    if not tail:
        return True
    if re.search(r"\s+[IVXLCDM]+\.\s+", tail[:350]):
        return True
    if re.search(r"\b(?:ARTIGO|CAP[IÍ]TULO|PAR[AÁ]GRAFO)\b", tail, re.IGNORECASE):
        return True
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}", tail)
    uppercase_words = [word for word in words if word == word.upper()]
    return len(uppercase_words) >= 2 and len(uppercase_words) * 4 >= len(words) * 3


def _sentence_boundary_before(text: str, position: int) -> bool:
    """Whether a flattened heading begins after completed prose/navigation."""

    before = text[:position].rstrip()
    if before.endswith((".", "!", "?", "…", "»", "”", '"', "'", ")", "]")):
        return True
    related = _RELATED_PARAGRAPHS_RE.search(before)
    return related is not None and related.end() == len(before)


def _bare_all_caps_boundary(text: str) -> int | None:
    """Find an unpunctuated terminal heading without eating short emphasis.

    The source has a small class of headings appended directly to prose, e.g.
    ``... uma criatura CRER EM JESUS CRISTO, O FILHO DE DEUS`` and
    ``... (Hb 5,7-9) JESUS ENSINA A ORAR``.  Four or more capitalized tokens,
    outside quotation/colon syntax, are required; the common emphatic sentence
    ``DEUS É AMOR`` therefore remains content.
    """

    match = _TRAILING_BARE_ALL_CAPS_HEADING_RE.search(text)
    if match is None:
        return None
    title = match.group("title").strip()
    words = re.findall(r"[A-ZÁÉÍÓÚÂÊÔÃÕÇÀÈÌÒÙÜ]+", title)
    before = text[:match.start()].rstrip()
    if (
        len(words) < 4
        or not before
        or before.endswith((":", "\"", "“", "«"))
        # A terminal quote may legitimately switch to emphatic capitals in
        # its final sentence (CCC 826). Headings are outside quoted prose.
        or text.rstrip().endswith(('"', "”", "»"))
    ):
        return None
    return match.start()


def _remove_repeated_page_overlap(text: str) -> str:
    """Drop a page-overlap restart only when its long tail already occurs verbatim.

    OCR chunks overlap at some page boundaries.  A physical page number can then
    be followed by a second copy of the end of the same CCC paragraph.  Requiring
    an earlier, long near-complete copy keeps ordinary numbers and repeated short
    formulas untouched.
    """

    for match in reversed(tuple(_INLINE_PAGE_RE.finditer(text))):
        tail = text[match.end():].strip()
        if len(tail) < 100:
            continue
        # Find the longest prefix of the post-page tail that is a suffix of
        # the preceding text. Keep the preceding copy and append only the new
        # continuation. The former implementation dropped that continuation,
        # truncating paragraphs 601 and 688.
        previous = text[:match.start()].rstrip()
        max_overlap = min(len(previous), len(tail))
        overlap = 0
        for size in range(max_overlap, 79, -1):
            if previous.endswith(tail[:size]):
                overlap = size
                break
        if overlap:
            continuation = tail[overlap:].lstrip()
            return f"{previous} {continuation}".rstrip()
    return text


def clean_ccc_article_text(text: str) -> str:
    """Remove edition/navigation matter that sits between CCC paragraph markers.

    The ingested edition flattens page numbers, section headings and web-style
    ``Parágrafos relacionados`` links into the same text stream as the numbered
    paragraphs.  Those elements occur *after* a paragraph but before the next
    numeric marker, so marker-based extraction alone would falsely present them
    as part of the Catechism.  This function is deliberately conservative: it
    removes only known navigation annotations and trailing heading patterns.
    """

    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return ""

    clean = _strip_audited_navigation_suffix(clean)
    clean = _strip_truncated_structural_suffix(clean)

    # Strong structural markers occur only in the flattened tail.  Including an
    # optional physical page number makes ``14 CAPÍTULO II ...`` and
    # ``332 CAPÍTULO I ...`` disappear as one unit instead of leaving the page.
    structural = next(
        (
            match
            for match in _STRUCTURAL_HEADING_RE.finditer(clean)
            if match.start() > 0 and len(clean) - match.start() <= 900
        ),
        None,
    )
    if structural is not None:
        before = clean[:structural.start()].rstrip()
        related = _RELATED_PARAGRAPHS_RE.search(before)
        ends_with_related_navigation = related is not None and related.end() == len(before)
        # A page-prefixed structure is a hard boundary in this edition.  A bare
        # heading must follow completed prose; this prevents a quoted inline
        # reference such as ``o ARTIGO 1: ... afirma`` from being truncated.
        parenthetical_prose = before.endswith("(A") and re.match(
            r"\s+(?:PRIMEIR[AO]|SEGUND[AO]|TERCEIR[AO]|QUART[AO]|QUINT[AO])\s+"
            r"(?:PARTE|SE[CÇ][AÃ]O)\s+d[oa]\b",
            clean[structural.start():],
            re.IGNORECASE,
        )
        if not parenthetical_prose and (
            structural.group("page") is not None
            or ends_with_related_navigation
            or before.endswith((".", "!", "?", "…", "»", "”", '"', "'"))
            or _looks_like_structural_tail(clean, structural)
        ):
            clean = before

    # Roman-numbered subsections are headings only when they follow completed
    # prose or a navigation annotation.  This preserves ordinary prose such as
    # ``desde o século II. Mas ...`` while cutting ``... (Ef 1,6). II. A obra``.
    roman = next(
        (
            match
            for match in _ROMAN_SECTION_HEADING_RE.finditer(clean)
            if match.start() > 0
            and len(clean) - match.start() <= 900
            and _sentence_boundary_before(clean, match.start())
        ),
        None,
    )
    if roman is not None:
        clean = clean[:roman.start()].rstrip()

    clean = _RELATED_PARAGRAPHS_RE.sub(" ", clean)

    # Subsection headings in this edition live after paragraph content. Once
    # navigation annotations are removed, a Roman heading at the absolute tail
    # is unambiguous even when the preceding OCR lost its final punctuation.
    roman_tail = next(
        (
            match
            for match in _ROMAN_SECTION_HEADING_RE.finditer(clean)
            if match.start() > 0 and len(clean) - match.start() <= 180
            and not clean[:match.start()].rstrip().casefold().endswith("século")
        ),
        None,
    )
    if roman_tail is not None:
        clean = clean[:roman_tail.start()].rstrip()

    # A page footer followed by a numbered section heading (e.g.
    # ``201 I. Como se chama este sacramento?``) starts editorial structure,
    # not the requested paragraph.
    boundary = _INLINE_PAGE_ROMAN_HEADING_RE.search(clean)
    if boundary is not None:
        clean = clean[:boundary.start()]

    # All-caps questions delimit a new section in the source (notably the
    # heading immediately after CCC 2558).  Everything after it belongs to the
    # following section, including any epigraph flattened before paragraph N+1.
    boundary = _first_tail_boundary(clean, _AUDITED_QUESTION_BOUNDARY_RE)
    if boundary is not None and clean[:boundary].rstrip().endswith((".", "!", "?", "…", "»", "”", '"')):
        clean = clean[:boundary]

    # A generic all-caps noun heading is ambiguous on its own.  It is removed
    # only when immediately coupled to the edition's trailing page number and
    # preceded by completed prose.  Thus ``... ouvintes. ACIMA ... 8`` is
    # structural, while ``ele proclama: DEUS É AMOR`` remains legitimate prose.
    boundary_match = _TRAILING_ALL_CAPS_WITH_PAGE_RE.search(clean)
    if boundary_match is not None:
        before = clean[:boundary_match.start()].rstrip()
        title = boundary_match.group("title").strip()
        title_words = re.findall(r"[A-ZÁÉÍÓÚÂÊÔÃÕÇÀÈÌÒÙÜ]{2,}", title)
        if before.endswith((".", "!", "?", "…", "»", "”", '"')) and len(title_words) >= 2:
            clean = before

    # Headings without a printed page number are also flattened after the
    # paragraph (for example ``... revelação. RESUMINDO``).  Restricting this
    # rule to the absolute tail after completed prose avoids treating emphasis
    # after a colon, quoted capitals or capitals inside a sentence as a heading.
    boundary_match = _TRAILING_ALL_CAPS_HEADING_RE.search(clean)
    if boundary_match is not None:
        clean = clean[:boundary_match.start()].rstrip()

    boundary = _bare_all_caps_boundary(clean)
    if boundary is not None:
        clean = clean[:boundary].rstrip()

    clean = _TRAILING_ROMAN_HEADING_RE.sub("", clean)
    clean = _remove_repeated_page_overlap(clean)
    clean = _TRAILING_PAGE_RE.sub("", clean)
    clean = _strip_audited_navigation_suffix(clean)
    return re.sub(r"\s+", " ", clean).strip()


def _marker_re(article: int) -> re.Pattern[str]:
    # The source contains valid forms such as ``112.1. Prestar...``.  For this
    # reason a digit immediately after the article dot cannot be prohibited.
    return re.compile(rf"(?<![\d,]){article}\s*\.")


def _adjacent_chunk_overlap_words(previous: str, current: str) -> int:
    """Return the exact rolling-window overlap of two consecutive chunks.

    The ingestion chunker advances 400 words through a 500-word window, so the
    next stored chunk normally repeats the previous chunk's final 100 words.
    Concatenating those database rows verbatim made dozens of CCC paragraphs
    visibly repeat whole blocks.  We only collapse an exact suffix/prefix match
    between consecutive sequence indexes and require a substantive 20-word
    overlap, which avoids treating a short repeated formula as ingestion data.
    """

    previous_words = re.sub(r"\s+", " ", previous or "").strip().split()
    current_words = re.sub(r"\s+", " ", current or "").strip().split()
    maximum = min(len(previous_words), len(current_words), 200)
    for size in range(maximum, 19, -1):
        if previous_words[-size:] == current_words[:size]:
            return size
    return 0


class CccCorpus:
    """An immutable, source-aware index over the ingested CCC chunks."""

    def __init__(self, chunks: Sequence[CccSourceChunk]) -> None:
        ordered = sorted(
            (chunk for chunk in chunks if (chunk.text or "").strip()),
            key=lambda chunk: (
                chunk.sequence_index is None,
                chunk.sequence_index if chunk.sequence_index is not None else 0,
                chunk.chunk_id,
            ),
        )
        self._chunks = tuple(ordered)
        parts: list[str] = []
        spans: list[_ChunkSpan] = []
        cursor = 0
        previous_chunk: CccSourceChunk | None = None
        for chunk in ordered:
            chunk_text = re.sub(r"\s+", " ", chunk.text or "").strip()
            overlap_words = 0
            if previous_chunk is not None:
                consecutive = (
                    previous_chunk.sequence_index is not None
                    and chunk.sequence_index is not None
                    and chunk.sequence_index == previous_chunk.sequence_index + 1
                )
                if consecutive:
                    overlap_words = _adjacent_chunk_overlap_words(
                        previous_chunk.text,
                        chunk_text,
                    )

            if overlap_words:
                chunk_text = " ".join(chunk_text.split()[overlap_words:])

            if not chunk_text:
                previous_chunk = chunk
                continue
            if parts:
                parts.append("\n")
                cursor += 1
            start = cursor
            parts.append(chunk_text)
            cursor += len(chunk_text)
            spans.append(_ChunkSpan(chunk, start, cursor))
            previous_chunk = chunk
        self._document = "".join(parts)
        self._spans = tuple(spans)
        self._body_start, self._body_end = self._find_body_bounds()
        self._markers = self._index_markers()
        self._canonical_starts = self._build_canonical_starts()

    def _find_body_bounds(self) -> tuple[int, int]:
        if not self._document:
            return 0, 0

        last_markers = list(_marker_re(CCC_MAX_ARTICLE).finditer(self._document))
        if not last_markers:
            return 0, len(self._document)
        final_marker = last_markers[-1]

        anchors = [
            match
            for match in _BODY_ANCHOR_RE.finditer(self._document)
            if match.start() < final_marker.start()
        ]
        start = 0
        if anchors:
            anchor = anchors[-1]
            first_article = _marker_re(1).search(
                self._document,
                anchor.start(),
                min(len(self._document), anchor.end() + 3000),
            )
            if first_article is not None:
                start = first_article.start()

        end = len(self._document)
        index_match = _INDEX_AFTER_BODY_RE.search(self._document, final_marker.end())
        if index_match is not None:
            end = index_match.start()
        return start, end

    def _index_markers(self) -> dict[int, tuple[tuple[int, int], ...]]:
        markers: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for match in _GENERIC_ARTICLE_MARKER_RE.finditer(
            self._document,
            self._body_start,
            self._body_end,
        ):
            number = int(match.group(1))
            if CCC_MIN_ARTICLE <= number <= CCC_MAX_ARTICLE:
                markers[number].append((match.start(), match.end()))
        return {number: tuple(values) for number, values in markers.items()}

    def _build_canonical_starts(self) -> dict[int, tuple[int, int]]:
        """Recover the complete 1..2865 marker chain when the full CCC exists.

        Overlapping OCR chunks duplicate some article markers.  Dynamic
        programming chooses a monotonic full chain and, on ties, the later
        duplicate because it normally contains the complete restarted page.
        Article extraction still ends at the *first* following marker, so the
        duplicate next page is never included in the preceding article.
        """

        if any(number not in self._markers for number in range(1, CCC_MAX_ARTICLE + 1)):
            return {}

        states: dict[int, list[_MarkerState]] = {
            CCC_MAX_ARTICLE: [
                _MarkerState(start, end, 1, None)
                for start, end in self._markers[CCC_MAX_ARTICLE]
            ]
        }
        for number in range(CCC_MAX_ARTICLE - 1, 0, -1):
            next_states = states[number + 1]
            current_states: list[_MarkerState] = []
            for start, end in self._markers[number]:
                choices = [
                    state
                    for state in next_states
                    if 3 < state.start - start <= 100_000
                ]
                if choices:
                    best = max(choices, key=lambda state: (state.chain_length, state.start))
                    current_states.append(
                        _MarkerState(start, end, best.chain_length + 1, best.start)
                    )
                else:
                    current_states.append(_MarkerState(start, end, 1, None))
            states[number] = current_states

        first_states = states[1]
        first = min(first_states, key=lambda state: abs(state.start - self._body_start))
        if first.chain_length != CCC_MAX_ARTICLE:
            return {}

        chosen: dict[int, tuple[int, int]] = {}
        current: _MarkerState | None = first
        for number in range(1, CCC_MAX_ARTICLE + 1):
            if current is None:
                return {}
            chosen[number] = (current.start, current.end)
            if current.next_start is None:
                current = None
            else:
                current = next(
                    (
                        state
                        for state in states.get(number + 1, ())
                        if state.start == current.next_start
                    ),
                    None,
                )
        return chosen

    def _fallback_start(self, article: int) -> tuple[int, int] | None:
        candidates = self._markers.get(article, ())
        if not candidates:
            return None
        next_candidates = self._markers.get(article + 1, ()) if article < CCC_MAX_ARTICLE else ()

        ranked: list[tuple[tuple[int, int, int], tuple[int, int]]] = []
        for index, (start, end) in enumerate(candidates):
            next_article = next((position for position, _ in next_candidates if position > start), None)
            later_same = candidates[index + 1][0] if index + 1 < len(candidates) else None
            repeated_before_next = (
                later_same is not None
                and (next_article is None or later_same < next_article)
            )
            stop = next_article if next_article is not None else self._body_end
            length = max(0, stop - end)
            score = (
                1 if next_article is not None or article == CCC_MAX_ARTICLE else 0,
                0 if repeated_before_next else 1,
                min(length, 20_000),
            )
            ranked.append((score, (start, end)))
        return max(ranked, key=lambda item: item[0])[1]

    def get_article(self, article: int) -> CccArticle | None:
        _validate_article_number(article)
        marker = self._canonical_starts.get(article) or self._fallback_start(article)
        if marker is None:
            return None
        start, text_start = marker

        if article < CCC_MAX_ARTICLE:
            # Use the first following marker, not the canonical later duplicate.
            next_start = next(
                (
                    position
                    for position, _ in self._markers.get(article + 1, ())
                    if position > start
                ),
                None,
            )
            if next_start is None:
                return None
            text_end = next_start
        else:
            text_end = self._body_end

        text = clean_ccc_article_text(self._document[text_start:text_end])
        if len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}", text)) < 4:
            return None

        intersecting = [
            span.chunk
            for span in self._spans
            if span.start < text_end and span.end > start
        ]
        if not intersecting:
            return None
        book_id = intersecting[0].book_id
        chunk_ids = tuple(dict.fromkeys(chunk.chunk_id for chunk in intersecting))
        pages = tuple(
            dict.fromkeys(
                chunk.pdf_page
                for chunk in intersecting
                if chunk.pdf_page is not None
            )
        )
        return CccArticle(
            number=article,
            text=text,
            source_book_id=book_id,
            source_chunk_ids=chunk_ids,
            source_pages=pages,
        )


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value).strip()


def _canonical_title(value: str) -> str:
    folded = _fold(value)
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


class SqlAlchemyCccArticleSource:
    """Lazy source backed by the exact full-Catechism ``CIC`` book."""

    _EXPECTED_TITLE = _canonical_title("Catecismo da Igreja Católica")

    def __init__(self, session_factory: Callable[[], Any] | None = None) -> None:
        if session_factory is None:
            from models.database import SessionLocal

            session_factory = SessionLocal
        self._session_factory = session_factory
        self._lock = threading.Lock()
        self._loaded = False
        self._corpus: CccArticleSource | None = None
        self.last_error: str | None = None

    def _load(self) -> None:
        from models.database import Book, BookFile, Chunk

        try:
            with self._session_factory() as db:
                books = db.query(Book).filter(Book.collection == "CIC").all()
                exact = [
                    book
                    for book in books
                    if self._EXPECTED_TITLE
                    in {
                        _canonical_title(book.title or ""),
                        _canonical_title(book.canonical_title or ""),
                    }
                ]
                if not exact:
                    self._corpus = None
                    self.last_error = "FULL_CCC_BOOK_NOT_FOUND"
                    return

                # If a re-ingestion created more than one exact book, use the
                # one with the most chunks instead of an arbitrary row.
                choices: list[tuple[int, Any, list[Any]]] = []
                for book in exact:
                    rows = (
                        db.query(Chunk)
                        .filter(Chunk.book_id == book.id)
                        .order_by(Chunk.sequence_index.nulls_last(), Chunk.id)
                        .all()
                    )
                    choices.append((len(rows), book, rows))
                _, book, rows = max(choices, key=lambda item: item[0])
                source_chunks = [
                    CccSourceChunk(
                        book_id=book.id,
                        chunk_id=row.id,
                        sequence_index=row.sequence_index,
                        text=row.text or "",
                        pdf_page=row.pdf_page,
                    )
                    for row in rows
                ]
                corpus: CccArticleSource | None = None
                book_file = (
                    db.query(BookFile)
                    .filter(BookFile.book_id == book.id)
                    .order_by(BookFile.id)
                    .first()
                )
                if book_file is not None and book_file.stored_path:
                    from storage.pdf_storage import get_pdf_storage

                    pdf_path = get_pdf_storage().resolve_for_processing(book_file.stored_path)
                    if pdf_path and os.path.isfile(pdf_path):
                        pdf_corpus = PdfCccCorpus(
                            pdf_path,
                            book_id=book.id,
                            chunk_ids=[row.id for row in rows],
                        )
                        if all(
                            pdf_corpus.get_article(number) is not None
                            for number in range(CCC_MIN_ARTICLE, CCC_MAX_ARTICLE + 1)
                        ):
                            corpus = pdf_corpus

                # Fail closed when the canonical PDF cannot yield all 2,865
                # paragraphs. The chunk corpus is retained only for injected
                # unit-test sources; production must not silently fall back to
                # overlapping search windows and call them exact source text.
                self._corpus = corpus
                self.last_error = None if self._corpus is not None else "FULL_CCC_PDF_UNAVAILABLE"
        except Exception as exc:  # Fail closed; callers receive SOURCE_UNAVAILABLE.
            self._corpus = None
            self.last_error = f"CCC_SOURCE_ERROR:{type(exc).__name__}"

    def get_article(self, article: int) -> CccArticle | None:
        _validate_article_number(article)
        if not self._loaded:
            with self._lock:
                if not self._loaded:
                    self._load()
                    self._loaded = True
        return self._corpus.get_article(article) if self._corpus is not None else None

    def refresh(self) -> None:
        """Clear the immutable corpus cache after an intentional CCC re-ingestion."""

        with self._lock:
            self._loaded = False
            self._corpus = None
            self.last_error = None


class SqlAlchemyPatristicChunkFilter:
    """Resolve an authoritative allow-list for candidate chunk IDs."""

    def __init__(self, session_factory: Callable[[], Any] | None = None) -> None:
        if session_factory is None:
            from models.database import SessionLocal

            session_factory = SessionLocal
        self._session_factory = session_factory

    def patristic_book_ids(self) -> list[int]:
        from sqlalchemy import or_

        from models.database import Book

        with self._session_factory() as db:
            rows = (
                db.query(Book.id)
                .filter(
                    or_(
                        Book.library_section == "patristica",
                        Book.patristic_tradition.isnot(None),
                        Book.collection.in_(STRICT_PATRISTIC_COLLECTIONS),
                    )
                )
                .all()
            )
        return sorted({int(row.id) for row in rows})

    def allowed_chunk_ids(self, chunk_ids: Sequence[int]) -> set[int]:
        from sqlalchemy import or_

        from models.database import Book, Chunk

        unique_ids = sorted({int(chunk_id) for chunk_id in chunk_ids if int(chunk_id) > 0})
        if not unique_ids:
            return set()
        with self._session_factory() as db:
            rows = (
                db.query(Chunk.id)
                .join(Book, Chunk.book_id == Book.id)
                .filter(
                    Chunk.id.in_(unique_ids),
                    or_(
                        Book.library_section == "patristica",
                        Book.patristic_tradition.isnot(None),
                        Book.collection.in_(STRICT_PATRISTIC_COLLECTIONS),
                    ),
                )
                .all()
            )
        return {int(row.id) for row in rows}


_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}", re.UNICODE)
_QUOTED_RE = re.compile(r"[\"“«](.*?)[\"”»]", re.DOTALL)
_SCRIPTURE_RE = re.compile(
    r"\b(?:[1-3]\s*)?(?:Gn|Ex|Lv|Nm|Dt|Js|Jz|Rt|Sm|Rs|Cr|Esd|Ne|Tb|Jt|Est|Mc|"
    r"Sl|Pr|Ecl|Ct|Sb|Eclo|Is|Jr|Lm|Br|Ez|Dn|Os|Jl|Am|Ab|Jn|Mq|Na|Hab|Sf|Ag|"
    r"Zc|Ml|Mt|Mc|Lc|Jo|At|Rm|Cor|Gl|Ef|Fl|Cl|Ts|Tm|Tt|Fm|Hb|Tg|Pd|Jo|Jd|Ap)"
    r"\s*\d{1,3}\s*[,.:]\s*\d{1,3}(?:\s*[-–—]\s*\d{1,3})?",
    re.IGNORECASE,
)

_STOPWORDS = {
    "a", "ao", "aos", "aquela", "aquele", "aqueles", "as", "assim", "com", "como",
    "da", "das", "de", "dela", "dele", "deles", "do", "dos", "e", "ela", "ele",
    "eles", "em", "entre", "era", "essa", "esse", "esta", "este", "estes", "foi",
    "há", "isso", "isto", "lhe", "lhes", "mais", "mas", "mesmo", "na", "nas", "não",
    "no", "nos", "nossa", "nosso", "num", "numa", "o", "os", "ou", "para", "pela",
    "pelas", "pelo", "pelos", "pois", "por", "porque", "qual", "que", "se", "sem",
    "ser", "seu", "seus", "sua", "suas", "também", "tem", "toda", "todo", "todos",
    "uma", "umas", "um", "uns", "parágrafo", "parágrafos", "relacionado", "relacionados",
    "primeira", "primeiro", "segunda", "segundo", "terceira", "terceiro", "parte",
}


def _extract_quoted_phrases(text: str) -> tuple[str, ...]:
    phrases: list[str] = []
    for match in _QUOTED_RE.finditer(text):
        phrase = re.sub(r"\s+", " ", match.group(1)).strip(" .,:;—–-")
        words = _WORD_RE.findall(phrase)
        if 2 <= len(words) <= 30 and len(phrase) >= 7:
            phrases.append(phrase)
    return tuple(dict.fromkeys(phrases))


def _extract_patristic_mentions(text: str) -> tuple[str, ...]:
    try:
        from utils.author_detection import PATRISTIC_AUTHORS
    except Exception:
        return ()
    found: list[str] = []
    for author, data in PATRISTIC_AUTHORS.items():
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in data.get("patterns", ())):
            found.append(author)
    return tuple(found)


def derive_query_from_exact_article(
    text: str,
    *,
    max_terms: int = 22,
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return query, terms, quotations, Scripture refs and Father mentions."""

    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return "", (), (), (), ()

    token_rows: list[tuple[str, str, int]] = []
    for index, match in enumerate(_WORD_RE.finditer(clean)):
        original = match.group(0)
        folded = _fold(original)
        if len(folded) < 3 or folded in {_fold(word) for word in _STOPWORDS}:
            continue
        token_rows.append((folded, original.casefold(), index))

    counts = Counter(row[0] for row in token_rows)
    first_position: dict[str, int] = {}
    display: dict[str, str] = {}
    for folded, original, index in token_rows:
        first_position.setdefault(folded, index)
        display.setdefault(folded, original)

    ranked = sorted(
        counts,
        key=lambda token: (
            -(counts[token] * 4 + max(0, 20 - first_position[token]) / 20),
            first_position[token],
            token,
        ),
    )[:max_terms]
    ranked.sort(key=lambda token: first_position[token])
    key_terms = tuple(display[token] for token in ranked)
    quoted = _extract_quoted_phrases(clean)
    scripture = tuple(dict.fromkeys(match.group(0) for match in _SCRIPTURE_RE.finditer(clean)))
    mentions = _extract_patristic_mentions(clean)

    # Exact short quotations are valuable vocabulary, but the final query is
    # bounded so an OCR-heavy article cannot create a giant ES request.
    phrase_words: list[str] = []
    for phrase in quoted[:2]:
        phrase_words.extend(_WORD_RE.findall(phrase)[:10])
    query_parts: list[str] = []
    seen: set[str] = set()
    for value in (*key_terms, *phrase_words, *mentions):
        key = _fold(value)
        if not key or key in seen:
            continue
        seen.add(key)
        query_parts.append(value)
    query = " ".join(query_parts)[:900].strip()
    return query, key_terms, quoted, scripture, mentions


def _validate_article_number(article: int) -> None:
    if isinstance(article, bool) or not isinstance(article, int):
        raise ValueError("article must be an integer between 1 and 2865")
    if not CCC_MIN_ARTICLE <= article <= CCC_MAX_ARTICLE:
        raise ValueError("article must be between 1 and 2865")


class CccCommentaryService:
    def __init__(
        self,
        article_source: CccArticleSource,
        search_client: AcervoSearchClient,
        patristic_filter: PatristicChunkFilter,
        patristic_book_ids_provider: Callable[[], Sequence[int]] | None = None,
    ) -> None:
        self._article_source = article_source
        self._search_client = search_client
        self._patristic_filter = patristic_filter
        self._patristic_book_ids_provider = patristic_book_ids_provider

    def build_context(self, article: int) -> CccArticleQuery:
        _validate_article_number(article)
        section = find_ccc_section(article)
        if section is None:  # Defensive; ccc_structure currently covers all valid articles.
            raise ValueError(f"article {article} is not mapped in the CCC structure")

        exact = self._article_source.get_article(article)
        if exact is None:
            return CccArticleQuery(
                article=article,
                section_title=section["title"],
                section_start=section["start"],
                section_end=section["end"],
                mode=CccQueryMode.SOURCE_UNAVAILABLE,
                query="",
                article_text=None,
                article_fingerprint=None,
                key_terms=(),
                quoted_phrases=(),
                scripture_references=(),
                patristic_mentions=(),
                source_book_id=None,
                source_chunk_ids=(),
                source_pages=(),
                warning=(
                    "Texto exato do artigo indisponível; a busca aproximada por seção "
                    "foi bloqueada para não atribuir ao artigo resultados genéricos."
                ),
            )

        query, terms, quotations, scripture, mentions = derive_query_from_exact_article(exact.text)
        if not query:
            return CccArticleQuery(
                article=article,
                section_title=section["title"],
                section_start=section["start"],
                section_end=section["end"],
                mode=CccQueryMode.SOURCE_UNAVAILABLE,
                query="",
                article_text=exact.text,
                article_fingerprint=exact.fingerprint,
                key_terms=(),
                quoted_phrases=quotations,
                scripture_references=scripture,
                patristic_mentions=mentions,
                source_book_id=exact.source_book_id,
                source_chunk_ids=exact.source_chunk_ids,
                source_pages=exact.source_pages,
                warning="O artigo foi localizado, mas não produziu uma consulta textual segura.",
            )

        return CccArticleQuery(
            article=article,
            section_title=section["title"],
            section_start=section["start"],
            section_end=section["end"],
            mode=CccQueryMode.EXACT_ARTICLE,
            query=query,
            article_text=exact.text,
            article_fingerprint=exact.fingerprint,
            key_terms=terms,
            quoted_phrases=quotations,
            scripture_references=scripture,
            patristic_mentions=mentions,
            source_book_id=exact.source_book_id,
            source_chunk_ids=exact.source_chunk_ids,
            source_pages=exact.source_pages,
        )

    def search(self, article: int, *, limit: int = 12) -> CccCommentarySearchResult:
        if not 1 <= limit <= 30:
            raise ValueError("limit must be between 1 and 30")
        context = self.build_context(article)
        if not context.is_exact:
            return CccCommentarySearchResult(context, (), 0, (), context.warning)

        candidate_limit = min(120, max(30, limit * 5))
        try:
            provider = self._patristic_book_ids_provider
            if provider is not None:
                patristic_book_ids = sorted(
                    {int(book_id) for book_id in provider() if int(book_id) > 0}
                )
            else:
                patristic_book_ids = self._patristic_filter.patristic_book_ids()
        except Exception as exc:
            return CccCommentarySearchResult(
                context=context,
                hits=(),
                candidate_count=0,
                rejected_chunk_ids=(),
                warning=(
                    "A lista autoritativa de obras patrísticas falhou; a busca "
                    f"foi bloqueada ({type(exc).__name__})."
                ),
            )
        if not patristic_book_ids:
            return CccCommentarySearchResult(
                context=context,
                hits=(),
                candidate_count=0,
                rejected_chunk_ids=(),
                warning="Nenhuma obra patrística autorizada está disponível para a busca.",
            )

        search_kwargs = {
            "query": context.query,
            "limit": candidate_limit,
            "query_language": "pt",
            "collection_filter": "patristica",
            "patristic_book_ids": patristic_book_ids,
        }
        hybrid = getattr(self._search_client, "search_acervo_hybrid", None)
        if callable(hybrid):
            candidates = hybrid(**search_kwargs)
        else:
            candidates = self._search_client.search_acervo(**search_kwargs)
        candidate_ids = tuple(
            dict.fromkeys(
                int(hit.chunk_id)
                for hit in candidates
                if getattr(hit, "chunk_id", None) is not None
            )
        )
        try:
            allowed = self._patristic_filter.allowed_chunk_ids(candidate_ids)
        except Exception as exc:
            return CccCommentarySearchResult(
                context=context,
                hits=(),
                candidate_count=len(candidates),
                rejected_chunk_ids=candidate_ids,
                warning=(
                    "O filtro patrístico autoritativo falhou; todos os candidatos "
                    f"foram bloqueados ({type(exc).__name__})."
                ),
            )

        accepted: list[Any] = []
        rejected: list[int] = []
        seen: set[int] = set()
        for hit in candidates:
            raw_id = getattr(hit, "chunk_id", None)
            if raw_id is None:
                continue
            chunk_id = int(raw_id)
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            if chunk_id not in allowed:
                rejected.append(chunk_id)
                continue
            accepted.append(hit)
            if len(accepted) >= limit:
                break

        return CccCommentarySearchResult(
            context=context,
            hits=tuple(accepted),
            candidate_count=len(candidates),
            rejected_chunk_ids=tuple(rejected),
        )


def build_default_ccc_commentary_service() -> CccCommentaryService:
    """Build the production service without module-import side effects."""

    from search.text_search import TextSearchClient

    return CccCommentaryService(
        article_source=SqlAlchemyCccArticleSource(),
        search_client=TextSearchClient(),
        patristic_filter=SqlAlchemyPatristicChunkFilter(),
    )


__all__ = [
    "CCC_MAX_ARTICLE",
    "CCC_MIN_ARTICLE",
    "CccArticle",
    "CccArticleQuery",
    "CccCommentarySearchResult",
    "CccCommentaryService",
    "CccCorpus",
    "CccQueryMode",
    "CccSourceChunk",
    "SqlAlchemyCccArticleSource",
    "SqlAlchemyPatristicChunkFilter",
    "build_default_ccc_commentary_service",
    "derive_query_from_exact_article",
    "clean_ccc_article_text",
]
