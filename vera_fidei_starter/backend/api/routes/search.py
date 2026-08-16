from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, replace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.auth import require_api_key
from core.config import settings
from core.deps import get_current_user, get_optional_user
from core.plans import search_daily_limit_for_plan
from models.database import Book, BookFile, Chunk, SearchUsage, SessionLocal, VerifiedPassage
from search.content_quality import assess_content, extract_semantic_passage, filter_quotable_hits
from search.text_search import (
    PATRISTIC_COLLECTIONS,
    TextSearchClient,
    theological_literal_variants,
)
from services.catena_service import BibleReferenceError, parse_bible_reference, search_catena
from services.ccc_commentary_service import (
    CccCommentaryService,
    SqlAlchemyCccArticleSource,
    SqlAlchemyPatristicChunkFilter,
)
from services.catechism_concordance_service import (
    CatechismConcordanceService,
    CatechismPassage,
    SqlAlchemyCatechismUnitSource,
)
from services.source_fidelity_service import (
    PUBLIC_SOURCE_FIDELITIES,
    VerifiedPassageCandidate,
    normalize_literal,
    select_verified_passage,
)

router = APIRouter()
_log = logging.getLogger(__name__)

_text_client: TextSearchClient | None = None
_ccc_service: CccCommentaryService | None = None
_catechism_concordance: CatechismConcordanceService | None = None

# Cache of patristic book IDs (refreshed every hour)
_patristic_ids_cache: list[int] = []
_patristic_ids_ts: float = 0.0
_PATRISTIC_CACHE_TTL = 3600.0
_QUOTE_SCAN_BATCH_SIZE = 120


def _client() -> TextSearchClient:
    global _text_client
    if _text_client is None:
        _text_client = TextSearchClient()
    return _text_client


def _ccc_commentary_service() -> CccCommentaryService:
    global _ccc_service
    if _ccc_service is None:
        _ccc_service = CccCommentaryService(
            article_source=SqlAlchemyCccArticleSource(),
            search_client=_client(),
            patristic_filter=SqlAlchemyPatristicChunkFilter(),
            patristic_book_ids_provider=_get_patristic_book_ids,
        )
    return _ccc_service


def _catechism_concordance_service() -> CatechismConcordanceService:
    global _catechism_concordance
    if _catechism_concordance is None:
        _catechism_concordance = CatechismConcordanceService(
            SqlAlchemyCatechismUnitSource()
        )
    return _catechism_concordance


def _get_patristic_book_ids() -> list[int]:
    """Return IDs of patristic books that are NOT in PL/PG/PO collection.
    (PL/PG/PO are already guaranteed by the collection filter in ES.)
    Covers Paulus Portuguese editions, English ANF/NPNF, and similar."""
    global _patristic_ids_cache, _patristic_ids_ts
    if time.time() - _patristic_ids_ts < _PATRISTIC_CACHE_TTL:
        return _patristic_ids_cache
    try:
        with SessionLocal() as db:
            from sqlalchemy import or_, not_
            rows = db.query(Book.id).filter(
                or_(
                    Book.library_section == "patristica",
                    Book.patristic_tradition.isnot(None),
                ),
                not_(Book.collection.in_(["PL", "PG", "PO"])),
            ).all()
        _patristic_ids_cache = [r.id for r in rows]
        _patristic_ids_ts = time.time()
    except Exception:
        pass
    return _patristic_ids_cache


# ─── Modelos de resposta ──────────────────────────────────────────────────────

class AcervoResult(BaseModel):
    chunk_id: int
    text: str
    author: str | None
    chunk_author: str | None
    work_title: str | None
    pdf_page: int | None
    chapter_or_section: str | None
    collection: str | None
    volume: int | None
    edition_label: str | None
    language: str | None
    translation_text: str | None
    relevance_score: float
    book_id: int | None
    book_file_id: int | None
    library_section: str | None
    patristic_tradition: str | None
    source_fidelity: str
    source_fidelity_label: str
    source_warning: str | None = None
    matched_query: str | None = None
    match_type: str = "literal"


class AcervoSearchResponse(BaseModel):
    results: list[AcervoResult]
    total: int
    query: str
    patristic_results: list[AcervoResult] = Field(default_factory=list)
    returned: int = 0
    readable_total: int = 0
    matching_works: int = 0
    has_more: bool = False
    next_cursor: str | None = None
    # ES-level totals (from cardinality aggregations, not affected by quality gate)
    total_matching_pages: int = 0
    total_matching_works: int = 0
    expanded_terms: list[str] = Field(default_factory=list)


class SearchUsageResponse(BaseModel):
    plan: str
    limit: int | None
    used: int
    remaining: int | None


