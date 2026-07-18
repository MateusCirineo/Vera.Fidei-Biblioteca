"""
Normalize display accents and title casing in catalog metadata.

This updates Book/Chunk database fields and refreshes the Elasticsearch metadata
used by the citation verifier. It is intentionally conservative: only known
Portuguese Catholic names/titles are changed.

Run inside the backend container:
  python -m scripts.normalize_catalog_accents
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from models.database import Book, Chunk, SessionLocal
from search.text_search import ES_INDEX, TextSearchClient


AUTHOR_EXACT = {
    "padre julio maria de lombaerde": "Padre Júlio Maria de Lombaerde",
    "papa sao pio v": "Papa São Pio V",
    "santo afonso maria de ligorio": "Santo Afonso Maria de Ligório",
    "santo inacio de loyola": "Santo Inácio de Loyola",
    "sao bernardo de claraval": "São Bernardo de Claraval",
    "sao leonardo de porto mauricio": "São Leonardo de Porto Maurício",
    "sao luis maria grignion de montfort": "São Luís Maria Grignion de Montfort",
    "sao roberto belarmino": "São Roberto Belarmino",
    "sao vicente de lerins": "São Vicente de Lérins",
    "santo tomas de aquino": "Santo Tomás de Aquino",
    "sao tomas de aquino": "Santo Tomás de Aquino",
    "sao boaventura": "São Boaventura",
    "boecio": "Boécio",
    "tomas de kempis": "Tomás de Kempis",
}

TEXT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Padre Julio Maria de Lombaerde", "Padre Júlio Maria de Lombaerde"),
    ("Papa Sao Pio V", "Papa São Pio V"),
    ("Sao Pio V", "São Pio V"),
    ("Santo Afonso Maria de Ligorio", "Santo Afonso Maria de Ligório"),
    ("Santo Inacio de Loyola", "Santo Inácio de Loyola"),
    ("Sao Bernardo de Claraval", "São Bernardo de Claraval"),
    ("Sao Leonardo de Porto Mauricio", "São Leonardo de Porto Maurício"),
    ("Sao Luis Maria Grignion de Montfort", "São Luís Maria Grignion de Montfort"),
    ("São Luis Maria Grignon de Montfort", "São Luís Maria Grignion de Montfort"),
    ("Sao Luis Maria Grignon de Montfort", "São Luís Maria Grignion de Montfort"),
    ("Sao Roberto Belarmino", "São Roberto Belarmino"),
    ("Sao Vicente de Lerins", "São Vicente de Lérins"),
    ("Santo Tomas de Aquino", "Santo Tomás de Aquino"),
    ("Sao Tomas de Aquino", "São Tomás de Aquino"),
    ("Sao Boaventura", "São Boaventura"),
    ("Tomas de Aquino", "Tomás de Aquino"),
    ("Tomas de Kempis", "Tomás de Kempis"),
    ("Boecio", "Boécio"),
    ("Comentario", "Comentário"),
    ("Meditacoes", "Meditações"),
    ("Questoes", "Questões"),
    ("Teologica", "Teológica"),
    ("teologica", "teológica"),
    ("Magisterio", "Magistério"),
    ("pontificio", "pontifício"),
    ("Salterio", "Saltério"),
    ("Saltério À", "Saltério à"),
    ("Contra Os Gentios", "contra os Gentios"),
)

TITLE_EXACT = {
    "suma contra os gentios livro 1": "Suma contra os Gentios - Livro 1",
    "suma contra os gentios livro 2": "Suma contra os Gentios - Livro 2",
    "suma contra os gentios livro 3": "Suma contra os Gentios - Livro 3",
    "suma contra os gentios livro 4": "Suma contra os Gentios - Livro 4",
    "comentario a tessalonicenses tomas de aquino": "Comentário a Tessalonicenses - Tomás de Aquino",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_person(value: str | None) -> str | None:
    if not value:
        return value
    exact = AUTHOR_EXACT.get(_key(value))
    if exact:
        return exact
    return normalize_text(value)


def normalize_title(value: str | None) -> str | None:
    if not value:
        return value
    exact = TITLE_EXACT.get(_key(value))
    if exact:
        return exact
    return normalize_text(value)


def normalize_text(value: str | None) -> str | None:
    if not value:
        return value
    text = unicodedata.normalize("NFC", value)
    for old, new in TEXT_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def _log(payload: dict) -> None:
    print(json.dumps({"at": _now(), **payload}, ensure_ascii=False), flush=True)


def _refresh_es_book_metadata(
    client: TextSearchClient,
    book_id: int,
    author: str | None,
    title: str | None,
    edition_label: str | None,
) -> None:
    client.es.update_by_query(
        index=ES_INDEX,
        body={
            "script": {
                "source": (
                    "ctx._source.author = params.author; "
                    "ctx._source.work_title = params.work_title; "
                    "ctx._source.edition_label = params.edition_label;"
                ),
                "lang": "painless",
                "params": {
                    "author": author,
                    "work_title": title,
                    "edition_label": edition_label,
                },
            },
            "query": {"term": {"book_id": book_id}},
        },
        conflicts="proceed",
        refresh=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-es", action="store_true")
    args = parser.parse_args()

    changed_books = 0
    changed_chunks = 0
    es_updates = 0
    changed_book_ids: set[int] = set()

    with SessionLocal() as db:
        for book in db.query(Book).order_by(Book.id.asc()).all():
            changes: dict[str, tuple[str | None, str | None]] = {}

            updates = {
                "title": normalize_title(book.title),
                "canonical_title": normalize_title(book.canonical_title),
                "author": normalize_person(book.author),
                "canonical_author": normalize_person(book.canonical_author),
                "pope": normalize_person(book.pope),
                "edition_label": normalize_text(book.edition_label),
                "source_label": normalize_text(book.source_label),
            }

            for attr, new_value in updates.items():
                old_value = getattr(book, attr)
                if new_value != old_value:
                    setattr(book, attr, new_value)
                    changes[attr] = (old_value, new_value)

            if changes:
                changed_books += 1
                changed_book_ids.add(book.id)
                _log({"event": "book_update", "book_id": book.id, "changes": changes})

        for chunk in db.query(Chunk).filter(Chunk.chunk_author.isnot(None)).all():
            new_author = normalize_person(chunk.chunk_author)
            if new_author != chunk.chunk_author:
                _log({
                    "event": "chunk_author_update",
                    "chunk_id": chunk.id,
                    "book_id": chunk.book_id,
                    "old": chunk.chunk_author,
                    "new": new_author,
                })
                chunk.chunk_author = new_author
                changed_chunks += 1
                changed_book_ids.add(chunk.book_id)

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    if changed_book_ids and not args.dry_run and not args.no_es:
        client = TextSearchClient()
        with SessionLocal() as db:
            for book_id in sorted(changed_book_ids):
                book = db.get(Book, book_id)
                if not book:
                    continue
                _refresh_es_book_metadata(
                    client,
                    book.id,
                    book.canonical_author or book.author,
                    book.canonical_title or book.title,
                    book.edition_label,
                )
                es_updates += 1

    _log({
        "event": "summary",
        "changed_books": changed_books,
        "changed_chunks": changed_chunks,
        "es_books_refreshed": es_updates,
        "dry_run": args.dry_run,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
