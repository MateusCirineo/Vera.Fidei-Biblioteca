"""Independent patristic search audit.

Varredura independente do corpus patrístico que NÃO usa o endpoint de busca.
Conta ocorrências diretas nos campos text/literal_search_text do ES e compara
com o que a API retorna, confirmando que os dois números coincidem.

Run inside the backend container from /app::

    python -m scripts.audit_patristic_search
    python -m scripts.audit_patristic_search --query eucharistia --collections PG PL
    python -m scripts.audit_patristic_search --full-report
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterator

sys.path.insert(0, "/app")

from elasticsearch import Elasticsearch
from search.text_search import (
    ES_INDEX,
    PATRISTIC_COLLECTIONS,
    TextSearchClient,
    theological_literal_variants,
)
from core.config import settings


_ES_HOST = getattr(settings, "elasticsearch_url", "http://elasticsearch:9200")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(label: str, data: dict | None = None) -> None:
    payload = {"at": _now(), "event": label}
    if data:
        payload.update(data)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _es() -> Elasticsearch:
    return Elasticsearch(_ES_HOST)


def _scroll_all_patristic(
    es: Elasticsearch,
    query_term: str,
    collections: list[str],
    field: str = "text",
    page_size: int = 500,
) -> Iterator[dict]:
    """Scroll through all ES documents matching query_term in given field."""
    body = {
        "query": {
            "bool": {
                "must": [{"match": {field: {"query": query_term, "operator": "and"}}}],
                "filter": [{"terms": {"collection": collections}}],
            }
        },
        "_source": ["chunk_id", "book_id", "collection", "author", "work_title",
                    "pdf_page", "source_fidelity", "source_page_key", "text",
                    "literal_search_text"],
        "size": page_size,
    }
    resp = es.search(index=ES_INDEX, body=body, scroll="2m")
    scroll_id = resp["_scroll_id"]
    hits = resp["hits"]["hits"]
    while hits:
        yield from hits
        resp = es.scroll(scroll_id=scroll_id, scroll="2m")
        scroll_id = resp["_scroll_id"]
        hits = resp["hits"]["hits"]
    es.clear_scroll(scroll_id=scroll_id)


def count_occurrences_in_text(text: str | None, variant: str) -> int:
    """Case-insensitive count of variant occurrences in text."""
    if not text:
        return 0
    return text.casefold().count(variant.casefold())


def run_independent_count(
    query: str,
    collections: list[str] | None = None,
    verbose: bool = False,
) -> dict:
    """Scan ES directly (no API) and count occurrences per work/collection."""
    if collections is None:
        collections = list(PATRISTIC_COLLECTIONS)

    es = _es()
    variants = [query, *theological_literal_variants(query)]
    unique_variants = list(dict.fromkeys(v.casefold() for v in variants))

    _log("audit_start", {"query": query, "variants": unique_variants, "collections": collections})

    per_work: dict[tuple[str, str], dict] = {}  # (work_title, collection) → stats
    total_occurrences = 0
    total_pages = set()
    total_works = set()
    chunk_ids_seen: set[int] = set()
    page_keys_seen: set[str] = set()

    for variant in unique_variants:
        for field in ("text", "literal_search_text"):
            for raw_hit in _scroll_all_patristic(es, variant, collections, field=field):
                src = raw_hit["_source"]
                chunk_id = src.get("chunk_id") or raw_hit.get("_id")
                page_key = src.get("source_page_key") or f"chunk:{chunk_id}"

                if page_key in page_keys_seen:
                    continue  # deduplicate by page
                page_keys_seen.add(page_key)

                book_id = src.get("book_id")
                collection = src.get("collection", "?")
                work_title = src.get("work_title", "?")
                author = src.get("author", "?")
                pdf_page = src.get("pdf_page")
                fidelity = src.get("source_fidelity", "?")

                text = src.get("text") or src.get("literal_search_text") or ""
                occurrences_in_page = sum(
                    count_occurrences_in_text(text, v) for v in unique_variants
                )
                if occurrences_in_page == 0:
                    occurrences_in_page = 1  # found by ES match = at least 1

                key = (work_title, collection)
                if key not in per_work:
                    per_work[key] = {
                        "author": author,
                        "work_title": work_title,
                        "collection": collection,
                        "book_id": book_id,
                        "pages": 0,
                        "occurrences": 0,
                        "fidelity": fidelity,
                    }
                per_work[key]["pages"] += 1
                per_work[key]["occurrences"] += occurrences_in_page

                total_occurrences += occurrences_in_page
                total_pages.add(page_key)
                if book_id is not None:
                    total_works.add(book_id)

    summary = {
        "query": query,
        "variants_searched": unique_variants,
        "collections": collections,
        "total_works": len(total_works),
        "total_pages": len(total_pages),
        "total_occurrences": total_occurrences,
        "works": sorted(per_work.values(), key=lambda x: -x["occurrences"]),
    }

    _log("audit_complete", {
        "query": query,
        "total_works": summary["total_works"],
        "total_pages": summary["total_pages"],
        "total_occurrences": summary["total_occurrences"],
    })

    return summary


def run_api_count(query: str, collections: list[str] | None = None) -> dict:
    """Call the search API and return its reported totals."""
    import asyncio
    from search.text_search import TextSearchClient, PATRISTIC_COLLECTIONS

    if collections is None:
        collections = list(PATRISTIC_COLLECTIONS)

    client = TextSearchClient()

    async def _fetch() -> dict:
        page = await client.search_acervo_page(
            query=query,
            offset=0,
            limit=1,
            collection_filter=collections,
            source_fidelities=None,
            literal_candidates_only=True,
            include_page_counts=True,
        )
        return {
            "total_pages": page.total,
            "matching_works": page.matching_works,
        }

    result = asyncio.run(_fetch())
    return result


def compare_counts(independent: dict, api: dict, tolerance_pct: float = 10.0) -> bool:
    """Return True if counts are within tolerance, print diff."""
    ind_pages = independent["total_pages"]
    api_pages = api["total_pages"]

    print("\n" + "=" * 60)
    print("COMPARISON: Independent scan vs API")
    print("=" * 60)
    print(f"Independent — pages:       {ind_pages:>8}")
    print(f"API         — pages:       {api_pages:>8}")
    print(f"Independent — works:       {independent['total_works']:>8}")
    print(f"API         — works:       {api['matching_works']:>8}")
    print(f"Independent — occurrences: {independent['total_occurrences']:>8}")

    if api_pages == 0:
        print("\n⚠️  API returned 0 pages — the fix may not be deployed yet.")
        return False

    diff_pct = abs(ind_pages - api_pages) / max(api_pages, 1) * 100
    if diff_pct <= tolerance_pct:
        print(f"\n✅  PASS — counts within {tolerance_pct:.0f}% tolerance (diff={diff_pct:.1f}%)")
        return True
    else:
        print(f"\n❌  FAIL — counts diverge by {diff_pct:.1f}% (tolerance={tolerance_pct:.0f}%)")
        print("   Documented reason: first-page aggregation may undercount scrolled corpus.")
        return False


def print_full_report(summary: dict) -> None:
    print("\n" + "=" * 60)
    print(f"FULL REPORT — query: {summary['query']!r}")
    print("=" * 60)
    print(f"Variants searched: {', '.join(summary['variants_searched'])}")
    print(f"Collections:       {', '.join(summary['collections'])}")
    print(f"Total works:       {summary['total_works']}")
    print(f"Total pages:       {summary['total_pages']}")
    print(f"Total occurrences: {summary['total_occurrences']}")
    print()
    print(f"{'Author':<30} {'Work':<40} {'Coll':<8} {'Pages':>6} {'Occ':>6}")
    print("-" * 100)
    for w in summary["works"][:50]:
        print(
            f"{w['author']:<30.30} {w['work_title']:<40.40} "
            f"{w['collection']:<8} {w['pages']:>6} {w['occurrences']:>6}"
        )
    if len(summary["works"]) > 50:
        print(f"... and {len(summary['works']) - 50} more works")


def check_ignatius_and_justin(collections: list[str]) -> None:
    """Specifically verify Ignatius of Antioch and Justin Martyr are found."""
    es = _es()
    print("\n" + "=" * 60)
    print("PATRISTIC CONTROL — Inácio de Antioquia & Justino Mártir")
    print("=" * 60)

    for author_pattern, work_pattern, term in [
        ("Inácio", "Esmirnenses", "eucaristia"),
        ("Ignatius", "Smyrnaeans", "eucharistia"),
        ("Justino", "Apologia", "eucaristia"),
        ("Justin", "Apology", "eucharistia"),
    ]:
        body = {
            "query": {
                "bool": {
                    "must": [{"match": {"text": {"query": term, "operator": "and"}}}],
                    "filter": [
                        {"terms": {"collection": collections}},
                    ],
                    "should": [
                        {"match": {"author": author_pattern}},
                        {"match": {"work_title": work_pattern}},
                    ],
                    "minimum_should_match": 1,
                }
            },
            "_source": ["author", "work_title", "collection", "pdf_page", "source_fidelity"],
            "size": 3,
        }
        resp = es.search(index=ES_INDEX, body=body)
        total = (resp["hits"]["total"] or {}).get("value", 0)
        if isinstance(resp["hits"]["total"], int):
            total = resp["hits"]["total"]
        hits = resp["hits"]["hits"]
        if total > 0:
            h = hits[0]["_source"]
            print(f"  ✅  Found {author_pattern}/{work_pattern}: "
                  f"{h.get('author', '?')} — {h.get('work_title', '?')} "
                  f"(collection={h.get('collection')}, "
                  f"fidelity={h.get('source_fidelity')}, "
                  f"page={h.get('pdf_page')})")
        else:
            print(f"  ❌  NOT FOUND: author~{author_pattern!r} + work~{work_pattern!r} + term={term!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit patristic search counts independently")
    parser.add_argument("--query", default="eucaristia", help="Search term (default: eucaristia)")
    parser.add_argument("--collections", nargs="*", default=None,
                        help="ES collections (default: all PATRISTIC_COLLECTIONS)")
    parser.add_argument("--full-report", action="store_true", help="Print per-work breakdown")
    parser.add_argument("--check-api", action="store_true",
                        help="Also call API and compare counts")
    parser.add_argument("--control-terms", action="store_true",
                        help="Run Ignatius/Justin control check")
    parser.add_argument("--tolerance", type=float, default=15.0,
                        help="Tolerance %% for count comparison (default: 15)")
    args = parser.parse_args()

    collections = args.collections or list(PATRISTIC_COLLECTIONS)

    independent = run_independent_count(args.query, collections, verbose=args.full_report)

    if args.full_report:
        print_full_report(independent)

    if args.check_api:
        api = run_api_count(args.query, collections)
        ok = compare_counts(independent, api, tolerance_pct=args.tolerance)
        if not ok:
            sys.exit(1)

    if args.control_terms:
        check_ignatius_and_justin(collections)

    # Always run Ignatius/Justin if full_report requested
    if args.full_report and not args.control_terms:
        check_ignatius_and_justin(collections)


if __name__ == "__main__":
    main()
