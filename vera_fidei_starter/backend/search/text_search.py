import logging
import os
import re
import unicodedata
from dataclasses import dataclass, replace

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from core.config import settings

ES_INDEX = "vera_fidei_chunks"

_log = logging.getLogger(__name__)


class AcervoSearchUnavailable(RuntimeError):
    """The authoritative lexical index could not answer the request."""

# Códigos realmente presentes no catálogo. ``patristic_book_ids`` continua
# sendo aceito porque novas coleções podem surgir sem uma alteração de código.
PATRISTIC_COLLECTIONS: tuple[str, ...] = (
    "PL",
    "PG",
    "PO",
    "PT",
    "Patrística EN",
    "Patrística LA",
    "Patrística PT",
    "DIDAQUE",
)
_PATRISTIC_ORIGINAL_COLLECTIONS: tuple[str, ...] = ("PL", "PG", "PO")
_PATRISTIC_PORTUGUESE_COLLECTIONS: tuple[str, ...] = ("PT", "Patrística PT")
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Portuguese → source-language theological term expansion
_THEO_LATIN: dict[str, list[str]] = {
    "eucaristia": ["eucharistia", "eucharistiam", "eucharistiae"],
    "batismo": ["baptismus", "baptisma", "baptismum", "baptismi"],
    "batizar": ["baptizare", "baptizo"],
    "trindade": ["trinitas", "trinitatis", "trinitate"],
    "graca": ["gratia", "gratiam", "gratiae"],
    "pecado": ["peccatum", "peccati", "peccata", "peccatorum"],
    "salvacao": ["salus", "salutis", "salvatio", "salvationis"],
    "ressurreicao": ["resurrectio", "resurrectionis", "resurrectione"],
    "encarnacao": ["incarnatio", "incarnationis", "incarnatione"],
    "paixao": ["passio", "passionis", "passione"],
    "fe": ["fides", "fidei", "fidem"],
    "caridade": ["caritas", "caritatis", "caritatem"],
    "esperanca": ["spes", "spei", "spem"],
    "oracao": ["oratio", "orationis", "orationem"],
    "alma": ["anima", "animae", "animam"],
    "corpo": ["corpus", "corporis", "corpore"],
    "sangue": ["sanguis", "sanguinis", "sanguine"],
    "igreja": ["ecclesia", "ecclesiae", "ecclesiam"],
    "sacerdote": ["sacerdos", "sacerdotis", "presbyteros", "presbyter"],
    "sacerdocio": ["sacerdotium", "sacerdotii"],
    "missa": ["missa", "missae"],
    "confirmacao": ["confirmatio", "confirmationis"],
    "penitencia": ["poenitentia", "poenitentiam", "paenitentia"],
    "matrimonio": ["matrimonium", "matrimonii"],
    "virgem": ["virgo", "virginis", "virginem"],
    "misericordia": ["misericordia", "misericordiam", "misericordiae"],
    "humildade": ["humilitas", "humilitatis", "humilitatem"],
    "contemplacao": ["contemplatio", "contemplationis"],
    "ascensao": ["ascensio", "ascensionis"],
    "pentecostes": ["pentecoste", "pentecostes"],
    "redencao": ["redemptio", "redemptionis"],
    "unção": ["unctio", "unctionis"],
    "martir": ["martyr", "martyris", "martyrem", "martyres"],
    "virgindade": ["virginitas", "virginitatis"],
    "celibato": ["caelibatus", "coelibatus"],
    "profecia": ["prophetia", "prophetiae"],
    "revelacao": ["revelatio", "revelationis"],
    "tradicao": ["traditio", "traditionis"],
    "escritura": ["scriptura", "scripturae", "scripturam"],
    "biblia": ["biblia", "scriptura sacra"],
    "apostolo": ["apostolus", "apostoli", "apostolum", "apostolos"],
    "bispo": ["episcopus", "episcopi", "episcopum", "episkopos"],
    "diacono": ["diaconus", "diaconi", "diaconum"],
    "monge": ["monachus", "monachi"],
    "deserto": ["desertum", "eremos"],
    "jejum": ["ieiunium", "ieiunii", "ieiunia"],
    "esmola": ["eleemosyna", "eleemosynae"],
    "pobreza": ["paupertas", "paupertatis"],
    "obediencia": ["oboedientia", "obedientia"],
    "castidade": ["castitas", "castitatis"],
    "oleo": ["oleum", "olei"],
    "crisma": ["chrisma", "chrismatis"],
    "absolvicao": ["absolutio", "absolutionis"],
    "indulgencia": ["indulgentia", "indulgentiae"],
    "purgatorio": ["purgatorium", "purgatorii"],
    "paraiso": ["paradisus", "paradisi"],
    "inferno": ["infernus", "inferni", "infernum"],
    "anjo": ["angelus", "angeli", "angelum", "angelos"],
    "demonio": ["daemon", "daemonis", "diabolus"],
    "diabo": ["diabolus", "diaboli"],
    "tentacao": ["tentatio", "tentationis"],
    "oracão dominical": ["oratio dominica", "pater noster"],
    "pai nosso": ["pater noster"],
    "ave maria": ["ave maria", "salutatio angelica"],
    "credo": ["symbolum", "credo", "symbolum fidei"],
    "palavra": ["verbum", "verbi"],
    "luz": ["lux", "lucis"],
    "verdade": ["veritas", "veritatis"],
    "vida": ["vita", "vitae"],
    "caminho": ["via", "viae"],
    "ressuscitado": ["resurrexit", "resurgens"],
    # Nomes próprios com declinações latinas diferentes do nominativo
    "maria": ["mariam", "mariae", "virgine maria", "beata virgo", "sancta maria"],
    "virgem maria": ["virgo maria", "beata virgo maria", "virginis mariae"],
    "mae de deus": ["dei genitrix", "theotokos", "mater dei", "mater domini"],
    "imaculada": ["immaculata", "immaculatae", "immaculatam", "sine labe concepta"],
    "assuncao": ["assumptio", "assumptionis", "assumptionem"],
    "anunciacao": ["annuntiatio", "annuntiationis"],
    "natividade": ["nativitas", "nativitatis", "nativitatem"],
    "jesus": ["iesum", "iesu", "iesus", "christe", "christum", "christi"],
    "cristo": ["christus", "christi", "christum", "christe"],
    "espirito santo": ["spiritus sanctus", "spiritus sancti", "spiritu sancto"],
    "deus pai": ["deus pater", "dei patris", "deum patrem"],
    "filho de deus": ["filius dei", "filii dei", "filium dei"],
    "cruz": ["crux", "crucis", "crucem", "cruce"],
    "morte": ["mors", "mortis", "mortem"],
    "morte de cristo": ["mors christi", "passio christi", "passione christi"],
    "amor": ["amor", "amoris", "amorem", "caritas"],
    # Alias legado mantido para consultas em italiano.
    "amore": ["amor", "amoris", "amorem", "caritas"],
    "verdadeiro corpo": ["verum corpus", "vere corpus"],
    "presença real": ["praesentia realis", "vere et realiter"],
}