class DailyCitationResponse(BaseModel):
    chunk_id: int | None
    text: str | None
    author: str | None
    work_title: str | None
    pdf_page: int | None
    chapter_or_section: str | None
    edition_label: str | None
    language: str | None
    translation_text: str | None
    book_id: int | None
    book_file_id: int | None
    day_of_year: int
    source_fidelity: str | None = None
    source_fidelity_label: str | None = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _query_centered_excerpt(text: str | None, query: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= limit:
        return clean
    terms = [
        token
        for token in re.findall(r"[\wÀ-ÿ]{3,}", query or "", re.UNICODE)
        if token.casefold() not in {"para", "como", "sobre", "este", "esta", "uma", "dos", "das"}
    ]
    folded = _norm(clean)
    positions = [folded.find(_norm(term)) for term in terms]
    positions = [position for position in positions if position >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - limit // 3)
    end = min(len(clean), start + limit)
    start = max(0, end - limit)
    prefix = "… " if start else ""
    suffix = " …" if end < len(clean) else ""
    return f"{prefix}{clean[start:end].strip()}{suffix}"


def _enrich_with_db(
    hits: list,
    *,
    query: str = "",
    preexcerpted: bool = False,
    require_source_verified: bool = False,
) -> list[AcervoResult]:
    """Add book_id / book_file_id / chunk_author / library_section / patristic_tradition from Postgres."""
    if not hits:
        return []
    chunk_ids = [h.chunk_id for h in hits]
    with SessionLocal() as db:
        rows = (
            db.query(Chunk.id, Chunk.book_id, Chunk.book_file_id, Chunk.chunk_author,
                     Chunk.extraction_method, Chunk.source_fidelity, Chunk.fidelity_score,
                     Book.library_section, Book.patristic_tradition)
            .join(Book, Chunk.book_id == Book.id, isouter=True)
            .filter(Chunk.id.in_(chunk_ids))
            .all()
        )
        book_ids = sorted({row.book_id for row in rows if row.book_id is not None})
        pages = sorted({hit.pdf_page for hit in hits if hit.pdf_page is not None})
        verified_rows = (
            db.query(VerifiedPassage)
            .filter(
                VerifiedPassage.book_id.in_(book_ids),
                VerifiedPassage.pdf_page.in_(pages),
            )
            .all()
            if book_ids and pages else []
        )
    meta = {
        r.id: {
            "book_id": r.book_id,
            "book_file_id": r.book_file_id,
            "chunk_author": r.chunk_author,
            "library_section": r.library_section,
            "patristic_tradition": r.patristic_tradition,
            "extraction_method": r.extraction_method,
            "source_fidelity": r.source_fidelity,
            "fidelity_score": r.fidelity_score,
        }
        for r in rows
    }
    verified_by_source: dict[tuple[int, int], list[VerifiedPassageCandidate]] = {}
    for passage in verified_rows:
        verified_by_source.setdefault((passage.book_id, passage.pdf_page), []).append(
            VerifiedPassageCandidate(
                text=passage.text,
                language=passage.language,
                method=passage.verification_method,
            )
        )
    results = []
    for hit in hits:
        m = meta.get(hit.chunk_id, {})
        raw_text = (hit.text or "") if preexcerpted else _query_centered_excerpt(hit.text, query, 700)
        matched_v: str | None = None  # set in OCR branch; used for matched_query
        verified = _select_verified_passage_for_query(
            raw_text,
            query,
            verified_by_source.get((m.get("book_id"), hit.pdf_page), ()),
        )
        stored_fidelity = m.get("source_fidelity") or "unverified"
        if verified is not None:
            # A full-page visual review is authoritative, but returning all
            # columns/footnotes makes one card dominate mobile screens. Keep
            # the wording untouched and select only a query-centred window.
            public_text = _query_centered_excerpt(
                verified.text,
                _matching_query_variant(verified.text, query) or query,
                700,
            )
            fidelity = "verified_transcription"
            fidelity_label = "Transcrição conferida com a página do PDF"
            source_warning = None
        elif stored_fidelity == "verified":
            public_text = raw_text
            fidelity = "verified_transcription"
            fidelity_label = "Transcrição conferida com a página do PDF"
            source_warning = None
        elif stored_fidelity == "source_text":
            public_text = raw_text
            fidelity = "source_text"
            fidelity_label = "Texto nativo da edição indexada"
            source_warning = None
        else:
            if require_source_verified:
                continue
            # Show an OCR excerpt centered on the matched variant so the user
            # can see the term highlighted before opening the PDF. The text is
            # labelled OCR-unverified; never presented as the edition wording.
            locator_variants = _query_literal_variants(query) if query else [query]
            matched_v = next(
                (v for v in locator_variants if v and _literal_query_supported(raw_text, v)),
                None,
            )
            public_text = (
                _query_centered_excerpt(raw_text, matched_v, 400)
                if matched_v and raw_text
                else ""
            )
            fidelity = "unverified_ocr"
            fidelity_label = "Página sugerida pelo índice; texto ainda não conferido"
            source_warning = (
                "Texto OCR — não conferido com a edição impressa. "
                "Abra o PDF para ler a redação original."
            )
        results.append(AcervoResult(
            chunk_id=hit.chunk_id,
            text=public_text,
            author=hit.author or None,
            chunk_author=m.get("chunk_author") or None,
            work_title=hit.work_title or None,
            pdf_page=hit.pdf_page,
            chapter_or_section=(hit.chapter_or_section or None) if fidelity != "unverified_ocr" else None,
            collection=hit.collection or None,
            volume=hit.volume,
            edition_label=hit.edition_label or None,
            language=hit.language or None,
            # Legacy translations have no independent page-level provenance.
            # They remain searchable internally, but cannot be displayed as
            # literal writing until a verified-translation record exists.
            translation_text=None,
            relevance_score=round(hit.score, 3),
            book_id=m.get("book_id"),
            book_file_id=m.get("book_file_id"),
            library_section=m.get("library_section"),
            patristic_tradition=m.get("patristic_tradition"),
            source_fidelity=fidelity,
            source_fidelity_label=fidelity_label,
            source_warning=source_warning,
            matched_query=(
                matched_v  # variant found in OCR text (e.g. "Eucharistia")
                if fidelity == "unverified_ocr"
                else _matching_query_variant(public_text, query)
            ),
            match_type=getattr(hit, "match_type", "literal"),
        ))
    return results


def _hydrate_quote_hit_authors(hits: list) -> list:
    """Attach per-work authors before deciding whether a hit is quotable."""
    if not hits:
        return hits
    chunk_ids = [hit.chunk_id for hit in hits]
    with SessionLocal() as db:
        author_by_chunk = dict(
            db.query(Chunk.id, Chunk.chunk_author)
            .filter(Chunk.id.in_(chunk_ids))
            .all()
        )
    return [
        replace(hit, chunk_author=author_by_chunk.get(hit.chunk_id))
        for hit in hits
    ]


def _filter_quotable_hits_preserving_verified(
    hits: list,
    query: str,
    *,
    limit: int,
    include_unverified_locators: bool = False,
    include_source_occurrences: bool = False,
) -> list:
    """Keep visually checked page transcriptions ahead of OCR heuristics.

    A large scanned page can contain notes, headers and OCR noise that make the
    carrier chunk fail the generic body-text filter. Once a specific passage
    on that exact page has been visually transcribed, those unrelated OCR
    defects must not hide the verified passage from an exact search.
    """
    if not hits:
        return []
    # Only a query-matching passage review may bypass carrier OCR noise. A
    # fully transcribed cover/index page is source-faithful too, but source
    # fidelity alone does not turn editorial matter into a quotable passage.
    visually_verified_ids = _hit_ids_supported_by_verified_passage(hits, query)
    remaining = [hit for hit in hits if hit.chunk_id not in visually_verified_ids]
    source_occurrences_by_id: dict[int, object] = {}
    if include_source_occurrences:
        public_source_ids = _public_source_chunk_ids(remaining)
        for hit in remaining:
            chunk_id = int(hit.chunk_id)
            source_text = getattr(hit, "text", "") or ""
            if chunk_id not in public_source_ids or not _literal_query_supported(source_text, query):
                continue
            matching_query = _matching_query_variant(source_text, query) or query
            centered_source = _query_centered_excerpt(source_text, matching_query, 700)
            centered_source = re.sub(
                r"\s*Digitized by Google\s*",
                " ",
                centered_source,
                flags=re.IGNORECASE,
            ).strip()
            if not _literal_query_supported(centered_source, query):
                continue
            assessment = assess_content(
                centered_source,
                section=getattr(hit, "chapter_or_section", None),
                author=(getattr(hit, "chunk_author", None) or getattr(hit, "author", None)),
                work_title=getattr(hit, "work_title", None),
                pdf_page=getattr(hit, "pdf_page", None),
            )
            if assessment.role in {
                "toc",
                "bibliography",
                "publisher_ad",
                "digitization_boilerplate",
                "appendix",
                "ocr_noise",
            }:
                continue
            source_occurrences_by_id[chunk_id] = replace(
                hit,
                text=centered_source,
            )
    # The lexical index expands a complete Portuguese theological term to its
    # curated source-language spellings. Apply the same exact alternatives in
    # the body-text gate; otherwise ES can find ``Eucharistia`` but this second
    # pass would discard it for not containing the Portuguese ``Eucaristia``.
    quality_candidates = [
        hit for hit in remaining
        if int(hit.chunk_id) not in source_occurrences_by_id
    ]
    filtered_by_id: dict[int, object] = {}
    for literal_query in _query_literal_variants(query):
        variant_hits = filter_quotable_hits(
            quality_candidates,
            literal_query,
            # Filtering can discard most ES candidates. Inspect the entire
            # bounded candidate window before applying the public result limit.
            limit=min(500, len(quality_candidates)),
            replace_hit=replace,
        )
        for hit in variant_hits:
            filtered_by_id.setdefault(int(hit.chunk_id), hit)
    filtered = list(filtered_by_id.values())
    # When include_unverified_locators is True (patrística searches), allow
    # unverified chunks (PT translations, Patrística EN/LA editions) to appear
    # as readable hits instead of being downgraded to locator-only cards.
    # require_source_verified=True would skip them here, leaving literal_generic_ids
    # empty for those chunks and making Ignatius, Justin etc. invisible.
    source_checked = _enrich_with_db(
        filtered,
        query=query,
        require_source_verified=not include_unverified_locators,
    )
    literal_generic_ids = {
        result.chunk_id
        for result in source_checked
        if _literal_query_supported(result.text, query)
    }
    # Check all curated theological variants (e.g. "Eucaristia" → "Eucharistia")
    # so that Migne Latin/Greek chunks are accepted as locators even when ES
    # returned them via variant expansion but the original query string differs.
    _locator_variants = _query_literal_variants(query) if query else [query]
    _NON_BODY_ROLES = {"toc", "notes", "bibliography", "publisher_ad", "digitization_boilerplate", "appendix"}
    raw_locator_ids = set()
    if include_unverified_locators:
        for hit in remaining:
            raw_text = getattr(hit, "text", "") or ""
            if not any(
                _literal_query_supported(raw_text, v)
                or _literal_query_supported(getattr(hit, "translation_text", "") or "", v)
                for v in _locator_variants
            ):
                continue
            content_ok = assess_content(
                raw_text,
                section=getattr(hit, "chapter_or_section", None),
                author=(getattr(hit, "chunk_author", None) or getattr(hit, "author", None)),
                work_title=getattr(hit, "work_title", None),
                pdf_page=getattr(hit, "pdf_page", None),
            ).role not in _NON_BODY_ROLES
            if content_ok:
                raw_locator_ids.add(int(hit.chunk_id))
    locator_ids = raw_locator_ids & _unverified_ocr_chunk_ids(remaining)
    readable = []
    locators = []
    for hit in hits:
        chunk_id = int(hit.chunk_id)
        if chunk_id in visually_verified_ids:
            readable.append(hit)
        elif chunk_id in source_occurrences_by_id:
            readable.append(source_occurrences_by_id[chunk_id])
        elif chunk_id in literal_generic_ids:
            # Use the complete-sentence excerpt produced by the quality gate,
            # not the original (often very large) carrier chunk.
            readable.append(filtered_by_id[chunk_id])
        elif chunk_id in locator_ids:
            # The OCR excerpt is used only to locate the PDF page. The final
            # enrichment layer blanks unchecked OCR before it reaches the API.
            locators.append(hit)

    # Readable source text must never be pushed below a wall of locator-only
    # cards. This also restores the original search experience on mobile.
    readable = _diversify_hits_by_book(_deduplicate_hits_by_page(readable), limit=limit)
    readable_pages = {_hit_source_page_identity(hit) for hit in readable}
    locators = [
        hit for hit in _deduplicate_hits_by_page(locators)
        if _hit_source_page_identity(hit) not in readable_pages
    ]
    remaining_slots = max(0, limit - len(readable))
    # OCR locators are not diversified by book: the user wants all pages where
    # the term appears, even if many come from the same Migne volume.
    return [
        *readable,
        *locators[:remaining_slots],
    ]


def _public_source_chunk_ids(hits: list) -> set[int]:
    chunk_ids = sorted({int(hit.chunk_id) for hit in hits})
    if not chunk_ids:
        return set()
    with SessionLocal() as db:
        rows = (
            db.query(Chunk.id, Chunk.source_fidelity)
            .filter(Chunk.id.in_(chunk_ids))
            .all()
        )
    return {
        int(row.id)
        for row in rows
        if (row.source_fidelity or "unverified") in PUBLIC_SOURCE_FIDELITIES
    }


def _unverified_ocr_chunk_ids(hits: list) -> set[int]:
    chunk_ids = sorted({int(hit.chunk_id) for hit in hits})
    if not chunk_ids:
        return set()
    with SessionLocal() as db:
        rows = (
            db.query(Chunk.id, Chunk.source_fidelity)
            .filter(Chunk.id.in_(chunk_ids))
            .all()
        )
    return {
        int(row.id)
        for row in rows
        if (row.source_fidelity or "unverified") not in PUBLIC_SOURCE_FIDELITIES
    }


def _diversify_hits_by_book(hits: list, *, limit: int) -> list:
    """Show at least one result from each matching work before repetitions."""
    first_per_book = []
    repeated = []
    seen: set[object] = set()
    for hit in hits:
        key: object = (
            ("book", int(hit.book_id))
            if getattr(hit, "book_id", None) is not None
            else ("chunk", int(hit.chunk_id))
        )
        if key in seen:
            repeated.append(hit)
        else:
            seen.add(key)
            first_per_book.append(hit)
    return (first_per_book + repeated)[:limit]


def _hit_source_page_identity(hit: object) -> tuple:
    page = getattr(hit, "pdf_page", None)
    if page is None:
        return ("chunk", int(getattr(hit, "chunk_id")))
    book_file_id = getattr(hit, "book_file_id", None)
    if book_file_id is not None:
        return ("file", int(book_file_id), "page", int(page))
    book_id = getattr(hit, "book_id", None)
    if book_id is not None:
        return ("book", int(book_id), "page", int(page))
    return ("chunk", int(getattr(hit, "chunk_id")))


def _deduplicate_hits_by_page(hits: list) -> list:
    unique = []
    seen: set[tuple] = set()
    for hit in hits:
        identity = _hit_source_page_identity(hit)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(hit)
    return unique


@dataclass(frozen=True)
class _QuoteScanResult:
    hits: list
    exhausted: bool
    next_offset: int
    candidate_total: int
    matching_works_es: int = 0


def _scan_quotable_source_hits(
    client: TextSearchClient,
    *,
    query: str,
    author_filter: str,
    collection_filter: str,
    patristic_book_ids: list[int],
    start_offset: int = 0,
    max_accepted: int | None = None,
    include_ocr_locators: bool = False,
) -> _QuoteScanResult:
    """Return one stable source-faithful candidate range without locators.

    Elasticsearch ranks before the body-text quality gate. Fetching only one
    small ranked window can therefore leave a single quote after tables of
    contents and editorial matter are rejected. Scan the public-source pages
    in bounded internal batches, apply the quotation gate to every batch, and
    paginate only the compact accepted list returned to the client. The cursor
    advances by consumed Elasticsearch candidates, so later discoveries never
    reorder, duplicate or skip already returned pages.
    """
    accepted: list = []
    scan_offset = max(0, int(start_offset))
    candidate_total: int | None = None
    matching_works_es: int = 0  # from first ES page aggregation
    batch_size = (
        min(_QUOTE_SCAN_BATCH_SIZE, max(1, int(max_accepted)))
        if max_accepted is not None
        else _QUOTE_SCAN_BATCH_SIZE
    )

    while candidate_total is None or scan_offset < candidate_total:
        fetch_size = batch_size
        if max_accepted is not None:
            remaining_slots = max(
                0,
                max(1, int(max_accepted)) - len(_deduplicate_hits_by_page(accepted)),
            )
            if remaining_slots <= 0:
                break
            # One ES candidate can produce at most one public page. Shrinking
            # the final fetch keeps mobile payloads within the requested page
            # size without consuming candidates that would then be dropped.
            fetch_size = min(fetch_size, remaining_slots)
        # When include_ocr_locators is True (patristic searches), we skip the
        # source_fidelity filter so ES also returns unverified OCR chunks from
        # Migne PG/PL/PO. Variant expansion is kept via literal_candidates_only.
        page = client.search_acervo_page(
            query=query,
            limit=fetch_size,
            offset=scan_offset,
            author_filter=author_filter,
            collection_filter=collection_filter,
            patristic_book_ids=patristic_book_ids,
            source_fidelities=None if include_ocr_locators else sorted(PUBLIC_SOURCE_FIDELITIES),
            literal_candidates_only=True,
            raise_on_error=True,
        )
        if candidate_total is None:
            candidate_total = page.total
            matching_works_es = page.matching_works
        batch = list(page.hits)
        if not batch:
            scan_offset = candidate_total
            break

        batch = _hydrate_quote_hit_authors(batch)
        accepted.extend(
            _filter_quotable_hits_preserving_verified(
                batch,
                query,
                limit=len(batch),
                include_source_occurrences=True,
                include_unverified_locators=include_ocr_locators,
            )
        )

        next_offset = scan_offset + page.consumed
        if page.consumed <= 0 or next_offset <= scan_offset:
            scan_offset = candidate_total
            break
        scan_offset = next_offset

        if max_accepted is not None:
            unique_so_far = _deduplicate_hits_by_page(accepted)
            if len(unique_so_far) >= max(1, int(max_accepted)):
                accepted = unique_so_far
                break

    unique = _deduplicate_hits_by_page(accepted)
    exhausted = candidate_total is not None and scan_offset >= candidate_total
    return _QuoteScanResult(
        hits=_diversify_hits_by_book(unique, limit=len(unique)),
        exhausted=exhausted,
        next_offset=scan_offset,
        candidate_total=int(candidate_total or 0),
        matching_works_es=int(matching_works_es or 0),
    )


def _scan_all_quotable_source_hits(
    client: TextSearchClient,
    *,
    query: str,
    author_filter: str,
    collection_filter: str,
    patristic_book_ids: list[int],
) -> list:
    """Compatibility wrapper for audits that intentionally need every hit."""
    return _scan_quotable_source_hits(
        client,
        query=query,
        author_filter=author_filter,
        collection_filter=collection_filter,
        patristic_book_ids=patristic_book_ids,
    ).hits


def _semantic_quotable_source_hits(
    client: TextSearchClient,
    *,
    query: str,
    author_filter: str,
    collection_filter: str,
    patristic_book_ids: list[int],
    limit: int = 120,
) -> list:
    """Return safe multilingual RAG matches for arbitrary user wording.

    The vector index only locates candidates. A result still needs native or
    visually verified source text and must pass the body-content gate before
    any wording reaches the client.
    """
    try:
        hits = client.search_acervo_semantic(
            query=query,
            limit=limit,
            author_filter=author_filter,
            collection_filter=collection_filter,
            patristic_book_ids=patristic_book_ids,
            semantic_min_score=0.36,
            semantic_timeout=5.0,
            raise_on_error=True,
        )
    except Exception as exc:
        _log.warning("Multilingual semantic retrieval unavailable: %s", exc)
        return []

    semantic = _hydrate_quote_hit_authors(hits)
    public_ids = _public_source_chunk_ids(semantic)
    accepted = []
    for hit in semantic:
        if int(hit.chunk_id) not in public_ids:
            continue
        passage = extract_semantic_passage(
            getattr(hit, "text", ""),
            section=getattr(hit, "chapter_or_section", None),
            author=(getattr(hit, "chunk_author", None) or getattr(hit, "author", None)),
            work_title=getattr(hit, "work_title", None),
            pdf_page=getattr(hit, "pdf_page", None),
        )
        if not passage:
            continue
        accepted.append(replace(
            hit,
            text=passage,
            translation_text=None,
            match_type="semantic",
        ))
    unique = _deduplicate_hits_by_page(accepted)
    return _diversify_hits_by_book(unique, limit=min(limit, len(unique)))


def _merge_literal_and_semantic_hits(literal: list, semantic: list) -> list:
    interleaved = []
    width = max(len(literal), len(semantic))
    for index in range(width):
        if index < len(literal):
            interleaved.append(literal[index])
        if index < len(semantic):
            interleaved.append(semantic[index])
    unique = _deduplicate_hits_by_page(interleaved)
    return _diversify_hits_by_book(unique, limit=len(unique))


def _literal_query_supported(text: str | None, query: str | None) -> bool:
    """Require exact wording or a curated whole-query language equivalent."""
    literal_text = _literal_search_key(text)
    variants = _query_literal_variants(query)
    if not literal_text or not variants:
        return False
    for variant in variants:
        literal_query = _literal_search_key(variant)
        if " " in literal_query:
            if literal_query in literal_text:
                return True
        elif re.search(rf"(?<!\w){re.escape(literal_query)}(?!\w)", literal_text) is not None:
            return True
    return False


def _matching_query_variant(text: str | None, query: str | None) -> str | None:
    """Return the exact safe query spelling present in the source text."""
    literal_text = _literal_search_key(text)
    for variant in _query_literal_variants(query):
        literal_variant = _literal_search_key(variant)
        if " " in literal_variant:
            if literal_variant in literal_text:
                return variant
        elif re.search(rf"(?<!\w){re.escape(literal_variant)}(?!\w)", literal_text):
            return variant
    return None


def _literal_search_key(value: str | None) -> str:
    """Fold accents only for matching; displayed source wording is untouched."""
    decomposed = unicodedata.normalize("NFKD", normalize_literal(value).casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _query_literal_variants(query: str | None) -> list[str]:
    """Exact user wording plus explicitly curated whole-query equivalents."""
    original = normalize_literal(query)
    if not original:
        return []
    variants = [original, *theological_literal_variants(original)]
    unique: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        normalized = normalize_literal(variant)
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            unique.append(normalized)
    return unique


def _allow_unverified_pdf_locators(query: str | None) -> bool:
    """Allow OCR-assisted navigation only for a single complete search term.

    A multiword OCR match can make a corrupted phrase appear to be confirmed.
    Single-term discovery is useful for opening all likely PDF pages, while the
    unchecked OCR wording itself remains absent from the public response.
    """
    return len(re.findall(r"[\w\u00c0-\u024f\u0370-\u03ff]+", query or "", re.UNICODE)) == 1


_SEARCH_CURSOR_TTL_SECONDS = 30 * 60


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _search_cursor_context(
    *,
    query: str,
    author: str,
    collection: str,
    quotes_only: bool,
    user_id: object,
) -> dict:
    return {
        "q": query.strip(),
        "author": author,
        "collection": collection,
        "quotes_only": bool(quotes_only),
        "sub": str(user_id),
    }


def _encode_search_cursor(*, offset: int, context: dict, now: int | None = None) -> str:
    payload = {
        "v": 1,
        "offset": max(0, int(offset)),
        "exp": int(now if now is not None else time.time()) + _SEARCH_CURSOR_TTL_SECONDS,
        **context,
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(settings.jwt_secret.encode("utf-8"), serialized, hashlib.sha256).digest()
    return f"{_urlsafe_b64encode(serialized)}.{_urlsafe_b64encode(signature)}"


def _decode_search_cursor(
    token: str,
    *,
    expected_context: dict,
    now: int | None = None,
) -> int:
    try:
        payload_part, signature_part = token.split(".", 1)
        serialized = _urlsafe_b64decode(payload_part)
        supplied_signature = _urlsafe_b64decode(signature_part)
        expected_signature = hmac.new(
            settings.jwt_secret.encode("utf-8"),
            serialized,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("invalid signature")
        payload = json.loads(serialized.decode("utf-8"))
        if payload.get("v") != 1:
            raise ValueError("unsupported cursor version")
        if int(payload.get("exp", 0)) < int(now if now is not None else time.time()):
            raise ValueError("expired cursor")
        for key, expected in expected_context.items():
            if payload.get(key) != expected:
                raise ValueError(f"cursor context mismatch: {key}")
        offset = int(payload.get("offset", -1))
        if offset < 0:
            raise ValueError("invalid offset")
        return offset
    except (TypeError, ValueError, KeyError, json.JSONDecodeError, base64.binascii.Error) as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "A continuação desta busca expirou ou é inválida. Faça a busca novamente.", "code": "SEARCH_CURSOR_INVALID"},
        ) from exc


def _select_verified_passage_for_query(
    displayed_text: str | None,
    query: str | None,
    passages,
) -> VerifiedPassageCandidate | None:
    """Select only a passage supporting the exact query or one safe variant."""
    variants = _query_literal_variants(query)
    if not variants:
        return select_verified_passage(displayed_text, query, passages)
    for variant in variants:
        selected = select_verified_passage(displayed_text, variant, passages)
        if selected is not None:
            return selected
    return None


def _hit_ids_supported_by_verified_passage(hits: list, query: str) -> set[int]:
    if not hits or not query.strip():
        return set()
    hit_by_id = {int(hit.chunk_id): hit for hit in hits}
    with SessionLocal() as db:
        rows = (
            db.query(Chunk.id, Chunk.book_id, Chunk.pdf_page)
            .filter(Chunk.id.in_(hit_by_id))
            .all()
        )
        book_ids = sorted({row.book_id for row in rows})
        pages = sorted({row.pdf_page for row in rows if row.pdf_page is not None})
        passages = (
            db.query(VerifiedPassage)
            .filter(
                VerifiedPassage.book_id.in_(book_ids),
                VerifiedPassage.pdf_page.in_(pages),
            )
            .all()
            if book_ids and pages else []
        )
    passages_by_source: dict[tuple[int, int], list[VerifiedPassageCandidate]] = {}
    for passage in passages:
        passages_by_source.setdefault((passage.book_id, passage.pdf_page), []).append(
            VerifiedPassageCandidate(
                text=passage.text,
                language=passage.language,
                method=passage.verification_method,
            )
        )
    allowed: set[int] = set()
    for row in rows:
        if row.pdf_page is None:
            continue
        hit = hit_by_id.get(int(row.id))
        if hit is None:
            continue
        if _select_verified_passage_for_query(
            getattr(hit, "text", ""),
            query,
            passages_by_source.get((row.book_id, row.pdf_page), ()),
        ) is not None:
            allowed.add(int(row.id))
    return allowed


def _quotable_patristic_results(hits: list, query: str, *, limit: int) -> list[AcervoResult]:
    """Apply the same body-text contract used by the public Fathers search.

    Belonging to a patristic book is not enough: introductions, indexes and
    footnotes inside that book still cannot be presented as a Father's words.
    This helper keeps the Catechism layers on the same strict quotation path.
    """

    hydrated = _hydrate_quote_hit_authors(hits)
    filtered = _filter_quotable_hits_preserving_verified(
        hydrated,
        query,
        limit=limit,
    )
    return _enrich_with_db(
        filtered,
        query=query,
        preexcerpted=True,
        require_source_verified=True,
    )


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def _search_usage_date() -> datetime.date:
    """Current quota date in the timezone advertised to the user."""
    try:
        timezone = ZoneInfo(settings.usage_reset_timezone)
    except ZoneInfoNotFoundError:
        timezone = datetime.timezone.utc
    return datetime.datetime.now(timezone).date()


def _check_and_increment_quota(user: "object") -> datetime.date:
    """Reserve one daily search atomically, returning its local usage date."""
    limit = search_daily_limit_for_plan(getattr(user, "plan", None))
    today = _search_usage_date()
    try:
        with SessionLocal() as db:
            statement = pg_insert(SearchUsage).values(
                user_id=user.id,
                usage_date=today,
                count=1,
            )
            update_kwargs: dict = {
                "set_": {"count": SearchUsage.count + 1},
            }
            if limit is not None:
                update_kwargs["where"] = SearchUsage.count < limit
            statement = statement.on_conflict_do_update(
                index_elements=[SearchUsage.user_id, SearchUsage.usage_date],
                **update_kwargs,
            ).returning(SearchUsage.count)
            new_count = db.execute(statement).scalar_one_or_none()
            if new_count is None:
                used = (
                    db.query(SearchUsage.count)
                    .filter(
                        SearchUsage.user_id == user.id,
                        SearchUsage.usage_date == today,
                    )
                    .scalar()
                    or limit
                    or 0
                )
                db.rollback()
                raise HTTPException(
                    status_code=429,
                    detail={
                        "message": f"Limite diário de {limit} buscas atingido. Renova à meia-noite.",
                        "code": "QUOTA_EXCEEDED",
                        "plan": user.plan,
                        "limit": limit,
                        "used": used,
                    },
                )
            db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"message": "O controle de buscas está temporariamente indisponível.", "code": "QUOTA_UNAVAILABLE"},
        ) from exc
    return today


def _refund_search_quota(user: "object", usage_date: datetime.date) -> None:
    """Return a reserved search when infrastructure fails before a response."""
    try:
        with SessionLocal() as db:
            db.query(SearchUsage).filter(
                SearchUsage.user_id == user.id,
                SearchUsage.usage_date == usage_date,
                SearchUsage.count > 0,
            ).update(
                {SearchUsage.count: SearchUsage.count - 1},
                synchronize_session=False,
            )
            db.commit()
    except Exception:
        # A refund must never replace the original service error.
        return


# ─── Endpoint: uso diário de busca ───────────────────────────────────────────

@router.get("/usage", response_model=SearchUsageResponse)
def get_search_usage(user=Depends(get_current_user)):
    """Retorna o uso diário de buscas do usuário autenticado."""
    limit = search_daily_limit_for_plan(user.plan)
    today = _search_usage_date()
    with SessionLocal() as db:
        usage = db.query(SearchUsage).filter(
            SearchUsage.user_id == user.id,
            SearchUsage.usage_date == today,
        ).first()
        count = usage.count if usage else 0
    remaining = (limit - count) if limit is not None else None
    return SearchUsageResponse(plan=user.plan, limit=limit, used=count, remaining=remaining)


# ─── Endpoint 1: busca no conteúdo do acervo ─────────────────────────────────

def _effective_collection_filter(collection: str, *, quotes_only: bool) -> str:
    if not quotes_only:
        return collection
    return "" if collection.casefold() == "all" else "patristica"


@router.get("/chunks", response_model=AcervoSearchResponse)
def search_chunks(
    q: str = Query(..., min_length=2, max_length=300, description="Termo ou frase a buscar"),
    limit: int = Query(default=36, ge=1, le=500),
    author: str = Query(default="", description="Filtrar por autor (keyword exato do ES)"),
    collection: str = Query(
        default="",
        description="'patristica' para os Padres; 'all' para citações de todo o acervo",
    ),
    include_patristic: bool = Query(default=False, description="Incluir uma lista patrística aprofundada"),
    patristic_limit: int = Query(default=500, ge=1, le=500),
    quotes_only: bool = Query(
        default=False,
        description="Retornar somente passagens citáveis do corpo das obras",
    ),
    cursor: str = Query(
        default="",
        max_length=2048,
        description="Cursor assinado retornado pela página anterior",
    ),
    user=Depends(get_optional_user),
):
    """Busca semântica/textual dentro dos trechos indexados do acervo.

    ``quotes_only`` descarta índices/notas/material editorial e devolve
    passagens completas, prontas para conferência no PDF. Por compatibilidade,
    o escopo padrão continua patrístico; ``collection=all`` aplica o mesmo
    contrato de fidelidade a todas as obras do acervo.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")
    # Patrística searches include OCR locators and can legitimately return
    # many results per term (e.g. "Eucharistia" across 37k Migne chunks).
    patristic_collection = _effective_collection_filter(collection, quotes_only=True) == "patristica"
    max_quotes_limit = 500 if patristic_collection else 100
    if quotes_only and limit > max_quotes_limit:
        raise HTTPException(
            status_code=422,
            detail=f"A busca paginada de citações aceita no máximo {max_quotes_limit} páginas por requisição.",
        )
    effective_collection = _effective_collection_filter(collection, quotes_only=quotes_only)
    cursor_context = _search_cursor_context(
        query=q,
        author=author,
        collection=effective_collection,
        quotes_only=quotes_only,
        user_id=user.id,
    )
    if cursor and not quotes_only:
        raise HTTPException(
            status_code=422,
            detail={"message": "Este cursor pertence à busca paginada de citações.", "code": "SEARCH_CURSOR_INVALID"},
        )
    page_offset = (
        _decode_search_cursor(cursor, expected_context=cursor_context)
        if cursor else 0
    )
    # Loading another page is the continuation of the same signed search, not
    # a new daily-quota event. The signature binds it to this user and query.
    usage_date = None if cursor else _check_and_increment_quota(user)
    patristic_ids = _get_patristic_book_ids()
    total = 0
    matching_works = 0
    readable_total = 0
    has_more = False
    next_cursor = None
    total_matching_pages: int = 0
    total_matching_works: int = 0
    try:
        client = _client()
        if quotes_only:
            # For patristica, include all patristic OCR chunks (Migne PG/PL/PO
            # and unverified PT/EN editions) so the full corpus is searchable.
            # Multi-word queries also get OCR locators since phrase matching is
            # exact enough to avoid false positives from corrupted OCR.
            include_ocr = effective_collection == "patristica"
            literal_scan = _scan_quotable_source_hits(
                client,
                query=q,
                author_filter=author,
                collection_filter=effective_collection,
                patristic_book_ids=patristic_ids,
                start_offset=page_offset,
                max_accepted=limit,
                include_ocr_locators=include_ocr,
            )
            quotable_hits = literal_scan.hits
            # Semantic RAG is a fallback for natural-language phrases with no
            # literal occurrence. Never pad a real word/quotation result with
            # merely related passages: that made rare searches look wrong.
            query_word_count = len(re.findall(
                r"[\w\u00c0-\u024f\u0370-\u03ff]+",
                q or "",
                re.UNICODE,
            ))
            if (
                not cursor
                and literal_scan.exhausted
                and not quotable_hits
                and query_word_count >= 2
            ):
                semantic_hits = _semantic_quotable_source_hits(
                    client,
                    query=q,
                    author_filter=author,
                    collection_filter=effective_collection,
                    patristic_book_ids=patristic_ids,
                    limit=max(limit + 8, 32),
                )
                quotable_hits = _merge_literal_and_semantic_hits(quotable_hits, semantic_hits)
            readable_total = len(quotable_hits) + (0 if literal_scan.exhausted else 1)
            total = readable_total
            # ES-level totals: how many pages and works matched the query across
            # the full corpus, before the content quality gate is applied.
            total_matching_pages = literal_scan.candidate_total
            total_matching_works = literal_scan.matching_works_es
            matching_works = len({
                ("book", int(hit.book_id))
                if getattr(hit, "book_id", None) is not None
                else ("chunk", int(hit.chunk_id))
                for hit in quotable_hits
            })
            hits = quotable_hits
            next_offset = literal_scan.next_offset
            has_more = not literal_scan.exhausted
            if has_more:
                next_cursor = _encode_search_cursor(
                    offset=next_offset,
                    context=cursor_context,
                )
        else:
            candidate_limit = limit
            hits = client.search_acervo_hybrid(
                query=q,
                limit=candidate_limit,
                author_filter=author,
                collection_filter=effective_collection,
                patristic_book_ids=patristic_ids,
                raise_on_error=True,
            )
        patristic_hits = []
        if include_patristic and not effective_collection:
            # One user action, one semantic encoding: the deep list reuses the
            # lexical engine and receives semantic patristic hits from the
            # already-computed general result below.
            lexical_patristic_hits = client.search_acervo(
                query=q,
                limit=patristic_limit,
                author_filter=author,
                collection_filter="patristica",
                patristic_book_ids=patristic_ids,
                raise_on_error=True,
            )
            patristic_collections = set(PATRISTIC_COLLECTIONS)
            allowed_book_ids = set(patristic_ids)
            # Keep semantic-only patristic candidates even when the lexical
            # branch already fills all 500 slots.
            semantic_patristic_hits = [
                hit
                for hit in hits
                if (hit.collection or "") in patristic_collections or hit.book_id in allowed_book_ids
            ]
            patristic_hits = list(semantic_patristic_hits)
            seen = {hit.chunk_id for hit in patristic_hits}
            for hit in lexical_patristic_hits:
                if hit.chunk_id not in seen:
                    patristic_hits.append(hit)
                    seen.add(hit.chunk_id)
        # Public search never presents unchecked OCR as if it were the literal
        # wording of the edition. OCR remains an internal discovery aid only.
        # Exception: for patristic searches, OCR chunks surface as page-locator
        # cards (via include_ocr_locators) with a short highlighted excerpt and
        # a clear "texto OCR" warning. require_source_verified=False lets them
        # through; _enrich_with_db still blanks text for truly empty hits.
        require_sv = effective_collection != "patristica"
        results = _enrich_with_db(
            hits,
            query=q,
            preexcerpted=quotes_only,
            require_source_verified=require_sv,
        )
        patristic_results = _enrich_with_db(
            patristic_hits[:patristic_limit],
            query=q,
            require_source_verified=True,
        )
    except Exception as exc:
        if usage_date is not None:
            _refund_search_quota(user, usage_date)
        raise HTTPException(
            status_code=503,
            detail={"message": "A busca no acervo está temporariamente indisponível.", "code": "SEARCH_UNAVAILABLE"},
        ) from exc
    _variants = theological_literal_variants(q) if q else []
    expanded = [q, *_variants] if q else []
    return AcervoSearchResponse(
        results=results,
        total=total if quotes_only else len(results),
        query=q,
        patristic_results=patristic_results,
        returned=len(results),
        readable_total=readable_total,
        matching_works=matching_works,
        has_more=has_more,
        next_cursor=next_cursor,
        total_matching_pages=total_matching_pages,
        total_matching_works=total_matching_works,
        expanded_terms=expanded[:10],
    )


# ─── Endpoint 2: citação do dia por autor ────────────────────────────────────

@router.get("/daily-citation", response_model=DailyCitationResponse)
def daily_citation(
    author: str = Query(..., min_length=2, max_length=200, description="Nome do autor (keyword do ES)"),
):
    """Retorna um trecho do autor escolhido deterministicamente pelo dia do ano."""
    day = datetime.date.today().timetuple().tm_yday
    hits = _client().author_chunks(author=author, limit=500)

    # Preferir trechos com tradução PT e texto substancial
    candidates = [
        h for h in hits
        if (h.translation_text or "").strip() and len((h.translation_text or "").strip()) >= 80
    ]
    if not candidates:
        candidates = [h for h in hits if len((h.text or "").strip()) >= 80]
    if not candidates:
        candidates = hits

    if not candidates:
        return DailyCitationResponse(
            chunk_id=None, text=None, author=author, work_title=None,
            pdf_page=None, chapter_or_section=None, edition_label=None,
            language=None, translation_text=None, book_id=None,
            book_file_id=None, day_of_year=day,
        )

    # Pick the daily passage only after the source-fidelity gate. Otherwise a
    # deterministic selection could still publish a different OCR corruption
    # every day.
    enriched = _enrich_with_db(candidates, require_source_verified=True)
    if not enriched:
        return DailyCitationResponse(
            chunk_id=None, text=None, author=author, work_title=None,
            pdf_page=None, chapter_or_section=None, edition_label=None,
            language=None, translation_text=None, book_id=None,
            book_file_id=None, day_of_year=day,
        )

    e = enriched[day % len(enriched)]

    return DailyCitationResponse(
        chunk_id=e.chunk_id,
        text=e.text,
        author=e.chunk_author or e.author,
        work_title=e.work_title,
        pdf_page=e.pdf_page,
        chapter_or_section=e.chapter_or_section,
        edition_label=e.edition_label,
        language=e.language,
        translation_text=e.translation_text,
        book_id=e.book_id,
        book_file_id=e.book_file_id,
        day_of_year=day,
        source_fidelity=e.source_fidelity,
        source_fidelity_label=e.source_fidelity_label,
    )


# ─── Endpoint 3: Catena Patrum — busca por referência bíblica ────────────────

# Abreviaturas dos livros bíblicos em português e latim
_BIBLE_ALIASES: dict[str, list[str]] = {
    "Gênesis": ["Gen", "Gn", "Genesis"],
    "Êxodo": ["Ex", "Exo", "Exodus"],
    "Levítico": ["Lv", "Lev", "Leviticus"],
    "Números": ["Nm", "Num", "Numeri"],
    "Deuteronômio": ["Dt", "Deu", "Deuteronomium"],
    "Josué": ["Jos", "Josh", "Iosue"],
    "Juízes": ["Jz", "Jg", "Judices"],
    "Rute": ["Rt", "Ruth"],
    "1 Samuel": ["1Sm", "1Sam", "1 Sm", "I Sam", "I Sm"],
    "2 Samuel": ["2Sm", "2Sam", "2 Sm", "II Sam"],
    "1 Reis": ["1Rs", "1Re", "1 Rs", "I Reg"],
    "2 Reis": ["2Rs", "2Re", "2 Rs", "II Reg"],
    "1 Crônicas": ["1Cr", "1Chr", "I Par"],
    "2 Crônicas": ["2Cr", "2Chr", "II Par"],
    "Esdras": ["Esd", "Ezr"],
    "Neemias": ["Ne", "Neh", "Neem"],
    "Ester": ["Est", "Esth"],
    "Jó": ["Jó", "Job"],
    "Salmos": ["Sl", "Ps", "Salm", "Psalm", "Sal"],
    "Provérbios": ["Pr", "Pro", "Prov"],
    "Eclesiastes": ["Ec", "Ecl", "Qo", "Eccl"],
    "Cântico dos Cânticos": ["Ct", "Cant", "Cant"],
    "Sabedoria": ["Sb", "Sap", "Wis"],
    "Eclesiástico": ["Sir", "Eclo", "Eccli"],
    "Isaías": ["Is", "Isa"],
    "Jeremias": ["Jr", "Jer"],
    "Lamentações": ["Lm", "Lam"],
    "Baruc": ["Bar", "Baruch"],
    "Ezequiel": ["Ez", "Ezek"],
    "Daniel": ["Dn", "Dan"],
    "Oseias": ["Os", "Hos"],
    "Joel": ["Jl", "Joel"],
    "Amós": ["Am", "Amos"],
    "Abdias": ["Ab", "Obad"],
    "Jonas": ["Jn", "Jon"],
    "Miquéias": ["Mq", "Mic"],
    "Naum": ["Na", "Nah"],
    "Habacuc": ["Hab"],
    "Sofonias": ["Sf", "Zep"],
    "Ageu": ["Ag", "Hag"],
    "Zacarias": ["Zc", "Zec"],
    "Malaquias": ["Ml", "Mal"],
    "1 Macabeus": ["1Mac", "1Mc", "I Macc"],
    "2 Macabeus": ["2Mac", "2Mc", "II Macc"],
    "Mateus": ["Mt", "Mat", "Matth"],
    "Marcos": ["Mc", "Mr", "Mk", "Marc"],
    "Lucas": ["Lc", "Lk", "Luc"],
    "João": ["Jo", "Jn", "Jão", "Ioh", "Ioan"],
    "Atos": ["At", "Atos dos Apóstolos", "Act", "Acts"],
    "Romanos": ["Rm", "Rom", "Ro"],
    "1 Coríntios": ["1Cor", "1Co", "I Cor"],
    "2 Coríntios": ["2Cor", "2Co", "II Cor"],
    "Gálatas": ["Gl", "Gal", "Ga"],
    "Efésios": ["Ef", "Eph", "Ep"],
    "Filipenses": ["Fp", "Fil", "Phil"],
    "Colossenses": ["Cl", "Col"],
    "1 Tessalonicenses": ["1Ts", "1Tess", "I Thess"],
    "2 Tessalonicenses": ["2Ts", "2Tess", "II Thess"],
    "1 Timóteo": ["1Tm", "1Tim", "I Tim"],
    "2 Timóteo": ["2Tm", "2Tim", "II Tim"],
    "Tito": ["Tt", "Tit"],
    "Filemon": ["Fm", "Phm", "Philem"],
    "Hebreus": ["Hb", "Heb"],
    "Tiago": ["Tg", "Jac", "Jas"],
    "1 Pedro": ["1Pd", "1Pe", "I Pet"],
    "2 Pedro": ["2Pd", "2Pe", "II Pet"],
    "1 João": ["1Jo", "1Jn", "I Ioan"],
    "2 João": ["2Jo", "2Jn", "II Ioan"],
    "3 João": ["3Jo", "3Jn", "III Ioan"],
    "Judas": ["Jd", "Jud"],
    "Apocalipse": ["Ap", "Apo", "Rev", "Apoc"],
}

_ABBR_TO_FULL: dict[str, str] = {}
for _full, _abbrs in _BIBLE_ALIASES.items():
    _ABBR_TO_FULL[_norm(_full)] = _full
    for _abbr in _abbrs:
        _ABBR_TO_FULL[_norm(_abbr)] = _full


def _normalize_bible_ref(ref: str) -> tuple[str, str, str]:
    """
    Parse 'Jo 6,53' or 'João 6:53' or '1Cor 13,4-7' into (book_full, chapter, verse).
    Returns ('', '', '') on failure.
    """
    ref = ref.strip()
    # Extrai número do livro + nome + capítulo:versículo
    m = re.match(
        r'^(\d?\s*[A-ZÀ-Ü][a-zà-ü]+(?:\s+[A-ZÀ-Ü][a-zà-ü]+)*)\s+(\d+)[,:\.](\d+(?:[–\-]\d+)?)$',
        ref.strip(),
        re.UNICODE,
    )
    if not m:
        # Tenta sem versículo: "Jo 6"
        m2 = re.match(r'^(\d?\s*[A-ZÀ-Ü][a-zà-ü]+(?:\s+[A-ZÀ-Ü][a-zà-ü]+)*)\s+(\d+)$', ref, re.UNICODE)
        if m2:
            book_raw, chapter = m2.group(1), m2.group(2)
            verse = ""
        else:
            return ("", "", "")
    else:
        book_raw, chapter, verse = m.group(1), m.group(2), m.group(3)

    book_full = _ABBR_TO_FULL.get(_norm(book_raw), book_raw)
    return (book_full, chapter, verse)


def _bible_search_variants(ref: str) -> list[str]:
    """Return alternative text forms to search for a Bible reference."""
    book_full, chapter, verse = _normalize_bible_ref(ref)
    if not book_full:
        return [ref]

    # All abbreviations for this book
    abbrs = [book_full] + _BIBLE_ALIASES.get(book_full, [])
    variants: list[str] = []
    seps = [",", ":", "."]
    for abbr in abbrs[:6]:
        for sep in seps:
            if verse:
                variants.append(f"{abbr} {chapter}{sep}{verse}")
                variants.append(f"{abbr} {chapter}{sep}{verse.split('-')[0]}")
            else:
                variants.append(f"{abbr} {chapter}")
    return list(dict.fromkeys(variants))[:12]


@router.get("/bible", response_model=AcervoSearchResponse)
def catena_patrum(
    ref: str = Query(..., min_length=3, max_length=80, description="Referência bíblica, ex: Jo 6,53 ou Mt 5,3"),
    limit: int = Query(default=20, ge=1, le=50),
    user=Depends(get_optional_user),
):
    """
    Catena Patrum: busca o que os Padres da Igreja escreveram sobre um versículo bíblico.
    Busca as variantes da referência no texto e tradução dos chunks indexados.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")
    try:
        # Reject malformed references before reserving quota.
        parse_bible_reference(ref)
    except BibleReferenceError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "code": exc.code},
        ) from exc

    usage_date = _check_and_increment_quota(user)
    try:
        with SessionLocal() as db:
            patristic_ids = [
                row.id
                for row in db.query(Book.id).filter(
                    (Book.library_section == "patristica")
                    | Book.patristic_tradition.isnot(None)
                    | Book.collection.in_(["PL", "PG", "PO", "PT"])
                ).all()
            ]
            catena_ids = [
                row.id
                for row in db.query(Book.id).filter(Book.title.ilike("%Catena Aurea%")).all()
            ]
        search_result = search_catena(
            _client().es,
            ref,
            patristic_ids,
            catena_book_ids=catena_ids,
            limit=limit,
        )
    except Exception as exc:
        _refund_search_quota(user, usage_date)
        raise HTTPException(
            status_code=503,
            detail={"message": "A Catena está temporariamente indisponível.", "code": "CATENA_UNAVAILABLE"},
        ) from exc

    from search.text_search import AcervoSearchHit

    try:
        raw_hits = [
            AcervoSearchHit(
                chunk_id=hit.chunk_id,
                score=hit.score,
                text=hit.excerpt,
                author=hit.author or "",
                work_title=hit.work_title or "",
                pdf_page=hit.pdf_page,
                chapter_or_section=hit.chapter_or_section,
                collection=hit.collection,
                volume=hit.volume,
                edition_label=hit.edition_label,
                language=hit.language,
                translation_text=None,
                book_id=hit.book_id,
            )
            for hit in search_result.hits
        ]
        results = _enrich_with_db(
            raw_hits,
            query=search_result.reference.canonical,
            require_source_verified=True,
        )
    except Exception as exc:
        _refund_search_quota(user, usage_date)
        raise HTTPException(
            status_code=503,
            detail={"message": "A Catena está temporariamente indisponível.", "code": "CATENA_UNAVAILABLE"},
        ) from exc
    return AcervoSearchResponse(
        results=results,
        total=len(results),
        query=search_result.reference.canonical,
    )


