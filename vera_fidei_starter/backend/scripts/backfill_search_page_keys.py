"""Add the derived PDF-page collapse key to existing Elasticsearch documents.

The operation is additive and idempotent: it never changes source text or
deletes a document. Run without ``--apply`` to inspect the pending count.
"""

from __future__ import annotations

import argparse
import json

from search.text_search import ES_INDEX, TextSearchClient


MISSING_QUERY = {
    "bool": {
        "must_not": [
            {"exists": {"field": "source_page_key"}},
        ]
    }
}


def backfill(*, apply: bool) -> dict:
    client = TextSearchClient()
    pending = int(
        client.es.count(index=ES_INDEX, query=MISSING_QUERY).get("count", 0)
    )
    result: dict = {
        "index": ES_INDEX,
        "pending_before": pending,
        "applied": apply,
    }
    if not apply or pending == 0:
        result["pending_after"] = pending
        return result

    response = client.es.options(request_timeout=600).update_by_query(
        index=ES_INDEX,
        conflicts="proceed",
        refresh=True,
        wait_for_completion=True,
        query=MISSING_QUERY,
        script={
            "lang": "painless",
            "source": """
                def chunk = ctx._source.chunk_id != null ? ctx._source.chunk_id : ctx._id;
                if (ctx._source.pdf_page == null) {
                    ctx._source.source_page_key = 'chunk:' + chunk;
                } else if (ctx._source.book_file_id != null) {
                    ctx._source.source_page_key = 'file:' + ctx._source.book_file_id + ':page:' + ctx._source.pdf_page;
                } else if (ctx._source.book_id != null) {
                    ctx._source.source_page_key = 'book:' + ctx._source.book_id + ':page:' + ctx._source.pdf_page;
                } else {
                    ctx._source.source_page_key = 'chunk:' + chunk + ':page:' + ctx._source.pdf_page;
                }
            """,
        },
    )
    result.update({
        "updated": int(response.get("updated", 0)),
        "version_conflicts": int(response.get("version_conflicts", 0)),
        "failures": response.get("failures", []),
        "pending_after": int(
            client.es.count(index=ES_INDEX, query=MISSING_QUERY).get("count", 0)
        ),
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = backfill(apply=args.apply)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if args.apply and (report.get("failures") or report.get("pending_after")):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
