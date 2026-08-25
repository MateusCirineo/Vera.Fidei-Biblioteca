"""Quarantine text-layer-only chunks for selected source languages.

The operation is intentionally one-way at runtime: it never promotes text.
Use a PostgreSQL backup to restore old metadata if needed. Run from /app::

    python -m scripts.enforce_visual_fidelity_gate --language la --language latim
    python -m scripts.enforce_visual_fidelity_gate --language la --language latim --apply
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone

from models.database import Book, Chunk, SessionLocal, init_db
from search.text_search import ES_INDEX, TextSearchClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _book_ids(languages: list[str]) -> list[int]:
    accepted = {value.strip().casefold() for value in languages if value.strip()}
    with SessionLocal() as db:
        return [
            book_id
            for book_id, language in db.query(Book.id, Book.language).all()
            if (language or "").casefold() in accepted
        ]


def _counts(book_ids: list[int]) -> dict[str, int]:
    if not book_ids:
        return {}
    with SessionLocal() as db:
        rows = (
            db.query(Book.language, Chunk.id)
            .join(Chunk, Chunk.book_id == Book.id)
            .filter(Chunk.book_id.in_(book_ids), Chunk.source_fidelity == "source_text")
            .all()
        )
    return dict(sorted(Counter(language or "unknown" for language, _id in rows).items()))


def enforce(apply: bool, languages: list[str]) -> dict:
    init_db()
    book_ids = _book_ids(languages)
    before = _counts(book_ids)
    result = {
        "created_at": _now(),
        "apply": apply,
        "languages": sorted({value.casefold() for value in languages}),
        "books": len(book_ids),
        "source_text_chunks_before": sum(before.values()),
        "by_language": before,
    }
    if not apply:
        result["status"] = "dry_run"
        return result

    with SessionLocal() as db:
        rows = (
            db.query(Chunk)
            .filter(Chunk.book_id.in_(book_ids), Chunk.source_fidelity == "source_text")
            .all()
            if book_ids else []
        )
        for chunk in rows:
            if chunk.extraction_method in {"digital_text", "digital_text_audited"}:
                chunk.extraction_method = "digital_text_candidate"
            chunk.source_fidelity = "unverified"
            chunk.fidelity_score = None
            chunk.fidelity_reasons = (
                "text-layer match only; visible PDF wording requires page-level visual verification"
            )
        db.commit()
        changed = len(rows)

    # PostgreSQL is the public authority and is already fail-closed. Keep the
    # lexical metadata consistent as well; a failure here cannot reopen text.
    es_status = "updated"
    try:
        client = TextSearchClient()
        client.es.update_by_query(
            index=ES_INDEX,
            conflicts="proceed",
            refresh=True,
            body={
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"source_fidelity": "source_text"}},
                            {"terms": {"book_id": book_ids}},
                        ]
                    }
                },
                "script": {
                    "lang": "painless",
                    "source": (
                        "ctx._source.source_fidelity = 'unverified'; "
                        "ctx._source.fidelity_score = null; "
                        "ctx._source.extraction_method = 'digital_text_candidate'; "
                        "ctx._source.is_quotable = false;"
                    ),
                },
            },
        )
    except Exception as exc:
        es_status = f"warning: {type(exc).__name__}: {exc}"

    after = _counts(book_ids)
    result.update({
        "status": "applied_fail_closed",
        "changed_chunks": changed,
        "source_text_chunks_after": sum(after.values()),
        "elasticsearch": es_status,
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--language", action="append", default=[])
    args = parser.parse_args()
    languages = args.language or ["la", "latim"]
    print(json.dumps(enforce(args.apply, languages), ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