# ─── Endpoint 4: chunks de um livro para leitura offline ─────────────────────

class OfflineChunk(BaseModel):
    chunk_id: int
    sequence_index: int | None
    chapter_or_section: str | None
    text: str
    translation_pt: str | None
    pdf_page: int | None
    volume: int | None
    source_fidelity: str
    source_fidelity_label: str


class OfflineBookResponse(BaseModel):
    book_id: int
    title: str
    author: str | None
    edition_label: str | None
    language: str | None
    chunks: list[OfflineChunk]
    total_chunks: int


@router.get("/book-chunks", response_model=OfflineBookResponse)
def book_chunks_offline(
    book_id: int = Query(..., description="ID do livro"),
    limit: int = Query(default=400, ge=1, le=600),
):
    """
    Retorna os trechos de texto extraídos de um livro para leitura offline.
    Retorna apenas texto já indexado — nunca o arquivo PDF original.
    """
    with SessionLocal() as db:
        book = db.get(Book, book_id)
        if not book:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Livro não encontrado.")

        chunks = (
            db.query(Chunk)
            .filter(
                Chunk.book_id == book_id,
                Chunk.source_fidelity.in_(PUBLIC_SOURCE_FIDELITIES),
            )
            .order_by(Chunk.sequence_index.nulls_last(), Chunk.id)
            .limit(limit)
            .all()
        )

        # A scanned page can still be available offline when a literal
        # transcription has been checked against that exact PDF page. Use a
        # chunk from the same page only as its stable carrier/locator; never
        # return the carrier's OCR wording.
        verified_rows = (
            db.query(VerifiedPassage)
            .filter(VerifiedPassage.book_id == book_id)
            .order_by(VerifiedPassage.pdf_page, VerifiedPassage.id)
            .all()
        )
        verified_pages = {row.pdf_page for row in verified_rows}
        carrier_rows = (
            db.query(Chunk)
            .filter(
                Chunk.book_id == book_id,
                Chunk.pdf_page.in_(verified_pages),
            )
            .order_by(Chunk.sequence_index.nulls_last(), Chunk.id)
            .all()
            if verified_pages else []
        )
        carrier_by_page: dict[int, Chunk] = {}
        for carrier in carrier_rows:
            carrier_by_page.setdefault(carrier.pdf_page, carrier)

        result_chunks = [
            OfflineChunk(
                chunk_id=c.id,
                sequence_index=c.sequence_index,
                chapter_or_section=c.chapter_or_section or None,
                text=c.text[:1200],
                translation_pt=None,
                pdf_page=c.pdf_page,
                volume=c.volume,
                source_fidelity="source_text",
                source_fidelity_label="Texto nativo da edição indexada",
            )
            for c in chunks
        ]
        for passage in verified_rows:
            carrier = carrier_by_page.get(passage.pdf_page)
            if carrier is None:
                continue
            result_chunks.append(OfflineChunk(
                chunk_id=carrier.id,
                sequence_index=carrier.sequence_index,
                chapter_or_section=carrier.chapter_or_section or None,
                text=passage.text,
                translation_pt=None,
                pdf_page=passage.pdf_page,
                volume=carrier.volume,
                source_fidelity="verified_transcription",
                source_fidelity_label="Transcrição conferida com a página do PDF",
            ))
        result_chunks.sort(key=lambda item: (
            item.sequence_index if item.sequence_index is not None else 2**31,
            item.chunk_id,
        ))
        result_chunks = result_chunks[:limit]

    return OfflineBookResponse(
        book_id=book_id,
        title=book.title,
        author=book.canonical_author or book.author or None,
        edition_label=book.edition_label or None,
        language=book.language or None,
        chunks=result_chunks,
        total_chunks=len(result_chunks),
    )


