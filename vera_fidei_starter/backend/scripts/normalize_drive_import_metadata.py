"""
Normalize metadata for Drive-imported books already present in the database.

This script is intentionally conservative: it fixes known accent/canonical-author
variants and known publisher labels for the recent Drive import without deleting
books, files, PDFs, chunks, or search indexes.

Run inside the backend container from /app:
  python -m scripts.normalize_drive_import_metadata --start-id 2105 --end-id 2135
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from models.database import Book, BookFile, SessionLocal


GENERIC_EDITIONS = {"", "Outras editoras", "Outras Editoras", "Google Drive"}

AUTHOR_NORMALIZATIONS = {
    "padre julio maria de lombaerde": "Padre Júlio Maria de Lombaerde",
    "papa sao pio v": "Papa São Pio V",
    "santo afonso maria de ligorio": "Santo Afonso Maria de Ligório",
    "santo inacio de loyola": "Santo Inácio de Loyola",
    "santo tomas de aquino": "Santo Tomás de Aquino",
    "sao tomas de aquino": "Santo Tomás de Aquino",
    "são tomas de aquino": "Santo Tomás de Aquino",
    "são tomás de aquino": "Santo Tomás de Aquino",
    "santo tomás de aquino": "Santo Tomás de Aquino",
    "sao bernardo de claraval": "São Bernardo de Claraval",
    "sao boaventura": "São Boaventura",
    "são boaventura": "São Boaventura",
    "sao leonardo de porto mauricio": "São Leonardo de Porto Maurício",
    "sao luis maria grignion de montfort": "São Luís Maria Grignion de Montfort",
    "sao roberto belarmino": "São Roberto Belarmino",
    "sao vicente de lerins": "São Vicente de Lérins",
    "boecio": "Boécio",
    "boécio": "Boécio",
    "santo agostinho": "Santo Agostinho",
    "tomas de kempis": "Tomás de Kempis",
    "tomás de kempis": "Tomás de Kempis",
}

TITLE_REPLACEMENTS = (
    ("Padre Julio Maria de Lombaerde", "Padre Júlio Maria de Lombaerde"),
    ("Papa Sao Pio V", "Papa São Pio V"),
    ("Sao Pio V", "São Pio V"),
    ("Santo Afonso Maria de Ligorio", "Santo Afonso Maria de Ligório"),
    ("Santo Inacio de Loyola", "Santo Inácio de Loyola"),
    ("Santo Tomas", "Santo Tomás"),
    ("Sao Tomas", "São Tomás"),
    ("Sao Bernardo de Claraval", "São Bernardo de Claraval"),
    ("Sao Boaventura", "São Boaventura"),
    ("Sao Leonardo de Porto Mauricio", "São Leonardo de Porto Maurício"),
    ("Sao Luis Maria Grignion de Montfort", "São Luís Maria Grignion de Montfort"),
    ("São Luis Maria Grignon de Montfort", "São Luís Maria Grignion de Montfort"),
    ("Sao Luis Maria Grignon de Montfort", "São Luís Maria Grignion de Montfort"),
    ("Sao Roberto Belarmino", "São Roberto Belarmino"),
    ("Sao Vicente de Lerins", "São Vicente de Lérins"),
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
    ("À", "À"),
    ("São", "São"),
)

PUBLISHER_RULES = (
    (("catena aurea",), "Ecclesiae"),
    (("suma contra os gentios",), "Vozes"),
    (("suma teologica",), "Loyola"),
    (("salterio a virgem maria",), "Ave-Maria"),
    (("de institutione arithmetica",), "Rodopi"),
    (("meditacoes para a quaresma",), "Permanência"),
    (("sermoes o pai nosso",), "Permanência"),
    (("questoes disputadas sobre a alma",), "Vozes"),
    (("escritos politicos",), "Vozes"),
    (("verdade e conhecimento",), "WMF Martins Fontes"),
    (("comentario ao tratado da trindade de boecio",), "Editora UNESP"),
    (("comentario a tessalonicenses",), "Concreta"),
    (("fundamentals of music",), "Yale University Press"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize(value: str | None) -> str:
    text = value or ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_author(value: str | None) -> str | None:
    if not value:
        return value
    return AUTHOR_NORMALIZATIONS.get(normalize(value), value)


def normalized_title(value: str) -> str:
    title = unicodedata.normalize("NFC", value or "")
    for old, new in TITLE_REPLACEMENTS:
        title = title.replace(old, new)
    return title


def publisher_for(book: Book) -> str | None:
    text = normalize(" ".join([
        book.title or "",
        book.canonical_title or "",
        book.edition_label or "",
        book.source_label or "",
    ]))
    for needles, publisher in PUBLISHER_RULES:
        if all(needle in text for needle in needles):
            return publisher
    return None


def should_replace_label(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip() in GENERIC_EDITIONS


def log(payload: dict) -> None:
    print(json.dumps({"at": _now(), **payload}, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-id", type=int, default=None)
    parser.add_argument("--end-id", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    changed_books = 0
    changed_files = 0

    with SessionLocal() as db:
        query = db.query(Book).order_by(Book.id.asc())
        if args.start_id is not None:
            query = query.filter(Book.id >= args.start_id)
        if args.end_id is not None:
            query = query.filter(Book.id <= args.end_id)

        books = query.all()
        for book in books:
            changes: dict[str, tuple[str | None, str | None]] = {}

            new_author = canonical_author(book.author)
            if new_author != book.author:
                changes["author"] = (book.author, new_author)
                book.author = new_author

            new_canonical_author = canonical_author(book.canonical_author)
            if new_canonical_author != book.canonical_author:
                changes["canonical_author"] = (book.canonical_author, new_canonical_author)
                book.canonical_author = new_canonical_author

            new_title = normalized_title(book.title)
            if new_title != book.title:
                changes["title"] = (book.title, new_title)
                book.title = new_title

            if book.canonical_title:
                new_canonical_title = normalized_title(book.canonical_title)
                if new_canonical_title != book.canonical_title:
                    changes["canonical_title"] = (book.canonical_title, new_canonical_title)
                    book.canonical_title = new_canonical_title

            if book.source_label:
                new_source_label = normalized_title(book.source_label)
                if new_source_label != book.source_label:
                    changes["source_label"] = (book.source_label, new_source_label)
                    book.source_label = new_source_label

            publisher = publisher_for(book)
            if publisher and should_replace_label(book.edition_label):
                changes["edition_label"] = (book.edition_label, publisher)
                book.edition_label = publisher

            file_changes = []
            if publisher:
                files = db.query(BookFile).filter(BookFile.book_id == book.id).all()
                for book_file in files:
                    if should_replace_label(book_file.editor):
                        file_changes.append((book_file.id, book_file.editor, publisher))
                        book_file.editor = publisher

            if changes or file_changes:
                changed_books += 1 if changes else 0
                changed_files += len(file_changes)
                log({
                    "event": "metadata_update",
                    "book_id": book.id,
                    "changes": changes,
                    "file_changes": file_changes,
                })

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    log({
        "event": "summary",
        "changed_books": changed_books,
        "changed_files": changed_files,
        "dry_run": args.dry_run,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
