"""Full patristic search audit.

Produces SEARCH_AUDIT.md + search-audit/ artifacts, runs Inácio/Justino
individual audit, counts eucharist variants independently in DB text.

Run inside the backend container:

    python /app/scripts/audit_full_patristic.py --output /tmp/audit-output
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from elasticsearch import Elasticsearch
from models.database import Book, Chunk, SessionLocal
from search.text_search import ES_INDEX, PATRISTIC_COLLECTIONS, TextSearchClient, theological_literal_variants


_ES_HOST = "http://elasticsearch:9200"

AUTHOR_VARIANTS: dict[str, list[str]] = {
    "Inácio de Antioquia": [
        "Inácio de Antioquia",
        "Santo Inácio de Antioquia",
        "Ignatius of Antioch",
        "Ignatius Antiochenus",
        "Ignatius",
        "Padres Apostólicos",
    ],
    "Justino Mártir": [
        "Justino Mártir",
        "São Justino Mártir",
        "Justin Martyr",
        "Iustinus Martyr",
        "Justinus Martyr",
    ],
    "Gregório de Nissa": [
        "Gregório de Nissa",
        "Gregory of Nyssa",
        "Gregorius Nyssenus",
    ],
    "Agostinho": ["Agostinho", "Augustine", "Augustinus", "Santo Agostinho"],
    "Irineu de Lião": [
        "Irineu de Lião",
        "Irenaeus of Lyons",
        "Irenaeus",
        "Santo Irineu de Lião",
    ],
    "Tertuliano": ["Tertuliano", "Tertullian", "Tertullianus"],
    "Cirilo de Jerusalém": [
        "Cirilo de Jerusalém",
        "Cyril of Jerusalem",
        "Cyrillus Hierosolymitanus",
    ],
    "Ambrósio": ["Ambrósio", "Ambrose", "Ambrosius"],
}

EUCHARIST_VARIANTS: list[tuple[str, str]] = [
    ("eucaristia",     "NFD+casefold"),
    ("eucharistia",    "NFD+casefold"),
    ("eucharist",      "NFD+casefold"),
    ("eucharistic",    "NFD+casefold"),
    ("eucharisticus",  "NFD+casefold"),
    ("eucarístico",    "NFD+casefold"),
    ("eucarística",    "NFD+casefold"),
    ("eucharistiam",   "NFD+casefold"),
    ("eucharistiae",   "NFD+casefold"),
    ("εὐχαριστία",    "NFD+casefold+original"),
    ("Εὐχαριστία",    "NFD+casefold+original"),
    ("ευχαριστια",    "NFD+casefold"),
    ("εὐχαριστίας",   "NFD+casefold+original"),
    ("εὐχαριστίᾳ",   "NFD+casefold+original"),
    ("εὐχαριστεῖν",  "NFD+casefold+original"),
]


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nfd(text: str) -> str:
    d = unicodedata.normalize("NFD", text)
    return "".join(c for c in d if not unicodedata.combining(c)).casefold()


def _es() -> Elasticsearch:
    return Elasticsearch(_ES_HOST)


def _pat_colls() -> list[str]:
    return list(PATRISTIC_COLLECTIONS)


# ─── 1. Per-author lookup ─────────────────────────────────────────────────────

def _wildcard_author_query(alias: str, colls: list[str]) -> dict:
    pat = f"*{alias}*"
    return {
        "bool": {
            "should": [
                {"wildcard": {"author": {"value": pat, "case_insensitive": True}}},
                {"wildcard": {"work_title": {"value": pat, "case_insensitive": True}}},
                {"wildcard": {"text": {"value": pat, "case_insensitive": True}}},
            ],
            "minimum_should_match": 1,
            "filter": [{"terms": {"collection": colls}}],
        }
    }


def audit_authors(es: Elasticsearch, colls: list[str]) -> list[dict]:
    rows = []
    for canon, aliases in AUTHOR_VARIANTS.items():
        with SessionLocal() as db:
            for alias in aliases:
                like = f"%{alias}%"
                books = (
                    db.query(Book)
                    .filter(
                        (Book.author.ilike(like))
                        | (Book.canonical_author.ilike(like))
                        | (Book.title.ilike(like))
                        | (Book.canonical_title.ilike(like))
                    )
                    .all()
                )
                for book in books:
                    chunks = db.query(Chunk).filter(Chunk.book_id == book.id).all()
                    chunk_count = len(chunks)
                    char_count = sum(len(c.text or "") for c in chunks)
                    pages_set = {c.pdf_page for c in chunks if c.pdf_page is not None}
                    fidelity_dist = {}
                    for c in chunks:
                        f = c.source_fidelity or "unverified"
                        fidelity_dist[f] = fidelity_dist.get(f, 0) + 1
                    # ES indexing status
                    r = es.count(index=ES_INDEX, body={"query": {"term": {"book_id": book.id}}})
                    es_count = r.get("count", 0)
                    rows.append({
                        "canon": canon,
                        "alias_found": alias,
                        "book_id": book.id,
                        "title": book.title,
                        "canonical_title": book.canonical_title,
                        "author": book.author,
                        "canonical_author": book.canonical_author,
                        "collection": book.collection,
                        "language": book.language,
                        "library_section": book.library_section,
                        "chunk_count": chunk_count,
                        "char_count": char_count,
                        "pages_extracted": len(pages_set),
                        "es_indexed": es_count,
                        "fidelity_dist": json.dumps(fidelity_dist),
                        "obs": "",
                    })
        # ES-only search (not in books table)
        r = es.search(
            index=ES_INDEX,
            body={
                "query": {
                    "bool": {
                        "should": [
                            {"wildcard": {"author": {"value": f"*{a}*", "case_insensitive": True}}}
                            for a in aliases
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "size": 0,
                "aggs": {"books": {"terms": {"field": "book_id", "size": 20}}},
            },
        )
        es_book_ids = {b["key"] for b in r["aggregations"]["books"]["buckets"]}
        already = {row["book_id"] for row in rows if row["canon"] == canon}
        if not (es_book_ids - already) and not es_book_ids:
            rows.append({
                "canon": canon,
                "alias_found": "NENHUM",
                "book_id": "null",
                "title": "null",
                "canonical_title": "null",
                "author": "null",
                "canonical_author": "null",
                "collection": "null",
                "language": "null",
                "library_section": "null",
                "chunk_count": 0,
                "char_count": 0,
                "pages_extracted": 0,
                "es_indexed": 0,
                "fidelity_dist": "{}",
                "obs": "Não encontrado em nenhuma tabela ou índice",
            })
    return rows


# ─── 2. Eucharist variant count ───────────────────────────────────────────────

def _count_variant_in_db(term: str, colls: list[str]) -> dict:
    """Count per-page occurrences in DB text fields, deduplicating by (book_id, pdf_page)."""
    term_lower = _nfd(term)
    # Try both stripped and original
    original_lower = term.casefold()
    search_terms = list({term_lower, original_lower})

    with SessionLocal() as db:
        books_in_colls = {
            b.id for b in db.query(Book.id, Book.collection).all()
            if (b.collection or "") in set(colls)
        }
        if not books_in_colls:
            return {
                "term": term,
                "pages": 0, "literal_occurrences": 0, "works": 0,
                "body": 0, "notes": 0, "intro": 0, "editorial": 0, "uncl": 0,
            }
        chunks = (
            db.query(Chunk.id, Chunk.book_id, Chunk.pdf_page,
                     Chunk.text, Chunk.source_fidelity, Chunk.chapter_or_section)
            .filter(Chunk.book_id.in_(books_in_colls))
            .all()
        )

    # Reconstruct canonical page text (deduplicate by book_id + pdf_page)
    page_texts: dict[tuple[int, int | None], list[str]] = {}
    page_meta: dict[tuple[int, int | None], str] = {}
    for c in chunks:
        key = (c.book_id, c.pdf_page)
        page_texts.setdefault(key, []).append(c.text or "")
        page_meta.setdefault(key, c.source_fidelity or "unverified")

    total_occurrences = 0
    matching_pages: set[tuple[int, int | None]] = set()
    matching_works: set[int] = set()
    by_role = {"body": 0, "notes": 0, "intro": 0, "editorial": 0, "uncl": 0}

    for key, texts in page_texts.items():
        page_text = " ".join(texts)
        page_norm = _nfd(page_text)
        page_orig = page_text.casefold()
        count = 0
        for t in search_terms:
            if " " in t:
                count += page_norm.count(t) + page_orig.count(t)
            else:
                count += len(re.findall(rf"(?<!\w){re.escape(t)}(?!\w)", page_norm))
                if t != term_lower:
                    count += len(re.findall(rf"(?<!\w){re.escape(t)}(?!\w)", page_orig))
        count = min(count, page_norm.count(term_lower) + 50)  # cap dedup errors
        if count > 0:
            matching_pages.add(key)
            matching_works.add(key[0])
            total_occurrences += count
            fid = page_meta[key]
            if fid in ("source_text", "verified"):
                by_role["body"] += count
            elif fid == "unverified_ocr":
                by_role["editorial"] += count
            else:
                by_role["uncl"] += count

    return {
        "term": term,
        "pages": len(matching_pages),
        "literal_occurrences": total_occurrences,
        "works": len(matching_works),
        "body": by_role["body"],
        "notes": by_role["notes"],
        "intro": by_role["intro"],
        "editorial": by_role["editorial"],
        "uncl": by_role["uncl"],
    }


def audit_variants(colls: list[str]) -> list[dict]:
    results = []
    print("Counting eucharist variants in DB...", flush=True)
    for term, mode in EUCHARIST_VARIANTS:
        row = _count_variant_in_db(term, colls)
        row["normalization"] = mode
        results.append(row)
        print(f"  {term}: pages={row['pages']} occ={row['literal_occurrences']} works={row['works']}", flush=True)
    return results


# ─── 3. Inácio / Justino individual audit ─────────────────────────────────────

def audit_ignatius_justin(es: Elasticsearch) -> str:
    lines: list[str] = []
    lines.append("# Auditoria: Inácio de Antioquia & Justino Mártir\n")
    lines.append(f"Gerado: {_ts()}\n")

    eu_terms = ["eucaristia", "eucharistia", "εὐχαριστία", "ευχαριστια", "eucharist", "eucharistiam", "eucharistiae"]

    for canon_name, book_id, alias_list in [
        ("Santo Inácio de Antioquia", 2090, ["Inácio de Antioquia", "Ignatius", "Padres Apostólicos"]),
        ("São Justino Mártir", 10, ["Justino Mártir", "Justin Martyr", "Iustinus Martyr"]),
    ]:
        lines.append(f"\n## {canon_name}\n")
        with SessionLocal() as db:
            book = db.query(Book).filter(Book.id == book_id).first()
            if not book:
                lines.append(f"**ERRO**: book_id={book_id} não encontrado no banco.\n")
                continue

            chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.id).all()
            fid_dist: dict[str, int] = {}
            for c in chunks:
                f = c.source_fidelity or "unverified"
                fid_dist[f] = fid_dist.get(f, 0) + 1
            pages_set = sorted({c.pdf_page for c in chunks if c.pdf_page})
            char_total = sum(len(c.text or "") for c in chunks)

        lines.append(f"- **book_id**: {book_id}\n")
        lines.append(f"- **title**: {book.title}\n")
        lines.append(f"- **author**: {book.author}\n")
        lines.append(f"- **collection**: {book.collection}\n")
        lines.append(f"- **language**: {book.language}\n")
        lines.append(f"- **library_section**: {book.library_section}\n")
        lines.append(f"- **chunks**: {len(chunks)}\n")
        lines.append(f"- **fidelity_dist**: {fid_dist}\n")
        lines.append(f"- **pages_extracted**: {len(pages_set)} (range: {min(pages_set) if pages_set else 'N/A'}–{max(pages_set) if pages_set else 'N/A'})\n")
        lines.append(f"- **char_total**: {char_total:,}\n")

        # ES indexed count
        r = es.count(index=ES_INDEX, body={"query": {"term": {"book_id": book_id}}})
        lines.append(f"- **es_indexed_chunks**: {r.get('count', 0)}\n")

        # Eucharist terms
        lines.append("\n### Termos eucarísticos presentes\n")
        lines.append("| Termo | Páginas | Ocorrências |\n")
        lines.append("|-------|---------|-------------|\n")
        with SessionLocal() as db:
            bchunks = db.query(Chunk).filter(Chunk.book_id == book_id).all()
        for term in eu_terms:
            term_n = _nfd(term)
            term_o = term.casefold()
            pages_found: set[int | None] = set()
            total_occ = 0
            for c in bchunks:
                text = c.text or ""
                text_n = _nfd(text)
                text_o = text.casefold()
                cnt = len(re.findall(rf"(?<!\w){re.escape(term_n)}(?!\w)", text_n))
                if term_o != term_n:
                    cnt += len(re.findall(rf"(?<!\w){re.escape(term_o)}(?!\w)", text_o))
                if cnt > 0:
                    pages_found.add(c.pdf_page)
                    total_occ += cnt
            if total_occ > 0:
                pages_str = ", ".join(str(p) for p in sorted(p for p in pages_found if p) if p)
                lines.append(f"| `{term}` | {pages_str} | {total_occ} |\n")

        # Context samples
        lines.append("\n### Amostras de texto\n")
        with SessionLocal() as db:
            sample_chunks = (
                db.query(Chunk)
                .filter(Chunk.book_id == book_id, Chunk.source_fidelity.in_(["source_text", "verified"]))
                .order_by(Chunk.id)
                .limit(3)
                .all()
            )
        for c in sample_chunks:
            snippet = (c.text or "")[:300].replace("\n", " ")
            lines.append(f"\n**chunk_id={c.id} page={c.pdf_page} fidelity={c.source_fidelity}**\n")
            lines.append(f"> {snippet}...\n")

        # ES query check
        lines.append("\n### Resultado na busca ES\n")
        r2 = es.search(index=ES_INDEX, body={
            "query": {"bool": {
                "must": [{"bool": {"should": [
                    {"match": {"text": {"query": "eucaristia", "operator": "and"}}},
                    {"match": {"literal_search_text": {"query": "eucaristia", "operator": "and"}}},
                    {"match": {"text": {"query": "eucharistia", "operator": "and"}}},
                    {"match": {"literal_search_text": {"query": "eucharistia", "operator": "and"}}},
                ], "minimum_should_match": 1}}],
                "filter": [{"term": {"book_id": book_id}}],
            }},
            "size": 5,
            "_source": ["pdf_page", "source_fidelity", "is_quotable", "author"],
        })
        total_es = r2["hits"]["total"]["value"]
        lines.append(f"- Hits ES para eucaristia/eucharistia: **{total_es}**\n")
        for h in r2["hits"]["hits"]:
            s = h["_source"]
            lines.append(f"  - chunk_id={h['_id']} page={s.get('pdf_page')} fidelity={s.get('source_fidelity')} is_quotable={s.get('is_quotable')}\n")

    return "".join(lines)


# ─── 4. Search summary ────────────────────────────────────────────────────────

def audit_search_summary(es: Elasticsearch) -> dict:
    client = TextSearchClient()
    page = client.search_acervo_page(
        query="eucaristia",
        offset=0,
        limit=1,
        collection_filter="patristica",
        source_fidelities=None,
        literal_candidates_only=True,
    )

    # Count verified/source_text
    r_verified = es.search(index=ES_INDEX, body={
        "query": {"bool": {
            "must": [{"bool": {"should": [
                {"match": {"literal_search_text": {"query": v, "operator": "and"}}}
                for v in ["eucaristia", "eucharistia", "eucharist"]
            ] + [
                {"match": {"text": {"query": v, "operator": "and"}}}
                for v in ["eucaristia", "eucharistia", "eucharist"]
            ], "minimum_should_match": 1}}],
            "filter": [
                {"terms": {"collection": list(PATRISTIC_COLLECTIONS)}},
                {"terms": {"source_fidelity": ["source_text", "verified"]}},
            ],
        }},
        "size": 0,
        "aggs": {
            "pages": {"cardinality": {"field": "source_page_key", "precision_threshold": 10000}},
            "works": {"cardinality": {"field": "book_id", "precision_threshold": 10000}},
        },
    })

    return {
        "generated_at": _ts(),
        "query": "eucaristia",
        "explanation": {
            "total_matching_pages_415": {
                "value": page.total,
                "source": "ES cardinality aggregation on source_page_key, ALL fidelity levels",
                "includes": "source_text, verified, unverified, unverified_ocr",
                "note": "Counts pages where ANY eucaristia variant matches, before quality gate",
            },
            "total_matching_works_69": {
                "value": page.matching_works,
                "source": "ES cardinality aggregation on book_id, ALL fidelity levels",
                "note": "Works where any page matches, including Migne PG/PL/PO OCR volumes",
            },
            "readable_cards_9": {
                "value": "9 (pre-promotion) → now based on verified/source_text content",
                "source": "Frontend filter: source_fidelity !== 'unverified_ocr' && text.trim()",
                "real_count": r_verified["aggregations"]["pages"]["value"],
                "real_works": r_verified["aggregations"]["works"]["value"],
                "note": "Only verified/source_text chunks appear as Trecho da Obra cards",
            },
            "false_254_trechos": {
                "value": 254,
                "source": "BUG: showMoreContentResults() sets contentReadableTotal(combined.length)",
                "correct_should_be": "combined.filter(hit => hit.source_fidelity !== 'unverified_ocr' && hit.text.trim()).length",
                "note": "After auto-loading all OCR locator pages, combined.length includes locators",
            },
        },
        "verified_readable": {
            "pages": r_verified["aggregations"]["pages"]["value"],
            "works": r_verified["aggregations"]["works"]["value"],
        },
        "es_totals": {
            "candidate_pages": page.total,
            "matching_works": page.matching_works,
        },
        "pagination": {
            "frontend_limit": 200,
            "backend_batch_size": 120,
            "auto_load_behavior": "patristica auto-loads all cursor pages silently",
            "issue": "No page navigation shown; all results fetched silently; only readable cards rendered",
        },
        "definitions": {
            "totalMatchingWorks": "Works where any page has a matching ES hit (ANY fidelity)",
            "totalMatchingPages": "Unique pages (source_page_key) with any matching ES hit",
            "totalOccurrences": "Not directly exposed; counted per-page in DB scan",
            "returnedItems": "Results returned by API (readable + locators combined)",
            "readableItems": "Subset of returnedItems with source_fidelity != unverified_ocr",
            "pageSize": "200 for patristica, 36 for all",
        },
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(Path(tempfile.gettempdir()) / "vera_fidei_audit_output"),
        help="Output directory",
    )
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    es = _es()
    colls = _pat_colls()

    print(f"[{_ts()}] Starting full patristic audit → {args.output}")

    # 1. Author audit
    print("[1/4] Auditing authors...")
    author_rows = audit_authors(es, colls)
    authors_csv = os.path.join(args.output, "authors.csv")
    fields = [
        "canon", "alias_found", "book_id", "title", "canonical_title",
        "author", "canonical_author", "collection", "language", "library_section",
        "chunk_count", "char_count", "pages_extracted", "es_indexed", "fidelity_dist", "obs",
    ]
    with open(authors_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(author_rows)
    print(f"  → {authors_csv} ({len(author_rows)} rows)")

    # 2. Variant count
    print("[2/4] Counting eucharist variants in DB...")
    variant_rows = audit_variants(colls)
    variants_csv = os.path.join(args.output, "eucharist-variants.csv")
    with open(variants_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["term", "normalization", "pages", "literal_occurrences", "works", "body", "notes", "intro", "editorial", "uncl"])
        w.writeheader()
        w.writerows(variant_rows)
    print(f"  → {variants_csv}")

    # 3. Inácio / Justino
    print("[3/4] Detailed Inácio/Justino audit...")
    ij_md = audit_ignatius_justin(es)
    ij_path = os.path.join(args.output, "ignatius-justin.md")
    with open(ij_path, "w", encoding="utf-8") as f:
        f.write(ij_md)
    print(f"  → {ij_path}")

    # 4. Search summary JSON
    print("[4/4] Building search summary...")
    summary = audit_search_summary(es)
    summary_path = os.path.join(args.output, "search-summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  → {summary_path}")

    # Print variant table to stdout
    print("\n=== EUCHARIST VARIANT TABLE ===")
    print(f"{'Termo':<25} {'Páginas':>8} {'Occ':>8} {'Obras':>6} {'Corpo':>7} {'OCR':>7}")
    print("-" * 65)
    total_pages = set()
    total_works = set()
    total_occ = 0
    for row in variant_rows:
        print(f"{row['term']:<25} {row['pages']:>8} {row['literal_occurrences']:>8} {row['works']:>6} {row['body']:>7} {row['editorial']:>7}")
        total_occ += row["literal_occurrences"]
    print(f"\nTotal occurrences (may overlap between terms): {total_occ}")

    print("\n=== AUTHOR SUMMARY ===")
    by_canon: dict[str, list] = {}
    for r in author_rows:
        by_canon.setdefault(r["canon"], []).append(r)
    print(f"{'Autor':<25} {'Obras':>6} {'Chunks':>8} {'ES idx':>8} {'Prob'}")
    print("-" * 70)
    for canon, rows in by_canon.items():
        real_rows = [r for r in rows if r["book_id"] != "null"]
        total_chunks = sum(r["chunk_count"] for r in real_rows)
        total_es = sum(r["es_indexed"] for r in real_rows)
        n_books = len({r["book_id"] for r in real_rows})
        prob = "" if real_rows else "NÃO ENCONTRADO"
        print(f"{canon:<25} {n_books:>6} {total_chunks:>8} {total_es:>8}  {prob}")

    print(f"\n[{_ts()}] Audit complete.")


if __name__ == "__main__":
    main()
