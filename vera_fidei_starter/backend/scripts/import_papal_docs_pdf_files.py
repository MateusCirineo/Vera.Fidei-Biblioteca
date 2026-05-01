from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from models.database import Book, BookFile, SessionLocal, init_db


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PDF_ROOT = BACKEND_DIR / "pdfs" / "documentos_pontificios"
SOURCE_LABEL = "Vatican.va"
COLLECTION = "MAG"
LIBRARY_SECTION = "documentos"

TYPE_FOLDERS = {
    "Enciclicas": "enciclica",
    "Cartas Apostolicas": "carta_apostolica",
    "Bulas Papais": "bula",
    "Constituicoes Apostolicas": "constituicao_apostolica",
    "Motu Proprio": "motu_proprio",
    "Exortacoes Apostolicas": "exortacao_apostolica",
}

POPE_ALIASES = {
    "Bento XV": "Papa Bento XV",
    "Bento XVI": "Papa Bento XVI",
    "Francisco": "Papa Francisco",
    "Joao Paulo II": "Papa Joao Paulo II",
    "Joao XXIII": "Papa Joao XXIII",
    "Leao XIII": "Papa Leao XIII",
    "Paulo VI": "Papa Paulo VI",
    "Pio X": "Papa Pio X",
    "Sao Pio X": "Papa Pio X",
    "Pio XI": "Papa Pio XI",
    "Pio XII": "Papa Pio XII",
}


@dataclass(frozen=True)
class PdfImportTarget:
    pdf_path: Path
    title: str
    pope: str
    document_type: str
    year: int | None
    language: str
    original_filename: str


def parse_year_and_title(folder_name: str) -> tuple[int | None, str]:
    match = re.match(r"^\s*(\d{4})\s*-\s*(.+?)\s*$", folder_name)
    if not match:
        return None, folder_name.strip()
    return int(match.group(1)), match.group(2).strip()


def canonical_pope_name(name: str) -> str:
    normalized = name.strip()
    if normalized.startswith("Papa "):
        normalized = normalized.removeprefix("Papa ").strip()
    ascii_name = unicodedata.normalize("NFKD", normalized)
    ascii_name = "".join(ch for ch in ascii_name if not unicodedata.combining(ch))
    return POPE_ALIASES.get(ascii_name, f"Papa {ascii_name}")


def parse_language(pdf_path: Path) -> str:
    stem = pdf_path.stem
    match = re.search(r"\s-\s([A-Za-z]{2,4})$", stem)
    if not match:
        return "xx"
    return match.group(1).lower()


def discover_targets(pdf_root: Path) -> list[PdfImportTarget]:
    targets: list[PdfImportTarget] = []
    for pdf_path in sorted(pdf_root.rglob("*.pdf")):
        try:
            work_dir = pdf_path.parent
            type_dir = work_dir.parent
            pope_dir = type_dir.parent
        except IndexError:
            continue

        document_type = TYPE_FOLDERS.get(type_dir.name)
        if document_type is None:
            continue

        year, title = parse_year_and_title(work_dir.name)
        targets.append(
            PdfImportTarget(
                pdf_path=pdf_path.resolve(),
                title=title,
                pope=canonical_pope_name(pope_dir.name),
                document_type=document_type,
                year=year,
                language=parse_language(pdf_path),
                original_filename=pdf_path.name,
            )
        )
    return targets


def find_existing_book(db, target: PdfImportTarget) -> Book | None:
    return (
        db.query(Book)
        .filter(
            Book.title == target.title,
            Book.author == target.pope,
            Book.source_label == SOURCE_LABEL,
            Book.document_type == target.document_type,
            Book.document_year == target.year,
        )
        .order_by(Book.id.asc())
        .first()
    )


def has_file(db, book: Book, target: PdfImportTarget) -> bool:
    stored_path = str(target.pdf_path)
    return (
        db.query(BookFile)
        .filter(BookFile.book_id == book.id, BookFile.stored_path == stored_path)
        .first()
        is not None
    )