# ─── Endpoint 5: comentário patrístico por parágrafo do Catecismo ────────────

class CccCommentaryResponse(BaseModel):
    article: int
    section_title: str
    themes: list[str]
    results: list[AcervoResult]
    total: int
    article_text: str | None = None
    source_pages: list[int] = Field(default_factory=list)
    mode: str = "exact_article"
    warning: str | None = None


class CatechismSourceRefResponse(BaseModel):
    book_id: int
    book_file_id: int | None = None
    chunk_ids: list[int] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)
    edition_label: str | None = None
    language: str | None = None


class CatechismPassageResponse(BaseModel):
    catechism: str
    source_title: str
    source_author: str | None = None
    locator: str
    section_title: str | None = None
    text: str
    source: CatechismSourceRefResponse
    verification: str = "indexed_edition"
    text_fingerprint: str


class CatechismMatchResponse(BaseModel):
    kind: str
    confidence: str
    evidence_terms: list[str] = Field(default_factory=list)


class CatechismComparisonResponse(BaseModel):
    status: str
    source: str
    source_title: str
    message: str | None = None
    passage: CatechismPassageResponse | None = None
    match: CatechismMatchResponse | None = None


class CatechismQueryResponse(BaseModel):
    kind: str = "ccc_paragraph"
    article: int


