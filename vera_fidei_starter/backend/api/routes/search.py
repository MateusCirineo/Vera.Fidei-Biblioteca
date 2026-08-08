from __future__ import annotations

import datetime
import re
import time
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.auth import require_api_key
from core.deps import get_current_user, get_optional_user
from core.plans import search_daily_limit_for_plan
from data.ccc_structure import find_ccc_section
from models.database import Book, Chunk, SearchUsage, SessionLocal, Translation
from search.text_search import TextSearchClient

router = APIRouter()

_text_client: TextSearchClient | None = None

# Cache of patristic book IDs (refreshed every hour)
_patristic_ids_cache: list[int] = []
_patristic_ids_ts: float = 0.0
_PATRISTIC_CACHE_TTL = 3600.0


def _client() -> TextSearchClient:
    global _text_client
    if _text_client is None:
        _text_client = TextSearchClient()
    return _text_client


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


class AcervoSearchResponse(BaseModel):
    results: list[AcervoResult]
    total: int
    query: str


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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _enrich_with_db(hits: list) -> list[AcervoResult]:
    """Add book_id / book_file_id / chunk_author / library_section / patristic_tradition from Postgres."""
    if not hits:
        return []
    chunk_ids = [h.chunk_id for h in hits]
    with SessionLocal() as db:
        rows = (
            db.query(Chunk.id, Chunk.book_id, Chunk.book_file_id, Chunk.chunk_author,
                     Book.library_section, Book.patristic_tradition)
            .join(Book, Chunk.book_id == Book.id, isouter=True)
            .filter(Chunk.id.in_(chunk_ids))
            .all()
        )
    meta = {
        r.id: {
            "book_id": r.book_id,
            "book_file_id": r.book_file_id,
            "chunk_author": r.chunk_author,
            "library_section": r.library_section,
            "patristic_tradition": r.patristic_tradition,
        }
        for r in rows
    }
    results = []
    for hit in hits:
        m = meta.get(hit.chunk_id, {})
        results.append(AcervoResult(
            chunk_id=hit.chunk_id,
            text=(hit.text or "")[:700],
            author=hit.author or None,
            chunk_author=m.get("chunk_author") or None,
            work_title=hit.work_title or None,
            pdf_page=hit.pdf_page,
            chapter_or_section=hit.chapter_or_section or None,
            collection=hit.collection or None,
            volume=hit.volume,
            edition_label=hit.edition_label or None,
            language=hit.language or None,
            translation_text=(hit.translation_text or "")[:450] or None,
            relevance_score=round(hit.score, 3),
            book_id=m.get("book_id"),
            book_file_id=m.get("book_file_id"),
            library_section=m.get("library_section"),
            patristic_tradition=m.get("patristic_tradition"),
        ))
    return results


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def _check_and_increment_quota(user: "object", skip: bool = False) -> None:
    """Check daily search quota and increment counter. Raises 429 if exceeded."""
    if skip:
        return
    limit = search_daily_limit_for_plan(getattr(user, "plan", None))
    today = datetime.date.today()
    with SessionLocal() as db:
        usage = db.query(SearchUsage).filter(
            SearchUsage.user_id == user.id,
            SearchUsage.usage_date == today,
        ).first()
        if usage is None:
            usage = SearchUsage(user_id=user.id, usage_date=today, count=0)
            db.add(usage)
            db.flush()
        if limit is not None and usage.count >= limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "message": f"Limite diário de {limit} buscas atingido. Renova à meia-noite.",
                    "code": "QUOTA_EXCEEDED",
                    "plan": user.plan,
                    "limit": limit,
                    "used": usage.count,
                },
            )
        usage.count += 1
        db.commit()


# ─── Endpoint: uso diário de busca ───────────────────────────────────────────

@router.get("/usage", response_model=SearchUsageResponse)
def get_search_usage(user=Depends(get_current_user)):
    """Retorna o uso diário de buscas do usuário autenticado."""
    limit = search_daily_limit_for_plan(user.plan)
    today = datetime.date.today()
    with SessionLocal() as db:
        usage = db.query(SearchUsage).filter(
            SearchUsage.user_id == user.id,
            SearchUsage.usage_date == today,
        ).first()
        count = usage.count if usage else 0
    remaining = (limit - count) if limit is not None else None
    return SearchUsageResponse(plan=user.plan, limit=limit, used=count, remaining=remaining)


# ─── Endpoint 1: busca no conteúdo do acervo ─────────────────────────────────

