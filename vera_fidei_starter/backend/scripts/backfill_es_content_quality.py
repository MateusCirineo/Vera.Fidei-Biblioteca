"""Backfill derived body/content-quality fields for public Elasticsearch docs."""

from __future__ import annotations

import argparse
import json

from elasticsearch.helpers import bulk

from models.database import Book, Chunk, SessionLocal
from search.content_quality import assess_content
from search.text_search import ES_INDEX, TextSearchClient, _strip_accents
from services.source_fidelity_service import PUBLIC_SOURCE_FIDELITIES


def run(*, batch_size: int) -> dict:
    client = TextSearchClient()
    processed = 0
    quotable = 0
    roles: dict[str, int] = {}
    with SessionLocal() as db:
        query = (
            db.query(
                Chunk.id,
                Chunk.text,
                Chunk.chapter_or_section,
                Chunk.chunk_author,
                Chunk.pdf_page,
                Chunk.extraction_method,
                Chunk.source_fidelity,
                Chunk.fidelity_score,
                Book.author,
                Book.title,
            )
            .join(Book, Chunk.book_id == Book.id)
            .filter(
                Chunk.source_fidelity.in_(PUBLIC_SOURCE_FIDELITIES),
                Chunk.text.isnot(None),
                Chunk.text != "",
            )
            .order_by(Chunk.id)
        )
        actions: list[dict] = []
        for row in query.yield_per(batch_size):
            quality = assess_content(
                row.text,
                section=row.chapter_or_section,
                author=row.chunk_author or row.author,
                work_title=row.title,
                pdf_page=row.pdf_page,
            )
            actions.append({
                "_op_type": "update",
                "_index": ES_INDEX,
                "_id": str(row.id),
                "doc": {
                    "content_role": quality.role,
                    "is_quotable": bool(quality.is_quotable),
                    "content_quality_score": quality.quality_score,
                    "extraction_method": row.extraction_method,
                    "source_fidelity": row.source_fidelity,
                    "fidelity_score": row.fidelity_score,
                    "literal_search_text": _strip_accents(row.text),
                },
            })
            processed += 1
            quotable += int(quality.is_quotable)
            roles[quality.role] = roles.get(quality.role, 0) + 1
            if len(actions) >= batch_size:
                bulk(client.es, actions, raise_on_error=True)
                actions.clear()
                if processed % max(batch_size * 5, 1) == 0:
                    print(json.dumps({
                        "event": "es_quality_progress",
                        "processed": processed,
                        "quotable": quotable,
                    }), flush=True)
        if actions:
            bulk(client.es, actions, raise_on_error=True)
        client.es.indices.refresh(index=ES_INDEX)
    return {
        "status": "ok",
        "processed": processed,
        "quotable": quotable,
        "roles": dict(sorted(roles.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    print(json.dumps(run(batch_size=max(1, args.batch_size)), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