class PatristicRootsResponse(BaseModel):
    results: list[AcervoResult] = Field(default_factory=list)
    total: int = 0


class CatechismNoticeResponse(BaseModel):
    scope: str
    code: str
    message: str


class CatechismConcordanceResponse(BaseModel):
    query: CatechismQueryResponse
    anchor: CatechismPassageResponse
    themes: list[str] = Field(default_factory=list)
    comparisons: list[CatechismComparisonResponse] = Field(default_factory=list)
    patristic_roots: PatristicRootsResponse
    notices: list[CatechismNoticeResponse] = Field(default_factory=list)


def _passage_response(passage: CatechismPassage) -> CatechismPassageResponse:
    return CatechismPassageResponse(
        catechism=passage.catechism,
        source_title=passage.source_title,
        source_author=passage.source_author,
        locator=passage.locator,
        section_title=passage.section_title,
        text=passage.text,
        source=CatechismSourceRefResponse(
            book_id=passage.source.book_id,
            book_file_id=passage.source.book_file_id,
            chunk_ids=list(passage.source.chunk_ids),
            pages=list(passage.source.pages),
            edition_label=passage.source.edition_label,
            language=passage.source.language,
        ),
        text_fingerprint=passage.text_fingerprint,
    )


def _ccc_anchor_response(context) -> CatechismPassageResponse:
    if not context.is_exact or not context.article_text or context.source_book_id is None:
        raise ValueError("exact CCC source unavailable")
    with SessionLocal() as db:
        book = db.get(Book, context.source_book_id)
        if book is None:
            raise ValueError("CCC source book unavailable")
        chunks = (
            db.query(Chunk)
            .filter(Chunk.id.in_(list(context.source_chunk_ids)))
            .order_by(Chunk.sequence_index.nulls_last(), Chunk.id)
            .all()
        )
        file_id = next(
            (chunk.book_file_id for chunk in chunks if chunk.book_file_id is not None),
            None,
        )
        if file_id is None:
            file_row = (
                db.query(BookFile)
                .filter(BookFile.book_id == book.id)
                .order_by(BookFile.id)
                .first()
            )
            file_id = file_row.id if file_row is not None else None

        return CatechismPassageResponse(
            catechism="ccc",
            source_title=book.title,
            source_author=book.canonical_author or book.author or None,
            locator=f"§ {context.article}",
            section_title=context.section_title,
            text=context.article_text,
            source=CatechismSourceRefResponse(
                book_id=book.id,
                book_file_id=file_id,
                chunk_ids=list(context.source_chunk_ids),
                pages=list(context.source_pages),
                edition_label=book.edition_label or None,
                language=book.language or None,
            ),
            text_fingerprint=context.article_fingerprint or "",
        )