@router.get("/chunks", response_model=AcervoSearchResponse)
def search_chunks(
    q: str = Query(..., min_length=2, max_length=300, description="Termo ou frase a buscar"),
    limit: int = Query(default=50, ge=1, le=500),
    author: str = Query(default="", description="Filtrar por autor (keyword exato do ES)"),
    collection: str = Query(default="", description="'patristica' para filtrar apenas PL/PG/PO"),
    user=Depends(get_optional_user),
):
    """Busca semântica/textual dentro dos trechos indexados do acervo."""
    if user is None:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")
    # Patristic sub-queries (collection='patristica') are internal and don't consume quota
    _check_and_increment_quota(user, skip=(collection == "patristica"))
    patristic_ids = _get_patristic_book_ids()
    hits = _client().search_acervo(
        query=q, limit=limit, author_filter=author,
        collection_filter=collection, patristic_book_ids=patristic_ids,
    )
    results = _enrich_with_db(hits)
    return AcervoSearchResponse(results=results, total=len(results), query=q)


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

    chosen = candidates[day % len(candidates)]
    enriched = _enrich_with_db([chosen])
    e = enriched[0] if enriched else None

    return DailyCitationResponse(
        chunk_id=chosen.chunk_id,
        text=(chosen.text or "")[:600],
        author=chosen.author or None,
        work_title=chosen.work_title or None,
        pdf_page=chosen.pdf_page,
        chapter_or_section=chosen.chapter_or_section or None,
        edition_label=chosen.edition_label or None,
        language=chosen.language or None,
        translation_text=(chosen.translation_text or "")[:450] or None,
        book_id=e.book_id if e else None,
        book_file_id=e.book_file_id if e else None,
        day_of_year=day,
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
    _check_and_increment_quota(user)
    variants = _bible_search_variants(ref)
    if not variants:
        return AcervoSearchResponse(results=[], total=0, query=ref)

    # Build a bool/should query matching any variant in text or translation
    should_clauses = []
    for v in variants:
        should_clauses.append({"match_phrase": {"text": v}})
        should_clauses.append({"match_phrase": {"translation_text": v}})

    body = {
        "query": {"bool": {"should": should_clauses, "minimum_should_match": 1}},
        "size": limit,
    }

    from search.text_search import ES_INDEX
    client = _client()
    try:
        resp = client.es.search(index=ES_INDEX, body=body)
    except Exception:
        return AcervoSearchResponse(results=[], total=0, query=ref)

    from search.text_search import AcervoSearchHit
    raw_hits = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        raw_hits.append(AcervoSearchHit(
            chunk_id=src.get("chunk_id", int(hit["_id"])),
            score=hit["_score"] or 0.0,
            text=src.get("text", ""),
            author=src.get("author", ""),
            work_title=src.get("work_title", ""),
            pdf_page=src.get("pdf_page"),
            chapter_or_section=src.get("chapter_or_section"),
            collection=src.get("collection"),
            volume=src.get("volume"),
            edition_label=src.get("edition_label"),
            language=src.get("language"),
            translation_text=src.get("translation_text"),
        ))

    results = _enrich_with_db(raw_hits)
    return AcervoSearchResponse(results=results, total=len(results), query=ref)


# ─── Endpoint 4: chunks de um livro para leitura offline ─────────────────────

class OfflineChunk(BaseModel):
    chunk_id: int
    sequence_index: int | None
    chapter_or_section: str | None
    text: str
    translation_pt: str | None
    pdf_page: int | None
    volume: int | None


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
            .filter(Chunk.book_id == book_id)
            .order_by(Chunk.sequence_index.nulls_last(), Chunk.id)
            .limit(limit)
            .all()
        )

        # Batch-load translations for PT
        chunk_ids = [c.id for c in chunks]
        translations = (
            db.query(Translation)
            .filter(Translation.chunk_id.in_(chunk_ids), Translation.language == "pt")
            .all()
        ) if chunk_ids else []
        trans_map: dict[int, str] = {t.chunk_id: t.text for t in translations}

        result_chunks = [
            OfflineChunk(
                chunk_id=c.id,
                sequence_index=c.sequence_index,
                chapter_or_section=c.chapter_or_section or None,
                text=c.text[:1200],
                translation_pt=trans_map.get(c.id, None),
                pdf_page=c.pdf_page,
                volume=c.volume,
            )
            for c in chunks
        ]

    return OfflineBookResponse(
        book_id=book_id,
        title=book.title,
        author=book.canonical_author or book.author or None,
        edition_label=book.edition_label or None,
        language=book.language or None,
        chunks=result_chunks,
        total_chunks=len(result_chunks),
    )


# ─── Endpoint 5: comentário patrístico por artigo do Catecismo ───────────────

class CccCommentaryResponse(BaseModel):
    article: int
    section_title: str
    themes: list[str]
    results: list[AcervoResult]
    total: int


@router.get("/ccc-commentary", response_model=CccCommentaryResponse)
def ccc_commentary(
    article: int = Query(..., ge=1, le=2865, description="Número do artigo do CCC (1–2865)"),
    limit: int = Query(default=12, ge=1, le=30),
    user=Depends(get_optional_user),
):
    """
    Retorna trechos patrísticos do acervo relacionados a um artigo do Catecismo da Igreja Católica.
    Usa os temas teológicos da seção do artigo para buscar no Elasticsearch.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")
    _check_and_increment_quota(user)
    section = find_ccc_section(article)
    if not section:
        raise HTTPException(status_code=404, detail=f"Artigo {article} não encontrado na estrutura do Catecismo.")

    # Combina os principais temas como query de busca
    themes_query = " ".join(section["themes"][:6])
    hits = _client().search_acervo(query=themes_query, limit=limit)
    results = _enrich_with_db(hits)

    return CccCommentaryResponse(
        article=article,
        section_title=section["title"],
        themes=section["themes"],
        results=results,
        total=len(results),
    )