def update_book_language_from_files(book: Book) -> None:
    languages = sorted(
        {
            parse_language(Path(book_file.original_filename))
            for book_file in book.files
            if book_file.original_filename
        }
    )
    if len(languages) > 1:
        book.language = "multi"
        book.edition_label = "Vatican.va PDFs multilingues"
    elif languages:
        book.language = languages[0]
        book.edition_label = f"Vatican.va PDF {languages[0].upper()}"


def ensure_book(db, target: PdfImportTarget) -> tuple[Book, bool]:
    book = find_existing_book(db, target)
    if book is not None:
        changed = False
        if not book.library_section:
            book.library_section = LIBRARY_SECTION
            changed = True
        if not book.document_type:
            book.document_type = target.document_type
            changed = True
        if not book.pope:
            book.pope = target.pope
            changed = True
        if book.document_year is None:
            book.document_year = target.year
            changed = True
        if not book.canonical_author:
            book.canonical_author = target.pope
            changed = True
        if not book.canonical_title:
            book.canonical_title = target.title
            changed = True
        if changed:
            db.flush()
        return book, False

    book = Book(
        collection=COLLECTION,
        title=target.title,
        author=target.pope,
        language=target.language,
        edition_label=f"Vatican.va PDF {target.language.upper()}",
        source_label=SOURCE_LABEL,
        is_primary_source=True,
        library_section=LIBRARY_SECTION,
        patristic_tradition=None,
        document_type=target.document_type,
        canonical_author=target.pope,
        canonical_title=target.title,
        pope=target.pope,
        document_year=target.year,
        is_ecumenical=False,
        document_status="official",
        volume_number=None,
        ingest_status="file_only",
        ingest_error=None,
    )
    db.add(book)
    db.flush()
    return book, True


def import_targets(targets: list[PdfImportTarget], dry_run: bool, report_every: int) -> dict[str, int]:
    stats = {
        "targets": len(targets),
        "books_created": 0,
        "books_reused": 0,
        "files_created": 0,
        "files_skipped": 0,
    }

    with SessionLocal() as db:
        for index, target in enumerate(targets, start=1):
            book = find_existing_book(db, target)
            book_created = book is None
            if book_created:
                stats["books_created"] += 1
            else:
                stats["books_reused"] += 1

            if not dry_run:
                book, _ = ensure_book(db, target)
                if has_file(db, book, target):
                    stats["files_skipped"] += 1
                else:
                    db.add(
                        BookFile(
                            book_id=book.id,
                            original_filename=target.original_filename,
                            stored_path=str(target.pdf_path),
                            volume_number=None,
                            editor="Vatican.va",
                            translator=None,
                        )
                    )
                    stats["files_created"] += 1
                update_book_language_from_files(book)
            else:
                if book is not None and has_file(db, book, target):
                    stats["files_skipped"] += 1
                else:
                    stats["files_created"] += 1

            if report_every and index % report_every == 0:
                print(
                    f"IMPORT_PROGRESS {index}/{len(targets)} "
                    f"books_new={stats['books_created']} files_new={stats['files_created']} "
                    f"files_skip={stats['files_skipped']}",
                    flush=True,
                )

        if dry_run:
            db.rollback()
        else:
            db.commit()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Cadastra PDFs pontificios do Vatican.va no banco para visualizacao.")
    parser.add_argument("--pdf-root", type=Path, default=DEFAULT_PDF_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--report-every", type=int, default=100)
    args = parser.parse_args()

    init_db(reset=False)
    targets = discover_targets(args.pdf_root)
    if args.limit:
        targets = targets[: args.limit]

    print(f"PDF_ROOT={args.pdf_root.resolve()}", flush=True)
    print(f"PDF_TARGETS={len(targets)} dry_run={args.dry_run}", flush=True)
    stats = import_targets(targets, dry_run=args.dry_run, report_every=args.report_every)
    print(
        "DONE "
        + " ".join(f"{key}={value}" for key, value in stats.items()),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
