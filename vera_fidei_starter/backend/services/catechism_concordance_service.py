"""Verified concordance between the CCC and other indexed catechisms.

The CCC paragraph number is never reused as if it were a locator in another
catechism.  The Compendium is linked only through the CCC references printed
beside each of its own questions.  Older catechisms keep their own question
numbers and are returned only when a conservative thematic score succeeds.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import unicodedata
from bisect import bisect_right
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from typing import Any, Callable, Protocol, Sequence

from search.content_quality import clean_ocr_text
from services.ccc_commentary_service import CccArticleQuery


CatechismId = str


@dataclass(frozen=True)
class CatechismSourceRef:
    book_id: int
    book_file_id: int | None
    chunk_ids: tuple[int, ...]
    pages: tuple[int, ...]
    edition_label: str | None
    language: str | None


@dataclass(frozen=True)
class CatechismPassage:
    catechism: CatechismId
    source_title: str
    source_author: str | None
    locator: str
    section_title: str | None
    text: str
    source: CatechismSourceRef

    @property
    def text_fingerprint(self) -> str:
        clean = re.sub(r"\s+", " ", self.text).strip()
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CatechismMatch:
    kind: str
    confidence: str
    evidence_terms: tuple[str, ...]


@dataclass(frozen=True)
class CatechismComparison:
    status: str
    source: CatechismId
    source_title: str
    message: str | None = None
    passage: CatechismPassage | None = None
    match: CatechismMatch | None = None


@dataclass(frozen=True)
class CatechismUnit:
    catechism: CatechismId
    question_number: int
    question: str
    answer: str
    ccc_ranges: tuple[tuple[int, int], ...]
    source_title: str
    source_author: str | None
    source: CatechismSourceRef

    @property
    def searchable_text(self) -> str:
        return f"{self.question} {self.answer}".strip()

    def to_passage(self) -> CatechismPassage:
        question, answer = _verified_unit_text(self)
        return CatechismPassage(
            catechism=self.catechism,
            source_title=self.source_title,
            source_author=self.source_author,
            locator=f"Pergunta {self.question_number}",
            section_title=question,
            text=answer,
            source=self.source,
        )


class CatechismUnitSource(Protocol):
    def get_units(self, catechism: CatechismId) -> tuple[CatechismUnit, ...] | None: ...

    def source_error(self, catechism: CatechismId) -> str | None: ...


_SOURCE_TITLES: dict[str, str] = {
    "compendium": "Compêndio do Catecismo da Igreja Católica",
    "pio_x": "Catecismo de São Pio X",
    "roman": "Catecismo Romano de São Pio V",
}

# Transcriptions checked visually against the indexed PDF pages.  The OCR text
# contains spacing artifacts (for example ``Cria for``); keeping the correction
# scoped to the five reviewed crosswalk entries prevents silent editorial
# guesses elsewhere in the corpus.
_VERIFIED_PIO_X_TRANSCRIPTIONS: dict[int, tuple[str, str]] = {
    68: (
        "Que nos ensina o segundo artigo do Credo: e em Jesus Cristo, um só seu Filho, Nosso Senhor?",
        "O segundo artigo do Credo ensina-nos que o Filho de Deus é a segunda Pessoa da "
        "Santíssima Trindade; que Ele é Deus eterno, todo-poderoso, Criador e Senhor, como o "
        "Padre; que se fez homem para nos salvar; e que o Filho de Deus feito homem se chama Jesus Cristo.",
    ),
    130: (
        "Que nos ensina o oitavo artigo do Credo: creio no Espírito Santo?",
        "O oitavo artigo do Credo ensina-nos que existe o Espírito Santo, terceira Pessoa da "
        "Santíssima Trindade, e que Ele é Deus eterno, infinito, onipotente, Criador e Senhor "
        "de todas as coisas, como o Padre e o Filho.",
    ),
    253: (
        "Que é a oração?",
        "A oração é uma elevação da alma a Deus, para adorá-Lo, para Lhe dar graças e "
        "para Lhe pedir aquilo de que precisamos.",
    ),
    594: (
        "Que é o Sacramento da Eucaristia?",
        "A Eucaristia é um Sacramento que, pela admirável conversão de toda a substância do "
        "pão no Corpo de Jesus Cristo, e de toda a substância do vinho no seu precioso Sangue, "
        "contém verdadeira, real e substancialmente o Corpo, Sangue, Alma e Divindade do mesmo "
        "Jesus Cristo Nosso Senhor, debaixo das espécies de pão e de vinho, para ser nosso alimento espiritual.",
    ),
    670: (
        "Que é o Sacramento da Penitência?",
        "A Penitência, chamada também Confissão, é o Sacramento instituído por Jesus Cristo "
        "para perdoar os pecados cometidos depois do Batismo.",
    ),
}


def _verified_unit_text(unit: CatechismUnit) -> tuple[str, str]:
    if unit.catechism == "pio_x":
        verified = _VERIFIED_PIO_X_TRANSCRIPTIONS.get(unit.question_number)
        if verified is not None:
            return verified
    return unit.question, unit.answer
_EXPECTED_TITLES: dict[str, tuple[str, ...]] = {
    "compendium": ("compendio do catecismo da igreja catolica",),
    "pio_x": ("catecismo sao pio x", "catecismo de sao pio x"),
}

_QUESTION_START = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ«\"]"
_COMPENDIUM_NEXT_MARKER = rf"(?<!\d)\d{{1,3}}\.\s+{_QUESTION_START}"
_PIO_X_NEXT_MARKER = rf"(?<!\d)\d{{1,3}}\)\s+{_QUESTION_START}"
_SCRIPTURE_CITATION_AFTER_QUESTION = (
    r"(?:\s+\((?:[1-3]\s*)?[A-Za-zÀ-ÿ]{1,8}\s+\d{1,3}"
    r"(?:,\s*\d{1,3}(?:\s*[-–—]\s*\d{1,3})?)?\))?"
)
_QUESTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "compendium": re.compile(
        rf"(?<!\d)(\d{{1,3}})\.\s+"
        rf"({_QUESTION_START}(?:(?!{_COMPENDIUM_NEXT_MARKER})[^?]){{2,279}}\?[»”\"]?)"
        rf"{_SCRIPTURE_CITATION_AFTER_QUESTION}(?=\s|$)"
    ),
    "pio_x": re.compile(
        rf"(?<!\d)(\d{{1,3}})\)\s+"
        rf"({_QUESTION_START}(?:(?!{_PIO_X_NEXT_MARKER})[^?]){{2,279}}\?[»”\"]?)"
        r"(?=\s|$)"
    ),
}
_ANY_PIO_MARKER_RE = re.compile(r"(?<!\d)\d{1,3}\)\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ«\"]")
_COMPENDIUM_REFERENCES_RE = re.compile(
    r"^\s*((?:\d{1,4}(?:\s*[–—-]\s*\d{1,4})?\s*(?:[;,.]\s*)?){1,14})(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ«\"(])"
)
_PAGE_NOISE_RE = re.compile(
    r"(?:\d{2}/\d{2}/\d{2,4},?\s+\d{2}:\d{2}\s+)?about:blank(?:\s+\d+/\d+)?",
    re.IGNORECASE,
)
_DATE_TIME_RE = re.compile(r"\b\d{2}/\d{2}/\d{2,4},?\s+\d{2}:\d{2}\b")
_PIO_PAGE_HEADER_RE = re.compile(r"Catecismo\s+de\s+S[aã]o\s+Pio\s+X\s+\d+", re.IGNORECASE)
_BOUNDARY_RE = re.compile(
    r"\s+(?:\d{1,3}\s+)?(?:CAP[IÍ]TULO\s+(?:[IVXLCDM]+|PRIMEIR[OA]|SEGUND[OA]|TERCEIR[OA]|QUART[OA])|"
    r"ARTIGO\s+\d+|PAR[AÁ]GRAFO\s+\d+|"
    r"(?:PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA)\s+PARTE|"
    r"(?:PRIMEIRA|SEGUNDA)\s+SEC[CÇ][AÃ]O|AP[EÊ]NDICE|"
    r"(?:§\s*)?\d+[oº°]\s*-\s+D[aoe])\b",
    re.IGNORECASE,
)
_ALL_CAPS_BOUNDARY_RE = re.compile(
    r"\s+(?:\d{1,3}\s+)?"
    r"(?:[A-ZÀ-Þ][A-ZÀ-Þ0-9«»‘’'\-:]*)(?:\s+"
    r"[A-ZÀ-Þ][A-ZÀ-Þ0-9«»‘’'\-:]*){1,16}"
    r"(?=\s|$)"
)


def _fold(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").casefold())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", normalized).strip()


def _canonical_title(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _fold(value)).strip()


def _clean_unit_text(value: str) -> str:
    clean = clean_ocr_text(value)
    clean = _PAGE_NOISE_RE.sub(" ", clean)
    clean = _DATE_TIME_RE.sub(" ", clean)
    clean = _PIO_PAGE_HEADER_RE.sub(" ", clean)
    return re.sub(r"\s+", " ", clean).strip(" -–—")


def _structural_boundary(value: str) -> int | None:
    """Return the first structural heading after an answer.

    Named headings are matched case-insensitively. Generic ALL-CAPS headings
    use a separate case-sensitive expression; combining both in one
    IGNORECASE regex made ordinary prose look like a heading.
    """

    matches = [
        match
        for pattern in (_BOUNDARY_RE, _ALL_CAPS_BOUNDARY_RE)
        if (match := pattern.search(value)) is not None
    ]
    return min((match.start() for match in matches), default=None)


def _parse_ccc_ranges(value: str) -> tuple[tuple[int, int], ...]:
    ranges: list[tuple[int, int]] = []
    for match in re.finditer(r"(\d{1,4})(?:\s*[–—-]\s*(\d{1,4}))?", value):
        start = int(match.group(1))
        end = int(match.group(2) or start)
        # OCR such as ``1928-133`` is not a valid descending CCC range.
        if not 1 <= start <= 2865 or not 1 <= end <= 2865 or end < start:
            continue
        ranges.append((start, end))
    return tuple(dict.fromkeys(ranges))


def _unit_quality(unit: CatechismUnit) -> tuple[int, int, int]:
    question_words = len(re.findall(r"[A-Za-zÀ-ÿ]{2,}", unit.question))
    answer_words = len(re.findall(r"[A-Za-zÀ-ÿ]{2,}", unit.answer))
    complete = int(bool(re.search(r"[.!?…][\"”’»)]?\s*$", unit.answer)))
    return complete, min(answer_words, 260), min(question_words, 40)


def parse_catechism_units(
    catechism: CatechismId,
    rows: Sequence[Any],
    *,
    source_title: str,
    source_author: str | None,
    edition_label: str | None,
    language: str | None,
    book_file_id: int | None,
) -> tuple[CatechismUnit, ...]:
    """Parse numbered Q/A units independently in overlapping source chunks."""

    pattern = _QUESTION_PATTERNS[catechism]
    by_number: dict[int, CatechismUnit] = {}
    for row in rows:
        text = _clean_unit_text(getattr(row, "text", "") or "")
        markers = list(pattern.finditer(text))
        for index, marker in enumerate(markers):
            number = int(marker.group(1))
            if number <= 0:
                continue
            question = _clean_unit_text(marker.group(2))
            if catechism == "compendium":
                # OCR chunks can flatten prefaces and part headings directly
                # before a real numbered question. Only the text after the
                # last structural heading belongs to the question.
                heading_tail = re.search(
                    r"(?:PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA)\s+(?:PARTE|SEC[CÇ][AÃ]O).*?(?=\d{1,3}\.\s)",
                    question,
                    re.IGNORECASE,
                )
                if heading_tail is not None:
                    nested = re.search(r"(\d{1,3})\.\s+(.+\?)$", question[heading_tail.start():])
                    if nested is not None and int(nested.group(1)) == number:
                        question = _clean_unit_text(nested.group(2))
            end = markers[index + 1].start() if index + 1 < len(markers) else min(len(text), marker.end() + 1900)
            if catechism == "pio_x":
                raw_next = _ANY_PIO_MARKER_RE.search(text, marker.end())
                if raw_next is not None:
                    end = min(end, raw_next.start())
            payload = text[marker.end():end].strip()
            references: tuple[tuple[int, int], ...] = ()
            if catechism == "compendium":
                reference_match = _COMPENDIUM_REFERENCES_RE.match(payload)
                if reference_match is None:
                    continue
                references = _parse_ccc_ranges(reference_match.group(1))
                if not references:
                    continue
                payload = payload[reference_match.end():].strip()

            boundary = _structural_boundary(payload)
            if boundary is not None:
                payload = payload[:boundary]
            answer = _clean_unit_text(payload)
            answer = re.sub(r"\s+\d{1,3}\s*$", "", answer).strip()
            lowercase_restart = re.search(r"[.!?]\s+(?=[a-zà-ÿ])", answer)
            if lowercase_restart is not None and lowercase_restart.start() >= 30:
                answer = answer[:lowercase_restart.start() + 1].strip()
            if not (4 <= len(question.split()) <= 55 and 5 <= len(answer.split()) <= 320):
                continue
            # A flattened chunk that ends mid-sentence is not an exact answer.
            # Drop it; overlapping source chunks normally provide the complete
            # duplicate, and otherwise the concordance must fail closed.
            if not re.search(r"[.!?…][\"”’»)]?\s*$", answer):
                continue

            source = CatechismSourceRef(
                book_id=int(getattr(row, "book_id")),
                book_file_id=(
                    int(getattr(row, "book_file_id"))
                    if getattr(row, "book_file_id", None) is not None
                    else book_file_id
                ),
                chunk_ids=(int(getattr(row, "id")),),
                pages=(int(getattr(row, "pdf_page")),) if getattr(row, "pdf_page", None) is not None else (),
                edition_label=edition_label,
                language=language,
            )
            unit = CatechismUnit(
                catechism=catechism,
                question_number=number,
                question=question,
                answer=answer,
                ccc_ranges=references,
                source_title=source_title,
                source_author=source_author,
                source=source,
            )
            previous = by_number.get(number)
            if previous is None or _unit_quality(unit) > _unit_quality(previous):
                by_number[number] = unit
    return tuple(by_number[number] for number in sorted(by_number))


def _units_with_exact_pdf_pages(
    catechism: CatechismId,
    units: Sequence[CatechismUnit],
    pdf_path: str,
) -> tuple[CatechismUnit, ...]:
    """Replace rolling-chunk pages with the physical page of each question.

    A 500-word chunk can begin on page N while its numbered question begins on
    N+1.  Linking the chunk's ``pdf_page`` therefore opens the wrong page for a
    large part of both catechisms.  The question marker itself is unambiguous in
    the source PDF; locate it there and fail closed for any unit that cannot be
    matched confidently.
    """

    try:
        import pymupdf
    except ImportError:  # pragma: no cover - production dependency is pinned.
        import fitz as pymupdf  # type: ignore

    page_texts: list[str] = []
    with pymupdf.open(pdf_path) as document:
        page_texts = [_clean_unit_text(page.get_text("text")) for page in document]
    if not page_texts:
        return ()

    # Search one continuous text stream instead of each page independently.
    # A question (or only its answer) may cross a physical page boundary.  The
    # offsets below retain the physical-page mapping while allowing the marker
    # regex to see that continuation.
    page_starts: list[int] = []
    page_ends: list[int] = []
    corpus_parts: list[str] = []
    cursor = 0
    for page_text in page_texts:
        if corpus_parts:
            corpus_parts.append(" ")
            cursor += 1
        page_starts.append(cursor)
        corpus_parts.append(page_text)
        cursor += len(page_text)
        page_ends.append(cursor)
    corpus = "".join(corpus_parts)

    def page_index_for_offset(offset: int) -> int:
        return max(0, min(len(page_starts) - 1, bisect_right(page_starts, offset) - 1))

    # start offset, end offset, first page index, last question page index,
    # extracted question.  Keeping all markers in document order lets us find
    # the exact answer interval: after this question and before the next one.
    markers: list[tuple[int, int, int, int, int, str]] = []
    for marker in _QUESTION_PATTERNS[catechism].finditer(corpus):
        start_offset = marker.start()
        end_offset = marker.end()
        first_page = page_index_for_offset(start_offset)
        last_question_page = page_index_for_offset(max(start_offset, end_offset - 1))
        markers.append(
            (
                int(marker.group(1)),
                start_offset,
                end_offset,
                first_page,
                last_question_page,
                _clean_unit_text(marker.group(2)),
            )
        )

    candidates: dict[int, list[tuple[int, int, int, int, str]]] = {}
    for marker_index, marker in enumerate(markers):
        number, start_offset, end_offset, first_page, last_question_page, question = marker
        next_marker_offset = (
            markers[marker_index + 1][1]
            if marker_index + 1 < len(markers)
            else len(corpus)
        )
        # The final numbered question has no following marker, and some Pio X
        # chapters put several pages of Scripture between two questions.  A
        # structural heading is an authoritative end of the current answer;
        # without this cap the appendix/readings can be mistaken for it.
        boundary = _structural_boundary(corpus[end_offset:next_marker_offset])
        if boundary is not None:
            next_marker_offset = min(next_marker_offset, end_offset + boundary)
        candidates.setdefault(number, []).append(
            (first_page, last_question_page, end_offset, next_marker_offset, question)
        )

    def aligned_answer_pages(
        expected_answer: str,
        answer_start: int,
        answer_end: int,
    ) -> set[int]:
        """Map the parsed answer itself back to physical zero-based pages.

        Set overlap is insufficient here: a long Scripture reading can share
        ordinary words with a short answer and falsely extend its page span.
        Ordered token alignment identifies where the known answer actually
        occurs.  Weak isolated matches are deliberately ignored.
        """

        expected_tokens = _canonical_title(expected_answer).split()
        if not expected_tokens or answer_end <= answer_start:
            return set()

        candidate_tokens: list[str] = []
        candidate_pages: list[int] = []
        first_answer_page = page_index_for_offset(answer_start)
        last_answer_page = page_index_for_offset(max(answer_start, answer_end - 1))
        for page_index in range(first_answer_page, last_answer_page + 1):
            fragment_start = max(answer_start, page_starts[page_index])
            fragment_end = min(answer_end, page_ends[page_index])
            if fragment_end <= fragment_start:
                continue
            fragment_tokens = _canonical_title(
                corpus[fragment_start:fragment_end]
            ).split()
            candidate_tokens.extend(fragment_tokens)
            candidate_pages.extend([page_index] * len(fragment_tokens))
        if not candidate_tokens:
            return set()

        # The rolling chunks and this PDF extraction pass through the same
        # canonical cleanup, so the answer must be present as one contiguous
        # token sequence.  If it is not, fail closed and keep only the pages
        # independently proven by the question marker.  This avoids turning
        # generic word similarities in readings or indexes into citations.
        width = len(expected_tokens)
        for start in range(0, len(candidate_tokens) - width + 1):
            if candidate_tokens[start:start + width] == expected_tokens:
                return set(candidate_pages[start:start + width])
        return set()

    resolved: list[CatechismUnit] = []
    for unit in units:
        matches = candidates.get(unit.question_number, ())
        if not matches:
            continue
        expected_question = _canonical_title(unit.question)
        old_page = unit.source.pages[0] if unit.source.pages else None

        def candidate_score(candidate: tuple[int, int, int, int, str]) -> tuple[float, int]:
            first_page, _, _, _, question = candidate
            similarity = SequenceMatcher(
                None,
                expected_question,
                _canonical_title(question),
                autojunk=False,
            ).ratio()
            page_number = first_page + 1
            proximity = -abs(page_number - old_page) if old_page is not None else 0
            return similarity, proximity

        (
            first_page,
            last_question_page,
            answer_start,
            answer_end,
            candidate_question,
        ) = max(matches, key=candidate_score)
        similarity = SequenceMatcher(
            None,
            expected_question,
            _canonical_title(candidate_question),
            autojunk=False,
        ).ratio()
        if similarity < 0.72:
            continue

        physical_pages = list(range(first_page + 1, last_question_page + 2))
        answer_pages = aligned_answer_pages(unit.answer, answer_start, answer_end)
        for page_index in sorted(answer_pages):
            if page_index > last_question_page:
                physical_pages.append(page_index + 1)
        resolved.append(
            replace(
                unit,
                source=replace(unit.source, pages=tuple(dict.fromkeys(physical_pages))),
            )
        )
    return tuple(resolved)


class SqlAlchemyCatechismUnitSource:
    """Lazy immutable Q/A corpora backed by the indexed catechism books."""

    def __init__(self, session_factory: Callable[[], Any] | None = None) -> None:
        if session_factory is None:
            from models.database import SessionLocal

            session_factory = SessionLocal
        self._session_factory = session_factory
        self._lock = threading.Lock()
        self._units: dict[str, tuple[CatechismUnit, ...] | None] = {}
        self._errors: dict[str, str | None] = {}

    def _load(self, catechism: str) -> None:
        from models.database import Book, BookFile, Chunk

        expected = set(_EXPECTED_TITLES.get(catechism, ()))
        try:
            with self._session_factory() as db:
                books = db.query(Book).all()
                candidates = [
                    book
                    for book in books
                    if expected.intersection(
                        {
                            _canonical_title(book.title),
                            _canonical_title(book.canonical_title),
                        }
                    )
                ]
                if not candidates:
                    self._units[catechism] = None
                    self._errors[catechism] = "SOURCE_NOT_FOUND"
                    return

                choices: list[tuple[int, Any, list[Any]]] = []
                for book in candidates:
                    rows = (
                        db.query(Chunk)
                        .filter(Chunk.book_id == book.id)
                        .order_by(Chunk.sequence_index.nulls_last(), Chunk.id)
                        .all()
                    )
                    choices.append((len(rows), book, rows))
                _, book, rows = max(choices, key=lambda item: item[0])
                file_row = (
                    db.query(BookFile)
                    .filter(BookFile.book_id == book.id)
                    .order_by(BookFile.id)
                    .first()
                )
                pdf_path: str | None = None
                if file_row is not None and file_row.stored_path:
                    from storage.pdf_storage import get_pdf_storage

                    candidate_path = get_pdf_storage().resolve_for_processing(file_row.stored_path)
                    if candidate_path and os.path.isfile(candidate_path):
                        pdf_path = candidate_path
                units = parse_catechism_units(
                    catechism,
                    rows,
                    source_title=book.title,
                    source_author=book.canonical_author or book.author or None,
                    edition_label=book.edition_label or None,
                    language=book.language or None,
                    book_file_id=file_row.id if file_row is not None else None,
                )
                if pdf_path is None:
                    self._units[catechism] = None
                    self._errors[catechism] = "SOURCE_PDF_UNAVAILABLE"
                    return
                units = _units_with_exact_pdf_pages(catechism, units, pdf_path)
                minimum = 400 if catechism == "compendium" else 700
                if len(units) < minimum:
                    self._units[catechism] = None
                    self._errors[catechism] = f"INCOMPLETE_CORPUS:{len(units)}"
                    return
                self._units[catechism] = units
                self._errors[catechism] = None
        except Exception as exc:
            self._units[catechism] = None
            self._errors[catechism] = f"SOURCE_ERROR:{type(exc).__name__}"

    def get_units(self, catechism: str) -> tuple[CatechismUnit, ...] | None:
        if catechism not in self._units:
            with self._lock:
                if catechism not in self._units:
                    self._load(catechism)
        return self._units.get(catechism)

    def source_error(self, catechism: str) -> str | None:
        if catechism not in self._units:
            self.get_units(catechism)
        return self._errors.get(catechism)

    def refresh(self) -> None:
        with self._lock:
            self._units.clear()
            self._errors.clear()


_TOKEN_RE = re.compile(r"[a-z]{3,}")
_STOPWORDS = {
    "aos", "aquelas", "aqueles", "assim", "cada", "com", "como", "das", "dela",
    "dele", "deles", "dos", "ela", "ele", "eles", "era", "essa", "esse", "esta",
    "este", "estes", "isso", "isto", "mais", "mas", "mesmo", "nao", "nos", "nossa",
    "nosso", "para", "pela", "pelo", "pelos", "pois", "por", "porque", "qual", "que",
    "saber", "sem", "ser", "seu", "seus", "sua", "suas", "tambem", "tem", "toda",
    "todo", "todos", "uma", "deus", "cristo", "igreja", "homem", "homens", "vida",
}
def _tokens(value: str) -> tuple[str, ...]:
    return tuple(token for token in _TOKEN_RE.findall(_fold(value)) if token not in _STOPWORDS)


def _explicit_compendium_match(
    context: CccArticleQuery,
    units: Sequence[CatechismUnit],
) -> tuple[CatechismUnit, tuple[str, ...]] | None:
    candidates: list[tuple[tuple[int, int, int], CatechismUnit]] = []
    query_tokens = set(_tokens(context.article_text or ""))
    for unit in units:
        covering = [(start, end) for start, end in unit.ccc_ranges if start <= context.article <= end]
        if not covering:
            continue
        width = min(end - start for start, end in covering)
        overlap = len(query_tokens.intersection(_tokens(unit.searchable_text)))
        # Prefer the narrowest printed CCC range; lexical overlap only breaks
        # ties between multiple explicit references.
        candidates.append(((-width, overlap, -unit.question_number), unit))
    if not candidates:
        return None
    _, unit = max(candidates, key=lambda item: item[0])
    evidence = tuple(
        f"CCC §§ {start}–{end}" if start != end else f"CCC § {start}"
        for start, end in unit.ccc_ranges
        if start <= context.article <= end
    )
    return unit, evidence


# High-confidence thematic correspondences manually verified against the
# indexed São Pio X edition. These entries are ranges because adjacent CCC
# paragraphs usually elaborate the same doctrinal question. Unlisted
# paragraphs fail closed instead of being assigned by an opaque similarity
# score and mislabeled as verified.
_PIO_X_VERIFIED_CROSSWALK: tuple[tuple[int, int, int], ...] = (
    (232, 234, 130),   # Santíssima Trindade / Espírito Santo
    (456, 460, 68),    # O Filho de Deus se fez homem
    (1322, 1327, 594), # natureza e lugar da Eucaristia
    (1420, 1424, 670), # natureza do Sacramento da Penitência
    (2558, 2565, 253), # definição da oração
)


def _verified_pio_x_match(
    context: CccArticleQuery,
    units: Sequence[CatechismUnit],
) -> tuple[CatechismUnit, tuple[str, ...]] | None:
    question_number = next(
        (
            question
            for start, end, question in _PIO_X_VERIFIED_CROSSWALK
            if start <= context.article <= end
        ),
        None,
    )
    if question_number is None:
        return None
    unit = next(
        (entry for entry in units if entry.question_number == question_number),
        None,
    )
    if unit is None:
        return None
    # Evidence names the exact doctrine visible in the older catechism rather
    # than claiming that its question number equals the CCC paragraph.
    evidence = tuple(dict.fromkeys(_tokens(unit.question)))[:6]
    return unit, evidence


class CatechismConcordanceService:
    def __init__(self, source: CatechismUnitSource) -> None:
        self._source = source

    def find_comparisons(self, context: CccArticleQuery) -> tuple[CatechismComparison, ...]:
        if not context.is_exact or not context.article_text:
            raise ValueError("an exact CCC paragraph is required")

        comparisons: list[CatechismComparison] = []
        compendium = self._source.get_units("compendium")
        if compendium is None:
            comparisons.append(
                CatechismComparison(
                    status="source_unavailable",
                    source="compendium",
                    source_title=_SOURCE_TITLES["compendium"],
                    message="A fonte indexada está temporariamente indisponível.",
                )
            )
        else:
            explicit = _explicit_compendium_match(context, compendium)
            if explicit is None:
                comparisons.append(
                    CatechismComparison(
                        status="no_reliable_match",
                        source="compendium",
                        source_title=_SOURCE_TITLES["compendium"],
                        message="Nenhuma referência explícita a este parágrafo foi localizada.",
                    )
                )
            else:
                unit, evidence = explicit
                comparisons.append(
                    CatechismComparison(
                        status="matched",
                        source="compendium",
                        source_title=unit.source_title,
                        passage=unit.to_passage(),
                        match=CatechismMatch("explicit_cross_reference", "high", evidence),
                    )
                )

        pio_x = self._source.get_units("pio_x")
        if pio_x is None:
            comparisons.append(
                CatechismComparison(
                    status="source_unavailable",
                    source="pio_x",
                    source_title=_SOURCE_TITLES["pio_x"],
                    message="A fonte indexada está temporariamente indisponível.",
                )
            )
        else:
            thematic = _verified_pio_x_match(context, pio_x)
            if thematic is None:
                comparisons.append(
                    CatechismComparison(
                        status="no_reliable_match",
                        source="pio_x",
                        source_title=_SOURCE_TITLES["pio_x"],
                        message="Nenhuma correspondência temática atingiu o nível de confiança exigido.",
                    )
                )
            else:
                unit, evidence = thematic
                comparisons.append(
                    CatechismComparison(
                        status="matched",
                        source="pio_x",
                        source_title=unit.source_title,
                        passage=unit.to_passage(),
                        match=CatechismMatch("thematic", "high", evidence),
                    )
                )

        # This source exists in the catalogue, but the current OCR corrupts
        # words and locators. Exposing it would contradict the verification
        # promise, so it remains explicit and fail-closed until re-OCR.
        comparisons.append(
            CatechismComparison(
                status="source_unavailable",
                source="roman",
                source_title=_SOURCE_TITLES["roman"],
                message="Temporariamente indisponível: esta edição precisa de novo OCR para comparação segura.",
            )
        )
        return tuple(comparisons)


def build_default_catechism_concordance_service() -> CatechismConcordanceService:
    return CatechismConcordanceService(SqlAlchemyCatechismUnitSource())


__all__ = [
    "CatechismComparison",
    "CatechismConcordanceService",
    "CatechismMatch",
    "CatechismPassage",
    "CatechismSourceRef",
    "CatechismUnit",
    "SqlAlchemyCatechismUnitSource",
    "build_default_catechism_concordance_service",
    "parse_catechism_units",
]