# Exact equivalents used by the multilingual corpus search. They complement
# the Latin morphology above without translating or rewriting the quotation
# itself: the result card always displays the indexed source wording.
_THEO_MULTILINGUAL: dict[str, list[str]] = {
    "eucaristia": [
        "eucharist",
        "eucharistic",
        "holy communion",
        "εὐχαριστία",
        "εὐχαριστίας",
        "εὐχαριστίᾳ",
        "εὐχαριστίαν",
        "εὐχαριστεῖν",
        "εὐχαριστήσατε",
        "εὐχαριστοῦμεν",
        "ευχαριστία",
        "ευχαριστίας",
        "ευχαριστίαν",
        "ευχαριστήσατε",
        "ευχαριστούμεν",
        "ܐܘܟܪܣܛܝܐ",
        "ܩܘܪܒܢܐ",
        "الإفخارستيا",
        "القربان",
    ],
    "anjo": [
        "angel",
        "angels",
        "ἄγγελος",
        "ἀγγέλου",
        "ἄγγελον",
        "ἄγγελοι",
        "ἀγγέλους",
        "αγγελος",
        "αγγελου",
        "αγγελον",
        "αγγελοι",
        "αγγελους",
        "ܡܠܐܟܐ",
        "ܡܠܐܟ̈ܐ",
        "ملاك",
        "ملائكة",
    ],
}


def _theological_equivalents(portuguese_term: str) -> list[str]:
    return [
        *_THEO_LATIN.get(portuguese_term, ()),
        *_THEO_MULTILINGUAL.get(portuguese_term, ()),
    ]


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(_strip_accents(text))