@router.get("/ccc-commentary", response_model=CccCommentaryResponse)
def ccc_commentary(
    article: int = Query(..., ge=1, le=2865, description="Número do parágrafo do CCC (1–2865)"),
    limit: int = Query(default=12, ge=1, le=30),
    user=Depends(get_optional_user),
):
    """
    Retorna trechos patrísticos relacionados ao texto exato de um parágrafo do
    Catecismo da Igreja Católica, com filtro autoritativo das fontes.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")
    usage_date = _check_and_increment_quota(user)
    try:
        # Over-fetch because the structural quotation filter below may reject
        # editorial chunks that passed the book-level patristic allow-list.
        candidate_limit = min(30, max(limit * 3, limit))
        outcome = _ccc_commentary_service().search(article, limit=candidate_limit)
    except Exception as exc:
        _refund_search_quota(user, usage_date)
        raise HTTPException(
            status_code=503,
            detail={"message": "O comentário do Catecismo está temporariamente indisponível.", "code": "CCC_UNAVAILABLE"},
        ) from exc
    if outcome.warning and not outcome.hits:
        _refund_search_quota(user, usage_date)
    context = outcome.context
    try:
        results = _quotable_patristic_results(
            list(outcome.hits),
            context.query,
            limit=limit,
        )
    except Exception as exc:
        if not (outcome.warning and not outcome.hits):
            _refund_search_quota(user, usage_date)
        raise HTTPException(
            status_code=503,
            detail={"message": "O comentário do Catecismo está temporariamente indisponível.", "code": "CCC_UNAVAILABLE"},
        ) from exc

    return CccCommentaryResponse(
        article=article,
        section_title=context.section_title,
        themes=list(context.key_terms[:8]),
        results=results,
        total=len(results),
        article_text=context.article_text,
        source_pages=list(context.source_pages),
        mode=context.mode.value,
        warning=outcome.warning,
    )


@router.get("/catechism-concordance", response_model=CatechismConcordanceResponse)
def catechism_concordance(
    article: int = Query(..., ge=1, le=2865, description="Número do parágrafo do CCC (1–2865)"),
    patristic_limit: int = Query(default=8, ge=1, le=12),
    user=Depends(get_optional_user),
):
    """Return one verified, three-layer Catechism reading experience.

    Layer 1 is the exact CCC paragraph. Layer 2 keeps every other catechism's
    own locator and distinguishes explicit references from thematic matches.
    Layer 3 contains only body-text quotations from patristic works.
    """

    if user is None:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")
    usage_date = _check_and_increment_quota(user)
    base_service = _ccc_commentary_service()
    try:
        context = base_service.build_context(article)
        if not context.is_exact or not context.article_text:
            raise ValueError("CCC_SOURCE_UNAVAILABLE")
        anchor = _ccc_anchor_response(context)
        comparisons = _catechism_concordance_service().find_comparisons(context)
    except Exception as exc:
        _refund_search_quota(user, usage_date)
        raise HTTPException(
            status_code=503,
            detail={
                "message": "O texto exato deste parágrafo está temporariamente indisponível.",
                "code": "CATECHISM_CONCORDANCE_UNAVAILABLE",
            },
        ) from exc

    notices: list[CatechismNoticeResponse] = []
    roots: list[AcervoResult] = []
    try:
        # Search the maximum service window, then let the quotation-quality
        # gate select the smaller public result set.
        root_outcome = base_service.search(article, limit=30)
        roots = _quotable_patristic_results(
            list(root_outcome.hits),
            context.query,
            limit=patristic_limit,
        )
        if root_outcome.warning:
            notices.append(
                CatechismNoticeResponse(
                    scope="patristic",
                    code="PATRISTIC_SEARCH_PARTIAL",
                    message=root_outcome.warning,
                )
            )
        elif not roots:
            notices.append(
                CatechismNoticeResponse(
                    scope="patristic",
                    code="NO_SAFE_PATRISTIC_ROOTS",
                    message=(
                        "Nenhuma passagem patrística superou os filtros de autoria e qualidade; "
                        "resultados aproximados foram omitidos."
                    ),
                )
            )
    except Exception:
        # The exact paragraph and catechism comparisons remain useful and
        # verified even when Elasticsearch/semantic search is unavailable.
        notices.append(
            CatechismNoticeResponse(
                scope="patristic",
                code="PATRISTIC_SEARCH_UNAVAILABLE",
                message="As raízes patrísticas estão temporariamente indisponíveis.",
            )
        )

    comparison_responses = [
        CatechismComparisonResponse(
            status=comparison.status,
            source=comparison.source,
            source_title=comparison.source_title,
            message=comparison.message,
            passage=(
                _passage_response(comparison.passage)
                if comparison.passage is not None
                else None
            ),
            match=(
                CatechismMatchResponse(
                    kind=comparison.match.kind,
                    confidence=comparison.match.confidence,
                    evidence_terms=list(comparison.match.evidence_terms),
                )
                if comparison.match is not None
                else None
            ),
        )
        for comparison in comparisons
    ]
    return CatechismConcordanceResponse(
        query=CatechismQueryResponse(article=article),
        anchor=anchor,
        themes=list(context.key_terms[:8]),
        comparisons=comparison_responses,
        patristic_roots=PatristicRootsResponse(results=roots, total=len(roots)),
        notices=notices,
    )
