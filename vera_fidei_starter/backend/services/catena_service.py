from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping, Sequence


DEFAULT_CATENA_INDEX = "vera_fidei_chunks"
_MAX_VERSE_NUMBER = 200  # Psalm 119 has 176 verses; rejects obvious garbage such as Jo 6,999.


class BibleReferenceError(ValueError):
    """Raised when a Catena query is not one unambiguous Bible verse."""

    def __init__(self, message: str, *, code: str = "INVALID_BIBLE_REFERENCE") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BibleBook:
    key: str
    name: str
    max_chapter: int
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class BibleReference:
    book: BibleBook
    chapter: int
    verse_start: int
    verse_end: int | None = None

    @property
    def canonical(self) -> str:
        suffix = str(self.verse_start)
        if self.verse_end is not None:
            suffix += f"-{self.verse_end}"
        return f"{self.book.name} {self.chapter},{suffix}"


@dataclass(frozen=True)
class CatenaHit:
    chunk_id: int
    book_id: int
    score: float
    excerpt: str
    evidence_kind: str
    reasons: tuple[str, ...]
    text: str
    translation_text: str | None
    author: str | None
    work_title: str | None
    pdf_page: int | None
    chapter_or_section: str | None
    collection: str | None
    volume: int | None
    edition_label: str | None
    language: str | None


@dataclass(frozen=True)
class CatenaSearchResult:
    reference: BibleReference
    hits: tuple[CatenaHit, ...]
    candidate_count: int

    @property
    def hit_ids(self) -> tuple[int, ...]:
        return tuple(hit.chunk_id for hit in self.hits)