def _contains_token_sequence(haystack: list[str], needle: list[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    width = len(needle)
    return any(haystack[start:start + width] == needle for start in range(len(haystack) - width + 1))


def theological_query_expansions(query: str) -> list[str]:
    """Retorna equivalentes somente para palavras/expressões completas.

    A implementação anterior usava ``if term in query`` e, por exemplo,
    encontrava ``fe`` dentro de ``afetos``. A comparação por sequência de
    tokens também permite expressões separadas por hífen ou pontuação.
    """
    query_tokens = _tokens(query)
    extra: list[str] = []
    seen: set[str] = set()
    for pt_term in dict.fromkeys((*_THEO_LATIN, *_THEO_MULTILINGUAL)):
        if not _contains_token_sequence(query_tokens, _tokens(pt_term)):
            continue
        for equivalent in _theological_equivalents(pt_term):
            normalized = unicodedata.normalize("NFC", equivalent).casefold().strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                extra.append(equivalent)
    return extra


def theological_literal_variants(query: str) -> list[str]:
    """Return curated source-language variants for one complete query term.

    This is deliberately stricter than :func:`theological_query_expansions`.
    Search expansion may enrich a longer query with several related terms,
    while the public quotation gate must never let one translated word
    authorize an otherwise different phrase. Only a query whose complete
    token sequence equals a curated Portuguese key receives literal variants.
    """
    query_tokens = _tokens(query)
    if not query_tokens:
        return []
    for portuguese_term in dict.fromkeys((*_THEO_LATIN, *_THEO_MULTILINGUAL)):
        if query_tokens == _tokens(portuguese_term):
            return _theological_equivalents(portuguese_term)
    return []


def expand_theological_query(query: str) -> str:
    """Expand a Portuguese theological query with Latin/Greek equivalents for Elasticsearch."""
    extra = theological_query_expansions(query)
    if extra:
        # Deduplicate and append to original query
        seen = set(_tokens(query))
        new_terms = [t for t in extra if _strip_accents(t) not in seen]
        if new_terms:
            return query + " " + " ".join(new_terms)
    return query


@dataclass
class TextSearchHit:
    chunk_id: int
    score: float
    excerpt: str


@dataclass
class AcervoSearchHit:
    chunk_id: int
    score: float
    text: str
    author: str
    work_title: str
    chunk_author: str | None = None
    pdf_page: int | None = None
    chapter_or_section: str | None = None
    collection: str | None = None
    volume: int | None = None
    edition_label: str | None = None
    language: str | None = None
    translation_text: str | None = None
    book_id: int | None = None
    book_file_id: int | None = None
    match_type: str = "literal"


@dataclass
class AcervoSearchPage:
    """One stable page of lexical results, collapsed by PDF source page."""

    hits: list[AcervoSearchHit]
    total: int
    matching_works: int
    offset: int
    consumed: int


def source_page_key(doc: dict, chunk_id: int) -> str:
    """Return the persisted key used to collapse duplicate chunks per page.

    A book can contain more than one PDF, so ``book_file_id`` takes priority.
    Legacy records without a file still remain stable under ``book_id``. A
    chunk without a page must not collapse together with every other pageless
    chunk, hence the final chunk-id fallback.
    """
    page = doc.get("pdf_page")
    if page is None:
        return f"chunk:{chunk_id}"
    book_file_id = doc.get("book_file_id")
    if book_file_id is not None:
        return f"file:{book_file_id}:page:{page}"
    book_id = doc.get("book_id")
    if book_id is not None:
        return f"book:{book_id}:page:{page}"
    return f"chunk:{chunk_id}:page:{page}"


class TextSearchClient:
    def __init__(self) -> None:
        self.es = Elasticsearch([settings.elasticsearch_url])
        self._ensure_index()

    def _ensure_index(self) -> None:
        quality_properties = {
            "content_role": {"type": "keyword"},
            "is_quotable": {"type": "boolean"},
            "content_quality_score": {"type": "float"},
            "extraction_method": {"type": "keyword"},
            "source_fidelity": {"type": "keyword"},
            "fidelity_score": {"type": "float"},
            "source_page_key": {"type": "keyword"},
            # Accent-folded copy of the authoritative source text. Public
            # quotation searches use this field only to locate exact wording;
            # the card still displays the untouched ``text`` value.
            "literal_search_text": {"type": "text", "analyzer": "standard"},
        }
        if not self.es.indices.exists(index=ES_INDEX):
            self.es.indices.create(index=ES_INDEX, body={
                "mappings": {
                    "properties": {
                        "chunk_id":          {"type": "integer"},
                        "book_id":           {"type": "integer"},
                        "book_file_id":      {"type": "integer"},
                        "text":              {"type": "text", "analyzer": "standard"},
                        "author":            {"type": "keyword"},
                        "work_title":        {"type": "keyword"},
                        "collection":        {"type": "keyword"},
                        "volume":            {"type": "integer"},
                        "column_start":      {"type": "integer"},
                        "language":          {"type": "keyword"},
                        "pdf_page":          {"type": "integer"},
                        "edition_label":     {"type": "keyword"},
                        "chapter_or_section":{"type": "keyword"},
                        "char_offset_start": {"type": "integer"},
                        "char_offset_end":   {"type": "integer"},
                        "translation_text":  {"type": "text", "analyzer": "standard"},
                        "translation_language": {"type": "keyword"},
                        **quality_properties,
                    }
                }
            })
        else:
            try:
                self.es.indices.put_mapping(index=ES_INDEX, properties=quality_properties)
            except Exception as exc:
                # Runtime quality filtering remains authoritative even when an
                # older/read-only ES index cannot accept the optional fields.
                _log.warning("Could not add content-quality mapping: %s", exc)

    def search(self, query: str, attributed_to: str = "", limit: int = 5, query_language: str = "unknown") -> list[TextSearchHit]:
        if not query.strip():
            return []

        _ORIGINAL_LANGS = {"la", "grc", "el", "he"}
        _TRANSLATION_LANGS = {"pt", "es", "fr", "it", "en", "de"}

        query_langs = set((query_language or "unknown").split("+"))

        if query_langs & _TRANSLATION_LANGS:
            fields = ["translation_text^2", "text"]
        elif query_langs & _ORIGINAL_LANGS:
            fields = ["text^2", "translation_text"]
        else:
            fields = ["text^1.2", "translation_text^1.2"]

        body = {
            "query": {
                "bool": {
                    "must": [{"multi_match": {"query": query, "fields": fields}}],
                    "should": ([{"match": {"author": attributed_to}}] if attributed_to else []),
                }
            },
            "size": limit,
        }

        try:
            resp = self.es.search(index=ES_INDEX, body=body)
        except Exception:
            return []

        hits = []
        for hit in resp["hits"]["hits"]:
            hits.append(TextSearchHit(
                chunk_id=hit["_source"]["chunk_id"],
                score=hit["_score"],
                excerpt=hit["_source"].get("text", "")[:350],
            ))
        return hits

    def _build_acervo_es_body(
        self,
        expanded_query: str,
        fields: list[str],
        author_filter: str,
        collection_filter: str,
        limit: int,
        patristic_book_ids: list[int] | None = None,
        original_query: str | None = None,
        collapse_by_book: bool = False,
        collapse_by_page: bool = False,
        offset: int = 0,
        source_fidelities: list[str] | None = None,
        include_page_counts: bool = False,
        literal_candidates_only: bool = False,
    ) -> dict:
        original_query = (original_query or expanded_query).strip()
        original_tokens = _tokens(original_query)

        # A consulta original precisa preservar um núcleo lexical mínimo. A
        # frase exata recebe forte boost, enquanto cada equivalente teológico
        # é uma alternativa (sinônimo), nunca um termo obrigatório adicional.
        if len(original_tokens) <= 2:
            minimum_should_match = "100%"
        elif len(original_tokens) <= 5:
            minimum_should_match = "70%"
        elif len(original_tokens) <= 10:
            minimum_should_match = "60%"
        else:
            minimum_should_match = "50%"

        if literal_candidates_only:
            literal_variants = [original_query, *theological_literal_variants(original_query)]
            query_alternatives = []
            seen_literal_variants: set[str] = set()
            for variant in literal_variants:
                folded_variant = _strip_accents(variant).strip()
                if not folded_variant or folded_variant in seen_literal_variants:
                    continue
                seen_literal_variants.add(folded_variant)
                variant_tokens = _tokens(folded_variant)
                # Search both literal_search_text (populated for source_text
                # and verified chunks) AND text (the raw OCR field, populated
                # for unverified_ocr Migne PG/PL/PO chunks where
                # literal_search_text is absent). One match in either field is
                # enough to surface the chunk for the fidelity gate downstream.
                if len(variant_tokens) == 1:
                    query_alternatives.append({
                        "bool": {
                            "should": [
                                {"match": {"literal_search_text": {"query": folded_variant, "operator": "and"}}},
                                {"match": {"text": {"query": folded_variant, "operator": "and"}}},
                            ],
                            "minimum_should_match": 1,
                        }
                    })
                else:
                    query_alternatives.append({
                        "bool": {
                            "should": [
                                {"match_phrase": {"literal_search_text": {"query": folded_variant, "slop": 0}}},
                                {"match_phrase": {"text": {"query": folded_variant, "slop": 1}}},
                            ],
                            "minimum_should_match": 1,
                        }
                    })
        else:
            query_alternatives = [{
                "multi_match": {
                    "query": original_query,
                    "fields": fields,
                    "type": "best_fields",
                    "minimum_should_match": minimum_should_match,
                    "boost": 2.0,
                }
            }]
        if not literal_candidates_only and len(original_tokens) >= 2:
            query_alternatives.insert(0, {
                "multi_match": {
                    "query": original_query,
                    "fields": fields,
                    "type": "phrase",
                    "slop": 1,
                    "boost": 6.0,
                }
            })
        if not literal_candidates_only and source_fidelities and original_tokens:
            # The historical index uses the standard analyzer, which does not
            # fold accents. A low-boost fuzzy branch retrieves candidates such
            # as ``ressurreicao`` -> ``ressurreiÃ§Ã£o``; the public literal gate
            # then requires accent-insensitive equality before displaying the
            # untouched source wording, so ordinary misspellings never pass.
            query_alternatives.append({
                "multi_match": {
                    "query": original_query,
                    "fields": fields,
                    "type": "best_fields",
                    "operator": "and",
                    "fuzziness": "AUTO",
                    "prefix_length": 2,
                    "boost": 0.35,
                }
            })
        for equivalent in ([] if literal_candidates_only else theological_query_expansions(original_query)):
            query_alternatives.append({
                "multi_match": {
                    "query": equivalent,
                    "fields": fields,
                    "type": "best_fields",
                    "operator": "and",
                    "boost": 0.8,
                }
            })

        must: list = [{
            "bool": {
                "should": query_alternatives,
                "minimum_should_match": 1,
            }
        }]
        should: list = []
        if author_filter:
            should.append({"match": {"author": author_filter}})
        filter_clauses: list = []
        if author_filter:
            filter_clauses.append({"term": {"author": author_filter}})
        if collection_filter == "patristica":
            patristic_alternatives: list[dict] = [
                {"terms": {"collection": list(PATRISTIC_COLLECTIONS)}}
            ]
            if patristic_book_ids:
                patristic_alternatives.append({"terms": {"book_id": sorted(set(patristic_book_ids))}})
            filter_clauses.append({
                "bool": {
                    "should": patristic_alternatives,
                    "minimum_should_match": 1,
                }
            })
        elif collection_filter == "patristica_original":
            filter_clauses.append({"terms": {"collection": list(_PATRISTIC_ORIGINAL_COLLECTIONS)}})
        elif collection_filter == "patristica_portuguesa":
            filter_clauses.append({"terms": {"collection": list(_PATRISTIC_PORTUGUESE_COLLECTIONS)}})
        if source_fidelities:
            filter_clauses.append({"terms": {"source_fidelity": source_fidelities}})
            filter_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"is_quotable": True}},
                        {"term": {"source_fidelity": "verified"}},
                        {"bool": {"must_not": [{"exists": {"field": "is_quotable"}}]}},
                    ],
                    "minimum_should_match": 1,
                }
            })
        body = {
            "query": {
                "bool": {
                    "must": must,
                    **({"should": should} if should else {}),
                    **({"filter": filter_clauses} if filter_clauses else {}),
                }
            },
            "size": limit,
            "from": max(0, offset),
            "min_score": 0.05,
        }
        if collapse_by_book and collapse_by_page:
            raise ValueError("collapse_by_book and collapse_by_page are mutually exclusive")
        if collapse_by_book:
            # Common terms can fill hundreds of top-ranked slots from one
            # very large volume. A second collapsed query reserves one hit
            # per matching work before repeated pages are merged in.
            body["collapse"] = {"field": "book_id"}
        elif collapse_by_page:
            body["collapse"] = {"field": "source_page_key"}
        if include_page_counts:
            body["track_total_hits"] = True
            body["aggs"] = {
                "matching_pages": {
                    "cardinality": {
                        "field": "source_page_key",
                        "precision_threshold": 40000,
                    }
                },
                "matching_works": {
                    "cardinality": {
                        "field": "book_id",
                        "precision_threshold": 40000,
                    }
                },
            }
        return body

    def _parse_acervo_response(self, resp: dict) -> list[AcervoSearchHit]:
        hits = []
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            hits.append(AcervoSearchHit(
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
                book_id=src.get("book_id"),
                book_file_id=src.get("book_file_id"),
            ))
        return hits

    def search_acervo(
        self,
        query: str,
        limit: int = 20,
        author_filter: str = "",
        query_language: str = "unknown",
        collection_filter: str = "",
        patristic_book_ids: list[int] | None = None,
        *,
        raise_on_error: bool = True,
        collapse_by_book: bool = False,
    ) -> list[AcervoSearchHit]:
        if not query.strip():
            return []

        _ORIGINAL_LANGS = {"la", "grc", "el", "he"}
        _TRANSLATION_LANGS = {"pt", "es", "fr", "it", "en", "de"}
        query_langs = set((query_language or "unknown").split("+"))

        if query_langs & _TRANSLATION_LANGS:
            fields = ["translation_text^2", "text"]
        elif query_langs & _ORIGINAL_LANGS:
            fields = ["text^2", "translation_text"]
        else:
            fields = ["text^1.2", "translation_text^1.2"]

        expanded = expand_theological_query(query)

        # Reserve fixed slots to guarantee patristic sources appear in every search.
        # PL/PG/PO: Latin/Greek originals; PT: Paulus Portuguese translations.
        # Only applies to general searches (not when already filtered to patristica or by author).
        do_pat_guarantee = collection_filter != "patristica" and not author_filter
        plpgpo_quota = 15 if do_pat_guarantee else 0
        pt_quota = 25 if do_pat_guarantee else 0
        pat_quota = plpgpo_quota + pt_quota
        main_limit = max(1, limit - pat_quota)

        try:
            main_body = self._build_acervo_es_body(
                expanded, fields, author_filter, collection_filter, main_limit,
                patristic_book_ids=patristic_book_ids,
                original_query=query,
                collapse_by_book=collapse_by_book,
            )
            resp = self.es.search(index=ES_INDEX, body=main_body)
            results = self._parse_acervo_response(resp)
        except Exception as exc:
            if raise_on_error:
                raise AcervoSearchUnavailable("Elasticsearch acervo search failed") from exc
            _log.warning("Acervo lexical search unavailable: %s", exc)
            return []

        seen_ids = {h.chunk_id for h in results}

        def _add_guaranteed(hits: list[AcervoSearchHit]) -> None:
            for h in hits:
                if h.chunk_id not in seen_ids:
                    results.append(h)
                    seen_ids.add(h.chunk_id)

        # Guaranteed PL/PG/PO: Latin/Greek/Oriental originals always appear.
        if plpgpo_quota > 0:
            try:
                plpgpo_body = self._build_acervo_es_body(
                    expanded, fields, "", "patristica_original", plpgpo_quota,
                    original_query=query,
                )
                _add_guaranteed(self._parse_acervo_response(self.es.search(index=ES_INDEX, body=plpgpo_body)))
            except Exception:
                pass

        # Guaranteed Portuguese patristic editions (PT and Patrística PT).
        if pt_quota > 0:
            try:
                pt_body = self._build_acervo_es_body(
                    query, ["text^2", "translation_text"], "", "patristica_portuguesa", pt_quota,
                    original_query=query,
                )
                _add_guaranteed(self._parse_acervo_response(self.es.search(index=ES_INDEX, body=pt_body)))
            except Exception:
                pass

        return results[:limit]

    def search_acervo_page(
        self,
        query: str,
        limit: int = 36,
        offset: int = 0,
        author_filter: str = "",
        query_language: str = "unknown",
        collection_filter: str = "",
        patristic_book_ids: list[int] | None = None,
        *,
        source_fidelities: list[str] | None = None,
        literal_candidates_only: bool | None = None,
        raise_on_error: bool = True,
    ) -> AcervoSearchPage:
        """Search one lightweight, page-deduplicated slice of the corpus.

        Elasticsearch collapse keeps multiple chunks from the same physical
        PDF page out of the public list. Cardinality aggregations provide the
        full page/work counts without shipping the full result set to mobile.
        """
        if not query.strip():
            return AcervoSearchPage([], 0, 0, max(0, offset), 0)

        original_languages = {"la", "grc", "el", "he"}
        translation_languages = {"pt", "es", "fr", "it", "en", "de"}
        query_languages = set((query_language or "unknown").split("+"))
        if query_languages & translation_languages:
            fields = ["translation_text^2", "text"]
        elif query_languages & original_languages:
            fields = ["text^2", "translation_text"]
        else:
            fields = ["text^1.2", "translation_text^1.2"]

        try:
            body = self._build_acervo_es_body(
                expand_theological_query(query),
                fields,
                author_filter,
                collection_filter,
                max(1, limit),
                patristic_book_ids=patristic_book_ids,
                original_query=query,
                collapse_by_page=True,
                offset=max(0, offset),
                source_fidelities=source_fidelities,
                include_page_counts=True,
                literal_candidates_only=(
                    literal_candidates_only
                    if literal_candidates_only is not None
                    else bool(source_fidelities)
                ),
            )
            response = self.es.search(index=ES_INDEX, body=body)
            hits = self._parse_acervo_response(response)
            aggregations = response.get("aggregations") or {}
            matching_pages = aggregations.get("matching_pages") or {}
            matching_works = aggregations.get("matching_works") or {}
            raw_total = (response.get("hits") or {}).get("total", 0)
            if isinstance(raw_total, dict):
                raw_total = raw_total.get("value", 0)
            return AcervoSearchPage(
                hits=hits,
                total=int(matching_pages.get("value", raw_total or 0)),
                matching_works=int(matching_works.get("value", 0)),
                offset=max(0, offset),
                consumed=len(hits),
            )
        except Exception as exc:
            if raise_on_error:
                raise AcervoSearchUnavailable("Elasticsearch paged acervo search failed") from exc
            _log.warning("Paged acervo lexical search unavailable: %s", exc)
            return AcervoSearchPage([], 0, 0, max(0, offset), 0)

    def _hydrate_acervo_hits(self, chunk_ids: list[int]) -> dict[int, AcervoSearchHit]:
        """Carrega documentos completos do ES mantendo a ordem fora do servidor."""
        if not chunk_ids:
            return {}
        response = self.es.mget(index=ES_INDEX, body={"ids": [str(chunk_id) for chunk_id in chunk_ids]})
        hydrated: dict[int, AcervoSearchHit] = {}
        for document in response.get("docs", []):
            if not document.get("found"):
                continue
            src = document.get("_source") or {}
            try:
                chunk_id = int(src.get("chunk_id", document.get("_id")))
            except (TypeError, ValueError):
                continue
            hydrated[chunk_id] = AcervoSearchHit(
                chunk_id=chunk_id,
                score=0.0,
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
                book_id=src.get("book_id"),
                book_file_id=src.get("book_file_id"),
            )
        return hydrated

    def search_acervo_hybrid(
        self,
        query: str,
        limit: int = 20,
        author_filter: str = "",
        query_language: str = "unknown",
        collection_filter: str = "",
        patristic_book_ids: list[int] | None = None,
        *,
        semantic_client: object | None = None,
        lexical_weight: float = 0.55,
        semantic_weight: float = 0.45,
        semantic_min_score: float = 0.18,
        semantic_timeout: float = 15.0,
        rrf_k: int = 60,
        exact_match_boost: float = 0.15,
        raise_on_error: bool = True,
    ) -> list[AcervoSearchHit]:
        """Busca híbrida com RRF lexical/vetorial e fallback seguro.

        A assinatura principal de ``search_acervo`` permanece intacta. Quem
        quiser semântica pode trocar apenas o nome do método; indisponibilidade
        do modelo, Chroma, subprocesso ou documento no ES devolve a busca
        lexical, sem transformar falha de infraestrutura em lista vazia. O
        limiar semântico é calibrado para a faixa do bge-m3 neste corpus; o
        ranking, e não a escala bruta dos scores, conduz a fusão.
        """
        lexical_hits = self.search_acervo(
            query=query,
            limit=limit,
            author_filter=author_filter,
            query_language=query_language,
            collection_filter=collection_filter,
            patristic_book_ids=patristic_book_ids,
            raise_on_error=raise_on_error,
        )
        if not query.strip() or limit <= 0:
            return lexical_hits[:max(0, limit)]
        if os.environ.get("VERA_ENABLE_SEMANTIC_SEARCH", "true").strip().lower() in {
            "0", "false", "no", "off",
        }:
            return lexical_hits[:limit]

        candidate_limit = min(200, max(30, limit * 3))
        try:
            if semantic_client is None:
                # Import tardio: o caminho puramente lexical não passa a
                # depender de torch/sentence-transformers no startup.
                from search.semantic_search import SemanticSearchClient
                semantic_client = SemanticSearchClient()
            semantic_hits = semantic_client.search(
                query,
                limit=candidate_limit,
                timeout=max(3.0, semantic_timeout),
            )
        except Exception as exc:
            _log.warning("Semantic search unavailable; using lexical fallback: %s", exc)
            return lexical_hits[:limit]

        semantic_scores: dict[int, float] = {}
        semantic_ranks: dict[int, int] = {}
        for rank, hit in enumerate(semantic_hits, start=1):
            score = max(0.0, min(1.0, float(hit.score)))
            if score >= semantic_min_score:
                chunk_id = int(hit.chunk_id)
                if chunk_id not in semantic_scores:
                    semantic_scores[chunk_id] = score
                    semantic_ranks[chunk_id] = rank
        if not semantic_scores:
            return lexical_hits[:limit]

        try:
            hydrated = self._hydrate_acervo_hits(list(semantic_scores))
        except Exception as exc:
            _log.warning("Could not hydrate semantic hits; using lexical fallback: %s", exc)
            return lexical_hits[:limit]

        lexical_by_id = {hit.chunk_id: hit for hit in lexical_hits}
        allowed_patristic_ids = set(patristic_book_ids or [])

        def allowed(hit: AcervoSearchHit) -> bool:
            if author_filter and hit.author != author_filter:
                return False
            if collection_filter == "patristica":
                return (
                    (hit.collection or "") in PATRISTIC_COLLECTIONS
                    or (hit.book_id is not None and hit.book_id in allowed_patristic_ids)
                )
            if collection_filter == "patristica_original":
                return (hit.collection or "") in _PATRISTIC_ORIGINAL_COLLECTIONS
            if collection_filter == "patristica_portuguesa":
                return (hit.collection or "") in _PATRISTIC_PORTUGUESE_COLLECTIONS
            return True

        hydrated = {chunk_id: hit for chunk_id, hit in hydrated.items() if allowed(hit)}
        # Um resultado já presente no ramo lexical não depende do ``mget``
        # para participar da fusão; hidratação é necessária apenas para
        # candidatos exclusivamente semânticos.
        semantic_scores = {
            chunk_id: score
            for chunk_id, score in semantic_scores.items()
            if chunk_id in lexical_by_id or chunk_id in hydrated
        }
        if not semantic_scores:
            return lexical_hits[:limit]

        lexical_weight = max(0.0, lexical_weight)
        semantic_weight = max(0.0, semantic_weight)
        exact_match_boost = max(0.0, exact_match_boost)
        rrf_k = max(1, int(rrf_k))
        lexical_ranks = {hit.chunk_id: rank for rank, hit in enumerate(lexical_hits, start=1)}
        normalized_query = _strip_accents(query).strip()
        maximum_rrf = max(
            (lexical_weight + semantic_weight + exact_match_boost) / (rrf_k + 1),
            1e-9,
        )
        fused: list[AcervoSearchHit] = []
        for chunk_id in set(lexical_by_id) | set(semantic_scores):
            hit = lexical_by_id.get(chunk_id) or hydrated.get(chunk_id)
            if hit is None:
                continue
            raw_rrf = 0.0
            lexical_rank = lexical_ranks.get(chunk_id)
            if lexical_rank is not None:
                raw_rrf += lexical_weight / (rrf_k + lexical_rank)
            semantic_rank = semantic_ranks.get(chunk_id)
            if semantic_rank is not None:
                raw_rrf += semantic_weight / (rrf_k + semantic_rank)

            if lexical_rank is not None and normalized_query:
                searchable_text = _strip_accents(
                    " ".join(filter(None, (hit.text, hit.translation_text)))
                )
                if normalized_query in searchable_text:
                    raw_rrf += exact_match_boost / (rrf_k + lexical_rank)

            fused_score = min(1.0, raw_rrf / maximum_rrf)
            fused.append(replace(
                hit,
                score=round(fused_score, 6),
                match_type="literal" if lexical_rank is not None else "semantic",
            ))

        fused.sort(key=lambda hit: (-hit.score, hit.chunk_id))
        return fused[:limit]

    def search_acervo_semantic(
        self,
        query: str,
        limit: int = 40,
        author_filter: str = "",
        collection_filter: str = "",
        patristic_book_ids: list[int] | None = None,
        *,
        semantic_min_score: float = 0.36,
        semantic_timeout: float = 8.0,
        raise_on_error: bool = True,
    ) -> list[AcervoSearchHit]:
        """Return semantic-only candidates without an unnecessary lexical scan."""
        if not query.strip() or limit <= 0:
            return []
        if os.environ.get("VERA_ENABLE_SEMANTIC_SEARCH", "true").strip().lower() in {
            "0", "false", "no", "off",
        }:
            return []
        try:
            from search.semantic_search import SemanticSearchClient

            raw_hits = SemanticSearchClient().search(
                query,
                limit=min(200, max(30, limit * 3)),
                timeout=max(3.0, semantic_timeout),
            )
            scores = {
                int(hit.chunk_id): max(0.0, min(1.0, float(hit.score)))
                for hit in raw_hits
                if float(hit.score) >= semantic_min_score
            }
            hydrated = self._hydrate_acervo_hits(list(scores))
        except Exception as exc:
            if raise_on_error:
                raise AcervoSearchUnavailable("Semantic acervo search failed") from exc
            _log.warning("Semantic-only acervo search unavailable: %s", exc)
            return []

        allowed_patristic_ids = set(patristic_book_ids or [])

        def allowed(hit: AcervoSearchHit) -> bool:
            if author_filter and hit.author != author_filter:
                return False
            if collection_filter == "patristica":
                return (
                    (hit.collection or "") in PATRISTIC_COLLECTIONS
                    or (hit.book_id is not None and hit.book_id in allowed_patristic_ids)
                )
            if collection_filter == "patristica_original":
                return (hit.collection or "") in _PATRISTIC_ORIGINAL_COLLECTIONS
            if collection_filter == "patristica_portuguesa":
                return (hit.collection or "") in _PATRISTIC_PORTUGUESE_COLLECTIONS
            return True

        ranked = [
            replace(hit, score=scores[chunk_id], match_type="semantic")
            for chunk_id, hit in hydrated.items()
            if allowed(hit)
        ]
        ranked.sort(key=lambda hit: (-hit.score, hit.chunk_id))
        return ranked[:limit]

    def author_chunks(self, author: str, limit: int = 500) -> list[AcervoSearchHit]:
        """Return chunks indexed under a specific author keyword (for daily citation)."""
        if not author.strip():
            return []
        body = {
            "query": {"term": {"author": author}},
            "size": limit,
            "sort": [{"pdf_page": {"order": "asc"}}],
        }
        try:
            resp = self.es.search(index=ES_INDEX, body=body)
        except Exception:
            return []
        hits = []
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            hits.append(AcervoSearchHit(
                chunk_id=src.get("chunk_id", int(hit["_id"])),
                score=1.0,
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
                book_id=src.get("book_id"),
                book_file_id=src.get("book_file_id"),
            ))
        return hits

    def index_chunk(self, chunk_id: int, doc: dict) -> None:
        source = {**doc, "chunk_id": chunk_id}
        source["source_page_key"] = source_page_key(source, chunk_id)
        source["literal_search_text"] = _strip_accents(source.get("text", ""))
        self.es.index(index=ES_INDEX, id=str(chunk_id), document=source)

    def index_chunks(self, items: list[tuple[int, dict]]) -> None:
        if not items:
            return
        actions = []
        for chunk_id, doc in items:
            source = {**doc, "chunk_id": chunk_id}
            source["source_page_key"] = source_page_key(source, chunk_id)
            source["literal_search_text"] = _strip_accents(source.get("text", ""))
            actions.append({
                "_op_type": "index",
                "_index": ES_INDEX,
                "_id": str(chunk_id),
                "_source": source,
            })
        bulk(self.es, actions)

    def delete_chunk(self, chunk_id: int) -> None:
        try:
            self.es.delete(index=ES_INDEX, id=str(chunk_id), ignore=[404])
        except Exception:
            pass
