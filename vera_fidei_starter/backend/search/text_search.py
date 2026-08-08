import unicodedata
from dataclasses import dataclass, field
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from core.config import settings

ES_INDEX = "vera_fidei_chunks"

# Portuguese → Latin/Greek theological term expansion
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
    "amore": ["amor", "amoris", "amorem", "caritas"],
    "verdadeiro corpo": ["verum corpus", "vere corpus"],
    "presença real": ["praesentia realis", "vere et realiter"],
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def expand_theological_query(query: str) -> str:
    """Expand a Portuguese theological query with Latin/Greek equivalents for Elasticsearch."""
    q = _strip_accents(query)
    extra: list[str] = []
    for pt_term, latin_terms in _THEO_LATIN.items():
        if pt_term in q:
            extra.extend(latin_terms)
    if extra:
        # Deduplicate and append to original query
        seen = set(query.lower().split())
        new_terms = [t for t in extra if t not in seen]
        if new_terms:
            return query + " " + " ".join(dict.fromkeys(new_terms))
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
    pdf_page: int | None = None
    chapter_or_section: str | None = None
    collection: str | None = None
    volume: int | None = None
    edition_label: str | None = None
    language: str | None = None
    translation_text: str | None = None


class TextSearchClient:
    def __init__(self) -> None:
        self.es = Elasticsearch([settings.elasticsearch_url])
        self._ensure_index()

    def _ensure_index(self) -> None:
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
                    }
                }
            })

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
    ) -> dict:
        must: list = [{"multi_match": {"query": expanded_query, "fields": fields, "type": "best_fields"}}]
        should: list = []
        if author_filter:
            should.append({"match": {"author": author_filter}})
        filter_clauses: list = []
        if author_filter:
            filter_clauses.append({"term": {"author": author_filter}})
        if collection_filter == "patristica":
            filter_clauses.append({"terms": {"collection": ["PL", "PG", "PO", "PT"]}})
        return {
            "query": {
                "bool": {
                    "must": must,
                    **({"should": should} if should else {}),
                    **({"filter": filter_clauses} if filter_clauses else {}),
                }
            },
            "size": limit,
        }

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
            main_body = self._build_acervo_es_body(expanded, fields, author_filter, collection_filter, main_limit)
            resp = self.es.search(index=ES_INDEX, body=main_body)
            results = self._parse_acervo_response(resp)
        except Exception:
            return []

        seen_ids = {h.chunk_id for h in results}

        def _add_guaranteed(hits: list[AcervoSearchHit]) -> None:
            for h in hits:
                if h.chunk_id not in seen_ids:
                    results.append(h)
                    seen_ids.add(h.chunk_id)

        # Guaranteed PL/PG/PO: Latin/Greek/Oriental originals always appear
        if plpgpo_quota > 0:
            try:
                plpgpo_body = self._build_acervo_es_body(expanded, fields, "", "patristica", plpgpo_quota)
                _add_guaranteed(self._parse_acervo_response(self.es.search(index=ES_INDEX, body=plpgpo_body)))
            except Exception:
                pass

        # Guaranteed PT: Paulus Portuguese editions always appear.
        # Uses collection='PT' keyword filter and searches the ORIGINAL query (not expanded Latin),
        # because PT books have Portuguese text — expanded Latin terms don't match their content.
        if pt_quota > 0:
            try:
                pt_body = {
                    "query": {
                        "bool": {
                            "must": [{"multi_match": {
                                "query": query,  # original Portuguese query, not expanded
                                "fields": ["text^2", "translation_text"],
                                "type": "best_fields",
                            }}],
                            "filter": [{"terms": {"collection": ["PT"]}}],
                        }
                    },
                    "size": pt_quota,
                }
                _add_guaranteed(self._parse_acervo_response(self.es.search(index=ES_INDEX, body=pt_body)))
            except Exception:
                pass

        return results[:limit]

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
            ))
        return hits

    def index_chunk(self, chunk_id: int, doc: dict) -> None:
        self.es.index(index=ES_INDEX, id=str(chunk_id), document={**doc, "chunk_id": chunk_id})

    def index_chunks(self, items: list[tuple[int, dict]]) -> None:
        if not items:
            return
        actions = [
            {
                "_op_type": "index",
                "_index": ES_INDEX,
                "_id": str(chunk_id),
                "_source": {**doc, "chunk_id": chunk_id},
            }
            for chunk_id, doc in items
        ]
        bulk(self.es, actions)

    def delete_chunk(self, chunk_id: int) -> None:
        try:
            self.es.delete(index=ES_INDEX, id=str(chunk_id), ignore=[404])
        except Exception:
            pass