# The aliases deliberately have one owner each. In Portuguese, Jo = Joao and
# Jn = Jonas. This removes the old collision where Jn silently meant both.
_BOOKS: tuple[BibleBook, ...] = (
    BibleBook("gen", "Genesis", 50, ("Gn", "Gen", "Genesis")),
    BibleBook("ex", "Exodo", 40, ("Ex", "Exo", "Exodus")),
    BibleBook("lev", "Levitico", 27, ("Lv", "Lev", "Leviticus")),
    BibleBook("num", "Numeros", 36, ("Nm", "Num", "Numeri")),
    BibleBook("deut", "Deuteronomio", 34, ("Dt", "Deu", "Deuteronomium")),
    BibleBook("jos", "Josue", 24, ("Js", "Jos", "Josh", "Iosue")),
    BibleBook("judg", "Juizes", 21, ("Jz", "Jg", "Judices")),
    BibleBook("ruth", "Rute", 4, ("Rt", "Ruth")),
    BibleBook("1sam", "1 Samuel", 31, ("1Sm", "1 Sm", "1Sam", "I Sam", "I Sm")),
    BibleBook("2sam", "2 Samuel", 24, ("2Sm", "2 Sm", "2Sam", "II Sam", "II Sm")),
    BibleBook("1kgs", "1 Reis", 22, ("1Rs", "1 Rs", "1Re", "I Reg")),
    BibleBook("2kgs", "2 Reis", 25, ("2Rs", "2 Rs", "2Re", "II Reg")),
    BibleBook("1chr", "1 Cronicas", 29, ("1Cr", "1 Cr", "1Chr", "I Par")),
    BibleBook("2chr", "2 Cronicas", 36, ("2Cr", "2 Cr", "2Chr", "II Par")),
    BibleBook("ezra", "Esdras", 10, ("Esd", "Ezr", "Esdras")),
    BibleBook("neh", "Neemias", 13, ("Ne", "Neh", "Neem")),
    BibleBook("tob", "Tobias", 14, ("Tb", "Tob", "Tobit")),
    BibleBook("jdt", "Judite", 16, ("Jt", "Jdt", "Judith")),
    BibleBook("esth", "Ester", 16, ("Est", "Esth", "Ester")),
    BibleBook("1macc", "1 Macabeus", 16, ("1Mc", "1 Mc", "1Mac", "1 Mac", "I Macc")),
    BibleBook("2macc", "2 Macabeus", 15, ("2Mc", "2 Mc", "2Mac", "2 Mac", "II Macc")),
    BibleBook("job", "Jó", 42, ("Job",)),
    BibleBook("ps", "Salmos", 150, ("Sl", "Ps", "Salm", "Psalm", "Salmos")),
    BibleBook("prov", "Proverbios", 31, ("Pr", "Pro", "Prov")),
    BibleBook("eccl", "Eclesiastes", 12, ("Ec", "Ecl", "Qo", "Eccl")),
    BibleBook("song", "Cantico dos Canticos", 8, ("Ct", "Cant", "Cantares")),
    BibleBook("wis", "Sabedoria", 19, ("Sb", "Sap", "Wis")),
    BibleBook("sir", "Eclesiastico", 51, ("Sir", "Eclo", "Eccli")),
    BibleBook("isa", "Isaias", 66, ("Is", "Isa")),
    BibleBook("jer", "Jeremias", 52, ("Jr", "Jer")),
    BibleBook("lam", "Lamentacoes", 5, ("Lm", "Lam")),
    BibleBook("bar", "Baruc", 6, ("Bar", "Baruch")),
    BibleBook("ezek", "Ezequiel", 48, ("Ez", "Ezek")),
    BibleBook("dan", "Daniel", 14, ("Dn", "Dan")),
    BibleBook("hos", "Oseias", 14, ("Os", "Hos")),
    BibleBook("joel", "Joel", 4, ("Jl", "Joel")),
    BibleBook("amos", "Amos", 9, ("Am", "Amos")),
    BibleBook("obad", "Abdias", 1, ("Ab", "Obad")),
    BibleBook("jonah", "Jonas", 4, ("Jn", "Jon", "Jonas", "Jonah")),
    BibleBook("mic", "Miqueias", 7, ("Mq", "Mic")),
    BibleBook("nah", "Naum", 3, ("Na", "Nah")),
    BibleBook("hab", "Habacuc", 3, ("Hab", "Habacuc")),
    BibleBook("zeph", "Sofonias", 3, ("Sf", "Zep")),
    BibleBook("hag", "Ageu", 2, ("Ag", "Hag")),
    BibleBook("zech", "Zacarias", 14, ("Zc", "Zec")),
    BibleBook("mal", "Malaquias", 4, ("Ml", "Mal")),
    BibleBook("matt", "Mateus", 28, ("Mt", "Mat", "Matt", "Matth", "Mateus")),
    BibleBook("mark", "Marcos", 16, ("Mc", "Mr", "Mk", "Marc", "Marcos")),
    BibleBook("luke", "Lucas", 24, ("Lc", "Lk", "Luc", "Lucas")),
    BibleBook("john", "João", 21, ("Jo", "Ioh", "Ioan", "John", "Joao")),
    BibleBook("acts", "Atos", 28, ("At", "Act", "Acts", "Atos dos Apostolos")),
    BibleBook("rom", "Romanos", 16, ("Rm", "Rom", "Ro")),
    BibleBook("1cor", "1 Corintios", 16, ("1Cor", "1 Cor", "1Co", "1 Co", "I Cor")),
    BibleBook("2cor", "2 Corintios", 13, ("2Cor", "2 Cor", "2Co", "2 Co", "II Cor")),
    BibleBook("gal", "Galatas", 6, ("Gl", "Gal", "Ga")),
    BibleBook("eph", "Efesios", 6, ("Ef", "Eph", "Ep")),
    BibleBook("phil", "Filipenses", 4, ("Fp", "Fil", "Phil")),
    BibleBook("col", "Colossenses", 4, ("Cl", "Col")),
    BibleBook("1thess", "1 Tessalonicenses", 5, ("1Ts", "1 Ts", "1Tess", "I Thess")),
    BibleBook("2thess", "2 Tessalonicenses", 3, ("2Ts", "2 Ts", "2Tess", "II Thess")),
    BibleBook("1tim", "1 Timoteo", 6, ("1Tm", "1 Tm", "1Tim", "I Tim")),
    BibleBook("2tim", "2 Timoteo", 4, ("2Tm", "2 Tm", "2Tim", "II Tim")),
    BibleBook("titus", "Tito", 3, ("Tt", "Tit", "Tito")),
    BibleBook("phlm", "Filemon", 1, ("Fm", "Phm", "Philem")),
    BibleBook("heb", "Hebreus", 13, ("Hb", "Heb")),
    BibleBook("jas", "Tiago", 5, ("Tg", "Jac", "Jas")),
    BibleBook("1pet", "1 Pedro", 5, ("1Pd", "1 Pd", "1Pe", "1 Pe", "I Pet")),
    BibleBook("2pet", "2 Pedro", 3, ("2Pd", "2 Pd", "2Pe", "2 Pe", "II Pet")),
    BibleBook("1john", "1 Joao", 5, ("1Jo", "1 Jo", "1Ioh", "1 Ioh", "I Ioan")),
    BibleBook("2john", "2 Joao", 1, ("2Jo", "2 Jo", "2Ioh", "2 Ioh", "II Ioan")),
    BibleBook("3john", "3 Joao", 1, ("3Jo", "3 Jo", "3Ioh", "3 Ioh", "III Ioan")),
    BibleBook("jude", "Judas", 1, ("Jd", "Jud", "Jude")),
    BibleBook("rev", "Apocalipse", 22, ("Ap", "Apo", "Apoc", "Rev")),
)


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("º", " ").replace("ª", " ")
    value = re.sub(r"(?<=\d)(?=[a-z])", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _accent_key(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    value = re.sub(r"(?<=\d)(?=[a-zà-öø-ÿ])", " ", value)
    value = re.sub(r"[^0-9a-zà-öø-ÿ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _build_alias_lookups() -> tuple[dict[str, BibleBook], dict[str, tuple[BibleBook, ...]]]:
    exact: dict[str, BibleBook] = {}
    folded: dict[str, list[BibleBook]] = {}
    for book in _BOOKS:
        for alias in (book.name, *book.aliases):
            exact_key = _accent_key(alias)
            owner = exact.get(exact_key)
            if owner is not None and owner.key != book.key:
                raise RuntimeError(f"Alias biblico ambiguo: {alias!r} ({owner.key}/{book.key})")
            exact[exact_key] = book
            fold_key = _fold(alias)
            owners = folded.setdefault(fold_key, [])
            if all(existing.key != book.key for existing in owners):
                owners.append(book)
    return exact, {key: tuple(value) for key, value in folded.items()}


_EXACT_ALIAS_TO_BOOK, _FOLDED_ALIAS_TO_BOOKS = _build_alias_lookups()
_REFERENCE_RE = re.compile(
    r"^\s*(?P<book>(?:[1-3]\s*)?[A-Za-zÀ-ÖØ-öø-ÿ]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ]+)*)"
    r"\s+(?P<chapter>\d{1,3})\s*[,.:]\s*(?P<verse>\d{1,3})"
    r"(?:\s*[-–—]\s*(?P<verse_end>\d{1,3}))?\s*$",
    re.UNICODE,
)


def parse_bible_reference(raw: str) -> BibleReference:
    """Parse exactly one canonical book + chapter + verse (or verse range)."""

    match = _REFERENCE_RE.fullmatch(raw or "")
    if match is None:
        raise BibleReferenceError(
            "Use livro, capitulo e versiculo, por exemplo: Jo 6,53 ou Mt 16,18.",
            code="REFERENCE_FORMAT_REQUIRED",
        )

    raw_book = match.group("book")
    book = _EXACT_ALIAS_TO_BOOK.get(_accent_key(raw_book))
    if book is None:
        folded_owners = _FOLDED_ALIAS_TO_BOOKS.get(_fold(raw_book), ())
        if len(folded_owners) == 1:
            book = folded_owners[0]
        elif len(folded_owners) > 1:
            options = ", ".join(owner.name for owner in folded_owners)
            raise BibleReferenceError(
                f"Abreviatura biblica ambigua; use um destes nomes: {options}.",
                code="AMBIGUOUS_BIBLE_BOOK",
            )
    if book is None:
        raise BibleReferenceError(
            f"Livro biblico desconhecido: {match.group('book').strip()}.",
            code="UNKNOWN_BIBLE_BOOK",
        )

    chapter = int(match.group("chapter"))
    verse_start = int(match.group("verse"))
    verse_end = int(match.group("verse_end")) if match.group("verse_end") else None
    if not 1 <= chapter <= book.max_chapter:
        raise BibleReferenceError(
            f"{book.name} possui capitulos de 1 a {book.max_chapter}.",
            code="INVALID_BIBLE_CHAPTER",
        )
    if not 1 <= verse_start <= _MAX_VERSE_NUMBER:
        raise BibleReferenceError("Versiculo fora do intervalo aceito.", code="INVALID_BIBLE_VERSE")
    if verse_end is not None:
        if not verse_start <= verse_end <= _MAX_VERSE_NUMBER:
            raise BibleReferenceError("Intervalo de versiculos invalido.", code="INVALID_BIBLE_RANGE")

    return BibleReference(book, chapter, verse_start, verse_end)


def _reference_variants(reference: BibleReference) -> tuple[str, ...]:
    aliases = dict.fromkeys((reference.book.name, *reference.book.aliases))
    verse = str(reference.verse_start)
    if reference.verse_end is not None:
        verse += f"-{reference.verse_end}"
    variants: list[str] = []
    for alias in aliases:
        for separator in (",", ":", "."):
            variants.append(f"{alias} {reference.chapter}{separator}{verse}")
            if reference.verse_end is not None:
                variants.append(f"{alias} {reference.chapter}{separator}{reference.verse_start}")
    return tuple(dict.fromkeys(variants))


def build_catena_es_query(
    reference: BibleReference,
    patristic_book_ids: Sequence[int],
    *,
    catena_book_ids: Sequence[int] = (),
    candidate_limit: int,
) -> dict[str, Any]:
    """Build the filtered candidate query; local code performs the final ranking."""

    allowed = sorted(
        {int(book_id) for book_id in (*patristic_book_ids, *catena_book_ids) if int(book_id) > 0}
    )
    if not allowed:
        raise ValueError("patristic_book_ids must contain at least one positive ID")

    should: list[dict[str, Any]] = []
    for variant in _reference_variants(reference):
        for field in ("text", "translation_text"):
            should.append({"match_phrase": {field: {"query": variant, "boost": 3.0}}})

    # Some commentaries identify a verse only as [6:53] because the work title
    # already supplies the biblical book. These markers are retrieval hints;
    # title scope and substantive prose are verified by the local ranker.
    marker = f"{reference.chapter}:{reference.verse_start}"
    marker_spaced = f"{reference.chapter}: {reference.verse_start}"
    for value in (marker, marker_spaced):
        for field in ("text", "translation_text"):
            should.append({"match_phrase": {field: {"query": value, "boost": 0.3}}})

    curated_catena = sorted({int(book_id) for book_id in catena_book_ids if int(book_id) > 0})
    if curated_catena:
        # Catena volumes commonly use a range header in one chunk and begin the
        # commentary in the next. A low-boost chapter seed gives the local
        # header parser enough recall without allowing non-curated TEO books.
        for alias in dict.fromkeys((reference.book.name, *reference.book.aliases)):
            for field in ("text", "translation_text"):
                should.append(
                    {
                        "bool": {
                            "filter": [{"terms": {"book_id": curated_catena}}],
                            "must": [
                                {
                                    "match_phrase": {
                                        field: {"query": f"{alias} {reference.chapter}", "boost": 0.15}
                                    }
                                }
                            ],
                        }
                    }
                )

    return {
        "query": {
            "bool": {
                "filter": [{"terms": {"book_id": allowed}}],
                "should": should,
                "minimum_should_match": 1,
            }
        },
        "size": candidate_limit,
        "_source": [
            "chunk_id",
            "book_id",
            "text",
            "translation_text",
            "author",
            "work_title",
            "pdf_page",
            "chapter_or_section",
            "collection",
            "volume",
            "edition_label",
            "language",
        ],
    }


_SCOPE_WORDS = re.compile(
    r"\b(catena|evangelh|gospel|comment|homil|tract|tratad|exposi|sermo|sermon|salmo|psalm)\w*\b"
)
_INTERPRETIVE_WORDS = re.compile(
    r"\b(isto e|quer dizer|significa|como se|portanto|porque|pois|ensina|explica|"
    r"entende|misterio|sentido|figura|alegor|faith|means|therefore|because|mystery)\w*\b"
)
_PATRISTIC_LABELS = re.compile(
    r"\b(santo|santa|sao|st|saint|origenes|agostinho|ambrosio|jeronimo|crisostomo|beda|hilario|cirilo|gregorio)\b"
)
_FRONT_MATTER = re.compile(
    r"\b(indice|index|sumario|contents|bibliograf|referencias|references|notas|notes|errata)\b"
)
_BIBLE_CITATION = re.compile(
    r"\b(?:[1-3]\s*)?[A-Za-zÀ-ÖØ-öø-ÿ]{1,12}\.?\s+\d{1,3}\s*[,.:]\s*\d{1,3}(?:\s*[-–—]\s*\d{1,3})?"
)


def _book_alias_tokens(reference: BibleReference) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_fold(alias) for alias in (reference.book.name, *reference.book.aliases)))


def _work_scopes_book(work_title: str, reference: BibleReference) -> bool:
    folded = _fold(work_title)
    if not _SCOPE_WORDS.search(folded):
        return False
    return any(re.search(rf"\b{re.escape(alias)}\b", folded) for alias in _book_alias_tokens(reference))


def _numeric_match(text: str, reference: BibleReference) -> re.Match[str] | None:
    end = reference.verse_end
    suffix = rf"(?:\s*[-–—]\s*{end})?" if end is not None else ""
    pattern = re.compile(
        rf"(?<!\d){reference.chapter}\s*[,.:]\s*{reference.verse_start}{suffix}(?!\d)",
        re.IGNORECASE,
    )
    return pattern.search(text)


_HEADER_NUMERIC = re.compile(
    r"(?:^|\[|\(|\b)(?P<chapter>\d{1,3})\s*[,.:]\s*(?P<start>\d{1,3})"
    r"(?:\s*[-–—]\s*(?P<end>\d{1,3}))?(?:\]|\)|\b)",
    re.UNICODE,
)


def _range_contains(reference: BibleReference, chapter: int, start: int, end: int | None) -> bool:
    upper = end if end is not None else start
    wanted_end = reference.verse_end if reference.verse_end is not None else reference.verse_start
    return chapter == reference.chapter and start <= reference.verse_start and wanted_end <= upper


def reference_in_bible_header(
    text: str,
    reference: BibleReference,
    *,
    work_title: str = "",
) -> bool:
    """Return whether a heading/range covers the requested verse.

    Book-less forms such as ``[6:52-54]`` are accepted only when the curated
    work title itself scopes the text to the requested biblical book.
    """

    if work_title and not _work_scopes_book(work_title, reference):
        return False

    alias_pattern = "|".join(
        re.escape(alias).replace(r"\ ", r"\s+")
        for alias in sorted(
            dict.fromkeys((reference.book.name, *reference.book.aliases)),
            key=len,
            reverse=True,
        )
    )
    full_header = re.compile(
        rf"(?<!\w)(?:{alias_pattern})\s+(?P<chapter>\d{{1,3}})\s*[,.:]\s*"
        rf"(?P<start>\d{{1,3}})\s*[-–—]\s*(?P<end>\d{{1,3}})(?!\d)",
        re.IGNORECASE | re.UNICODE,
    )
    for match in full_header.finditer(text or ""):
        if _range_contains(
            reference,
            int(match.group("chapter")),
            int(match.group("start")),
            int(match.group("end")) if match.group("end") else None,
        ):
            return True

    if not work_title or not _work_scopes_book(work_title, reference):
        return False
    for match in _HEADER_NUMERIC.finditer(text or ""):
        if match.group("end") is None:
            continue
        if _range_contains(
            reference,
            int(match.group("chapter")),
            int(match.group("start")),
            int(match.group("end")) if match.group("end") else None,
        ):
            return True
    return False


def _contains_scoped_range_header(text: str, reference: BibleReference, work_title: str) -> bool:
    if not _work_scopes_book(work_title, reference):
        return False
    alias_pattern = "|".join(
        re.escape(alias).replace(r"\ ", r"\s+")
        for alias in sorted(
            dict.fromkeys((reference.book.name, *reference.book.aliases)),
            key=len,
            reverse=True,
        )
    )
    return bool(
        re.search(
            rf"(?<!\w)(?:{alias_pattern})\s+\d{{1,3}}\s*[,.:]\s*\d{{1,3}}\s*[-–—]\s*\d{{1,3}}(?!\d)",
            text or "",
            re.IGNORECASE | re.UNICODE,
        )
    )


def _explicit_book_reference(text: str, reference: BibleReference) -> bool:
    folded = _fold(text)
    number_phrase = f"{reference.chapter} {reference.verse_start}"
    for alias in _book_alias_tokens(reference):
        if re.search(rf"\b{re.escape(alias)}\s+{re.escape(number_phrase)}\b", folded):
            return True
    return False


def _center_excerpt(text: str, match: re.Match[str] | None, *, radius: int = 360) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return ""
    if match is None:
        return clean[: radius * 2]
    # Whitespace collapsing changes positions slightly, but the bounded raw
    # position still centers the evidence much better than text[:700].
    center = min(len(clean), (match.start() + match.end()) // 2)
    start = max(0, center - radius)
    end = min(len(clean), center + radius)
    return clean[start:end].strip()


def _looks_like_reference_dump(window: str, section: str) -> bool:
    folded = _fold(f"{section} {window}")
    if _FRONT_MATTER.search(folded) and len(window.split()) < 180:
        return True
    citation_count = len(_BIBLE_CITATION.findall(window))
    sentences = len(re.findall(r"[.!?](?:\s|$)", window))
    prose_words = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{4,}", window))
    return citation_count >= 5 and (sentences <= 2 or prose_words < citation_count * 8)


def _rank_candidate(
    source: Mapping[str, Any],
    es_score: float,
    reference: BibleReference,
    *,
    curated_catena: bool = False,
    header_context: bool = False,
) -> CatenaHit | None:
    try:
        chunk_id = int(source["chunk_id"])
        book_id = int(source["book_id"])
    except (KeyError, TypeError, ValueError):
        return None

    original = str(source.get("text") or "")
    translation = str(source.get("translation_text") or "")
    searchable = original if len(original) >= len(translation) else translation
    numeric = _numeric_match(searchable, reference)
    explicit = _explicit_book_reference(searchable, reference)
    scoped = _work_scopes_book(str(source.get("work_title") or ""), reference)
    header_match = curated_catena and reference_in_bible_header(
        searchable,
        reference,
        work_title=str(source.get("work_title") or ""),
    )
    if numeric is None and not explicit and not header_match and not header_context:
        return None

    excerpt = _center_excerpt(searchable, numeric)
    folded_excerpt = _fold(excerpt)
    section = str(source.get("chapter_or_section") or "")
    reference_dump = _looks_like_reference_dump(excerpt, section)

    reasons: list[str] = []
    score = min(4.0, math.log1p(max(0.0, float(es_score))))
    if curated_catena and (scoped or header_match or header_context):
        score += 30.0
        reasons.append("catena_curada_no_escopo")
    elif curated_catena:
        score += 4.0
        reasons.append("catena_curada_fora_do_escopo")
    if header_context:
        score += 42.0
        reasons.append("contexto_de_cabecalho_catena")
    elif header_match:
        score += 16.0
        reasons.append("cabecalho_cobre_versiculo")
    if explicit:
        score += 34.0
        reasons.append("referencia_explicita")
    if numeric is not None and scoped:
        score += 38.0
        reasons.append("versiculo_no_escopo_da_obra")
    elif numeric is not None:
        score += 8.0
        reasons.append("marcador_numerico")

    word_count = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}", excerpt))
    if word_count >= 45:
        score += 16.0
        reasons.append("contexto_substantivo")
    if _INTERPRETIVE_WORDS.search(folded_excerpt):
        score += 14.0
        reasons.append("linguagem_exegetica")
    if _PATRISTIC_LABELS.search(folded_excerpt):
        score += 10.0
        reasons.append("autor_patristico_no_contexto")
    if reference_dump:
        score -= 52.0
        reasons.append("lista_de_referencias")
    if _FRONT_MATTER.search(_fold(section)):
        score -= 45.0
        reasons.append("secao_pre_textual")
    page = int(source["pdf_page"]) if source.get("pdf_page") is not None else None
    if curated_catena and page is not None and page <= 15 and not header_context:
        score -= 60.0
        reasons.append("paginas_preliminares")

    # A bare citation/list is not a Catena answer. Keep weak prose references
    # only when they have at least some explanatory context.
    if score < 20.0 or (reference_dump and "linguagem_exegetica" not in reasons):
        return None

    if header_context:
        evidence_kind = "catena_header_context"
    elif header_match:
        evidence_kind = "catena_header"
    else:
        evidence_kind = "scoped_verse" if scoped and numeric is not None else "explicit_reference"
    return CatenaHit(
        chunk_id=chunk_id,
        book_id=book_id,
        score=round(score, 3),
        excerpt=excerpt,
        evidence_kind=evidence_kind,
        reasons=tuple(reasons),
        text=original,
        translation_text=translation or None,
        author=str(source.get("author")) if source.get("author") else None,
        work_title=str(source.get("work_title")) if source.get("work_title") else None,
        pdf_page=page,
        chapter_or_section=section or None,
        collection=str(source.get("collection")) if source.get("collection") else None,
        volume=int(source["volume"]) if source.get("volume") is not None else None,
        edition_label=str(source.get("edition_label")) if source.get("edition_label") else None,
        language=str(source.get("language")) if source.get("language") else None,
    )


def _near_duplicate(left: CatenaHit, right: CatenaHit) -> bool:
    if left.book_id != right.book_id:
        return False
    if left.pdf_page is not None and right.pdf_page is not None and abs(left.pdf_page - right.pdf_page) > 1:
        return False
    a = _fold(left.excerpt)
    b = _fold(right.excerpt)
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.72


def _deduplicate(hits: Iterable[CatenaHit]) -> list[CatenaHit]:
    kept: list[CatenaHit] = []
    for hit in hits:
        if any(_near_duplicate(hit, existing) for existing in kept):
            continue
        kept.append(hit)
    return kept


def search_catena(
    es: Any,
    raw_reference: str,
    patristic_book_ids: Sequence[int],
    *,
    catena_book_ids: Sequence[int] = (),
    limit: int = 20,
    index: str = DEFAULT_CATENA_INDEX,
) -> CatenaSearchResult:
    """Return ranked, deduplicated patristic commentary candidates.

    ``es`` is an Elasticsearch-compatible object exposing ``search``. The
    caller remains responsible for obtaining the authoritative patristic book
    IDs from PostgreSQL. An empty allow-list intentionally returns no hits.
    """

    reference = parse_bible_reference(raw_reference)
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    patristic_ids = {int(book_id) for book_id in patristic_book_ids if int(book_id) > 0}
    curated_catena_ids = {int(book_id) for book_id in catena_book_ids if int(book_id) > 0}
    allowed_ids = tuple(sorted(patristic_ids | curated_catena_ids))
    if not allowed_ids:
        return CatenaSearchResult(reference=reference, hits=(), candidate_count=0)

    candidate_limit = min(500, max(100, limit * 10))
    body = build_catena_es_query(
        reference,
        tuple(sorted(patristic_ids)),
        catena_book_ids=tuple(sorted(curated_catena_ids)),
        candidate_limit=candidate_limit,
    )
    response = es.search(index=index, body=body)
    raw_hits = list(response.get("hits", {}).get("hits", []))
    allowed = set(allowed_ids)

    # Expand forward from a curated Catena range header. Chunk IDs are
    # sequential within an ingested book; the next one or two chunks normally
    # contain the patristic comments belonging to that header.
    header_seeds: list[tuple[int, int]] = []
    for raw_hit in raw_hits:
        source = raw_hit.get("_source") or {}
        try:
            source_book_id = int(source.get("book_id"))
            source_chunk_id = int(source.get("chunk_id"))
        except (TypeError, ValueError):
            continue
        if source_book_id not in curated_catena_ids:
            continue
        searchable = str(source.get("text") or source.get("translation_text") or "")
        if reference_in_bible_header(
            searchable,
            reference,
            work_title=str(source.get("work_title") or ""),
        ):
            header_seeds.append((source_book_id, source_chunk_id))

    contextual_ids: set[int] = set()
    if header_seeds:
        requested_neighbors = sorted(
            {chunk_id + offset for _, chunk_id in header_seeds for offset in range(1, 9)}
        )
        neighbor_response = es.search(
            index=index,
            body={
                "query": {
                    "bool": {
                        "filter": [
                            {"terms": {"book_id": sorted(curated_catena_ids)}},
                            {"terms": {"chunk_id": requested_neighbors}},
                        ]
                    }
                },
                "size": len(requested_neighbors),
                "_source": body["_source"],
            },
        )
        seen_ids = {
            int(item.get("_source", {}).get("chunk_id"))
            for item in raw_hits
            if item.get("_source", {}).get("chunk_id") is not None
        }
        neighbor_by_key: dict[tuple[int, int], Mapping[str, Any]] = {}
        raw_neighbor_by_key: dict[tuple[int, int], Mapping[str, Any]] = {}
        for neighbor in neighbor_response.get("hits", {}).get("hits", []):
            source = neighbor.get("_source") or {}
            try:
                chunk_id = int(source.get("chunk_id"))
                book_id = int(source.get("book_id"))
            except (TypeError, ValueError):
                continue
            neighbor_by_key[(book_id, chunk_id)] = source
            raw_neighbor_by_key[(book_id, chunk_id)] = neighbor

        for seed_book, seed_chunk in header_seeds:
            for offset in range(1, 9):
                key = (seed_book, seed_chunk + offset)
                source = neighbor_by_key.get(key)
                if source is None:
                    continue
                searchable = str(source.get("text") or source.get("translation_text") or "")
                work_title = str(source.get("work_title") or "")
                if _contains_scoped_range_header(searchable, reference, work_title):
                    break
                chunk_id = seed_chunk + offset
                contextual_ids.add(chunk_id)
                if chunk_id not in seen_ids:
                    raw_hits.append(raw_neighbor_by_key[key])
                    seen_ids.add(chunk_id)

    ranked: list[CatenaHit] = []
    for raw_hit in raw_hits:
        source = raw_hit.get("_source") or {}
        try:
            source_book_id = int(source.get("book_id"))
        except (TypeError, ValueError):
            continue
        if source_book_id not in allowed:  # Defensive even if a fake/proxy ES ignores filters.
            continue
        source_chunk_id = int(source.get("chunk_id"))
        hit = _rank_candidate(
            source,
            float(raw_hit.get("_score") or 0.0),
            reference,
            curated_catena=source_book_id in curated_catena_ids,
            header_context=source_chunk_id in contextual_ids,
        )
        if hit is not None:
            ranked.append(hit)

    ranked.sort(key=lambda item: (-item.score, item.book_id, item.chunk_id))
    unique = _deduplicate(ranked)
    return CatenaSearchResult(
        reference=reference,
        hits=tuple(unique[:limit]),
        candidate_count=len(raw_hits),
    )


__all__ = [
    "BibleReference",
    "BibleReferenceError",
    "CatenaHit",
    "CatenaSearchResult",
    "build_catena_es_query",
    "parse_bible_reference",
    "reference_in_bible_header",
    "search_catena",
]
