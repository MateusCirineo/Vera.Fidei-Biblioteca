"""Repair physical PDF page metadata without replacing chunks or embeddings.

Older imports were created before the chunker's global-offset fix. Their text is
valid, but many ``pdf_page`` values point to an early page. This command matches
the beginning of each stored chunk against the authoritative PDF text layer and
updates only page coordinates.

Dry-run (default):
    python -m scripts.repair_legacy_chunk_pages --book-id 7 --book-id 8

Apply after reviewing the JSON summary:
    python -m scripts.repair_legacy_chunk_pages --book-id 7 --book-id 8 --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

import pymupdf as fitz
from elasticsearch.helpers import bulk

sys.path.insert(0, "/app")

from models.database import Book, BookFile, Chunk, SessionLocal
from search.text_search import ES_INDEX, TextSearchClient
from storage.pdf_storage import get_pdf_storage


_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", re.UNICODE)
_ANCHOR_WIDTHS = (18, 14, 10, 8)
_ANCHOR_STARTS = (0, 4, 10, 18, 28, 40)

# Manually verified physical pages for the only ambiguous legacy chunks in
# books 7-10.  These are not guesses: each value was checked against the PDF
# text layer and the surrounding monotonic chunk sequence.  Chunk 2114 is a
# two-number duplicate from the terminal index and has no useful coordinate.
_VERIFIED_PAGE_OVERRIDES: dict[int, int | None] = {
    528: 59,
    1896: 32,
    1929: 61,
    2029: 144,
    2030: 145,
    2114: None,
}


@dataclass(frozen=True)
class PageMatch:
    page: int | None
    confidence: float
    anchor_width: int
    reason: str


def _tokens(text: str | None) -> list[str]:
    normalized = unicodedata.normalize("NFKD", (text or "").casefold())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return _WORD_RE.findall(normalized)


def _page_tokens(pdf_path: str) -> list[list[str]]:
    document = fitz.open(pdf_path)
    try:
        return [_tokens(page.get_text("text")) for page in document]
    finally:
        document.close()


def _anchor_index(pages: list[list[str]], width: int) -> dict[tuple[str, ...], set[int]]:
    index: dict[tuple[str, ...], set[int]] = defaultdict(set)
    for page_number, tokens in enumerate(pages, start=1):
        if len(tokens) < width:
            continue
        for start in range(0, len(tokens) - width + 1):
            index[tuple(tokens[start:start + width])].add(page_number)
    return index


def _match_chunk(
    chunk_tokens: list[str],
    indices: dict[int, dict[tuple[str, ...], set[int]]],
) -> PageMatch:
    if len(chunk_tokens) < min(_ANCHOR_WIDTHS):
        return PageMatch(None, 0.0, 0, "chunk_curto")

    votes: dict[int, float] = defaultdict(float)
    earliest_page: int | None = None
    best_width = 0
    exact_unique = False

    for width in _ANCHOR_WIDTHS:
        if len(chunk_tokens) < width:
            continue
        for offset in _ANCHOR_STARTS:
            if offset + width > len(chunk_tokens):
                continue
            pages = indices[width].get(tuple(chunk_tokens[offset:offset + width]), set())
            if not pages:
                continue
            weight = (width / max(_ANCHOR_WIDTHS)) * (1.0 / (1.0 + offset / 14.0))
            for page in pages:
                votes[page] += weight / len(pages)
            if len(pages) == 1:
                page = next(iter(pages))
                if earliest_page is None or offset < 10:
                    earliest_page = page
                    best_width = max(best_width, width)
                    exact_unique = exact_unique or width >= 10
        if exact_unique and best_width >= 14:
            break

    if not votes:
        return PageMatch(None, 0.0, 0, "sem_ancora_exata")

    ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
    page, score = ranked[0]
    if earliest_page is not None and votes.get(earliest_page, 0.0) >= score * 0.72:
        page = earliest_page
        score = votes[page]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = score / max(score + runner_up, 1e-9)
    confidence = min(1.0, 0.58 + 0.25 * margin + 0.17 * (best_width / max(_ANCHOR_WIDTHS)))
    return PageMatch(page, round(confidence, 4), best_width, "ancora_exata")


def _targets(book_ids: Iterable[int]) -> list[tuple[Book, BookFile]]:
    with SessionLocal() as db:
        return (
            db.query(Book, BookFile)
            .join(BookFile, BookFile.book_id == Book.id)
            .filter(Book.id.in_(sorted(set(book_ids))))
            .order_by(Book.id, BookFile.id)
            .all()
        )


def _monotonic_regressions(rows: list[dict], key: str) -> int:
    pages = [row[key] for row in rows if row.get(key) is not None]
    return sum(1 for left, right in zip(pages, pages[1:]) if right < left)


def _es_page_updates(
    text_client: TextSearchClient,
    page_by_id: dict[int, int | None],
) -> None:
    if not page_by_id:
        return
    bulk(
        text_client.es,
        [
            {
                "_op_type": "update",
                "_index": ES_INDEX,
                "_id": str(chunk_id),
                "doc": {"pdf_page": page},
            }
            for chunk_id, page in page_by_id.items()
        ],
        refresh=True,
    )
    response = text_client.es.mget(
        index=ES_INDEX,
        body={"ids": [str(chunk_id) for chunk_id in page_by_id]},
        _source_includes=["pdf_page"],
    )
    observed = {
        int(doc["_id"]): (doc.get("_source") or {}).get("pdf_page")
        for doc in response.get("docs", [])
        if doc.get("found")
    }
    mismatch = {
        chunk_id: {"expected": page, "observed": observed.get(chunk_id)}
        for chunk_id, page in page_by_id.items()
        if observed.get(chunk_id) != page
    }
    if mismatch:
        raise RuntimeError(f"Elasticsearch page verification failed: {mismatch}")


def _db_page_updates(page_by_id: dict[int, int | None]) -> None:
    """Apply and independently verify one PostgreSQL coordinate mapping."""
    if not page_by_id:
        return
    with SessionLocal() as db:
        rows = {
            chunk.id: chunk
            for chunk in db.query(Chunk).filter(Chunk.id.in_(list(page_by_id))).all()
        }
        missing = sorted(set(page_by_id) - set(rows))
        if missing:
            raise RuntimeError(f"Chunks disappeared during page repair: {missing}")
        for chunk_id, page in page_by_id.items():
            rows[chunk_id].pdf_page = page
        db.commit()

    with SessionLocal() as verify_db:
        observed = dict(
            verify_db.query(Chunk.id, Chunk.pdf_page)
            .filter(Chunk.id.in_(list(page_by_id)))
            .all()
        )
    if observed != page_by_id:
        raise RuntimeError(
            f"PostgreSQL page verification failed: expected={page_by_id}, observed={observed}"
        )


def _repair_file(
    book: Book,
    book_file: BookFile,
    *,
    apply: bool,
    clear_unmatched: bool,
    min_confidence: float,
    text_client: TextSearchClient | None,
) -> dict:
    pdf_path = get_pdf_storage().resolve_for_processing(book_file.stored_path)
    if not pdf_path:
        return {
            "book_id": book.id,
            "file_id": book_file.id,
            "title": book.title,
            "error": "pdf_indisponivel",
        }

    pages = _page_tokens(pdf_path)
    indices = {width: _anchor_index(pages, width) for width in _ANCHOR_WIDTHS}
    with SessionLocal() as db:
        chunks = (
            db.query(Chunk)
            .filter(Chunk.book_file_id == book_file.id)
            .order_by(Chunk.sequence_index.asc().nulls_last(), Chunk.id.asc())
            .all()
        )
        rows: list[dict] = []
        pending: list[tuple[int, int | None, int | None]] = []
        for chunk in chunks:
            match = _match_chunk(_tokens(chunk.text), indices)
            has_override = chunk.id in _VERIFIED_PAGE_OVERRIDES
            new_page = (
                _VERIFIED_PAGE_OVERRIDES[chunk.id]
                if has_override
                else (match.page if match.confidence >= min_confidence else None)
            )
            final_page = (
                new_page
                if new_page is not None or has_override
                else (None if clear_unmatched else chunk.pdf_page)
            )
            rows.append({
                "chunk_id": chunk.id,
                "sequence_index": chunk.sequence_index,
                "old_page": chunk.pdf_page,
                "new_page": new_page,
                "final_page": final_page,
                "confidence": match.confidence,
                "anchor_width": match.anchor_width,
                "reason": "override_verificado" if has_override else match.reason,
            })
            if final_page != chunk.pdf_page:
                pending.append((chunk.id, chunk.pdf_page, final_page))

        # Never apply a mapping that still moves backwards. It indicates an
        # ambiguous/repeated anchor and requires manual inspection.
        regressions_after = _monotonic_regressions(rows, "final_page")
        if apply and regressions_after:
            raise RuntimeError(
                f"book_id={book.id} file_id={book_file.id}: "
                f"{regressions_after} regressões permaneceram no dry-run"
            )

    if apply and pending:
        if text_client is None:
            raise RuntimeError("TextSearchClient is required in apply mode")
        old_page_by_id = {chunk_id: old_page for chunk_id, old_page, _ in pending}
        new_page_by_id = {chunk_id: new_page for chunk_id, _, new_page in pending}
        # Elasticsearch cannot participate in the PostgreSQL transaction. Both
        # sides are therefore verified after each write, and any failure runs a
        # compensating write back to the exact pre-repair coordinates.
        try:
            _es_page_updates(text_client, new_page_by_id)
            _db_page_updates(new_page_by_id)
        except Exception as original_error:
            restore_errors: list[str] = []
            try:
                _db_page_updates(old_page_by_id)
            except Exception as exc:
                restore_errors.append(f"PostgreSQL: {exc}")
            try:
                _es_page_updates(text_client, old_page_by_id)
            except Exception as exc:
                restore_errors.append(f"Elasticsearch: {exc}")
            if restore_errors:
                raise RuntimeError(
                    "Page repair failed and compensation was incomplete: "
                    + "; ".join(restore_errors)
                ) from original_error
            raise

    matched = sum(1 for row in rows if row["new_page"] is not None)
    return {
        "book_id": book.id,
        "file_id": book_file.id,
        "title": book.title,
        "pdf_pages": len(pages),
        "chunks": len(rows),
        "matched": matched,
        "unmatched": len(rows) - matched,
        "cleared_unmatched": sum(
            1 for row in rows if row["new_page"] is None and row["final_page"] is None
        ) if clear_unmatched else 0,
        "changed": len(pending),
        "regressions_before": _monotonic_regressions(rows, "old_page"),
        "regressions_after": regressions_after,
        "applied": apply,
        "sample_changes": [row for row in rows if row["old_page"] != row["final_page"]][:12],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id", type=int, action="append", required=True)
    parser.add_argument("--min-confidence", type=float, default=0.8)
    parser.add_argument(
        "--clear-unmatched",
        action="store_true",
        help=(
            "Limpar a página de chunks sem âncora confiável. Use somente em "
            "importações legadas cuja coordenada antiga já foi comprovada como incorreta."
        ),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    targets = _targets(args.book_id)
    confidence = max(0.0, min(1.0, args.min_confidence))

    # In apply mode, analyze every requested file before the first write. This
    # prevents an unsafe file near the end of the command from leaving earlier
    # books repaired only partially.
    if args.apply:
        preflight = [
            _repair_file(
                book,
                book_file,
                apply=False,
                clear_unmatched=args.clear_unmatched,
                min_confidence=confidence,
                text_client=None,
            )
            for book, book_file in targets
        ]
        preflight_failed = any(
            report.get("error") or report.get("regressions_after")
            for report in preflight
        )
        if preflight_failed:
            print(json.dumps(
                {"mode": "preflight_failed", "reports": preflight},
                ensure_ascii=False,
                indent=2,
            ))
            return 1

    text_client = TextSearchClient() if args.apply else None
    reports = [
        _repair_file(
            book,
            book_file,
            apply=args.apply,
            clear_unmatched=args.clear_unmatched,
            min_confidence=confidence,
            text_client=text_client,
        )
        for book, book_file in targets
    ]
    payload = {"mode": "apply" if args.apply else "dry_run", "reports": reports}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    has_error = any(report.get("error") or report.get("regressions_after") for report in reports)
    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
