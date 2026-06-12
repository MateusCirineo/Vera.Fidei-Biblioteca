"""Register Council PDFs from backend/pdfs/concilios/ into PostgreSQL.

Expected folder layout (no strict depth requirement — searches all *.pdf under root):
    concilios/
      Seculo IV (325-381)/
        01 - 325 - Niceia I/
          Canones e Documentos/
            Canones e Documentos - PT.pdf
            Canones e Documentos - EN.pdf
            ...

Extracted per PDF:
  - council_name  : parent of document folder  (e.g. "01 - 325 - Niceia I")
  - doc_title     : document folder name         (e.g. "Canones e Documentos")
  - language      : suffix of filename stem      (e.g. "pt")
  - document_year : four-digit year embedded in council folder name
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from models.database import Book, BookFile, SessionLocal, init_db


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PDF_ROOT = BACKEND_DIR / "pdfs" / "concilios"
PDF_ROOT_BASE = BACKEND_DIR / "pdfs"

COLLECTION = "MAG"
LIBRARY_SECTION = "documentos"
DOCUMENT_TYPE = "concilio"

# Source label heuristics based on filename fragments (lower-cased)
SOURCE_LABEL_DEFAULT = "Fontes Históricas"
SOURCE_LABEL_MAP: dict[str, str] = {
    "vatican.va": "Vatican.va",
    "newadvent": "New Advent / NPNF",
    "apologistas": "Apologistas Católicos",
    "elpenor": "Elpenor.org",
    "ewtn": "EWTN",
    "dca": "Documenta Catholica Omnia",
}

# Canonical council names extracted from folder name numbers
COUNCIL_CANONICAL: dict[int, str] = {
    1:  "Concílio de Nicéia I",
    2:  "Concílio de Constantinopla I",
    3:  "Concílio de Éfeso",
    4:  "Concílio de Calcedônia",
    5:  "Concílio de Constantinopla II",
    6:  "Concílio de Constantinopla III",
    7:  "Concílio de Nicéia II",
    8:  "Concílio de Constantinopla IV",
    9:  "Concílio do Latrão I",
    10: "Concílio do Latrão II",
    11: "Concílio do Latrão III",
    12: "Concílio do Latrão IV",
    13: "Concílio de Lião I",
    14: "Concílio de Lião II",
    15: "Concílio de Viena",
    16: "Concílio de Constança",
    17: "Concílio de Florença",
    18: "Concílio do Latrão V",
    19: "Concílio de Trento",
    20: "Concílio Vaticano I",
    21: "Concílio Vaticano II",
}


@dataclass(frozen=True)
class PdfImportTarget:
    pdf_path: Path
    council_name: str       # canonical name from COUNCIL_CANONICAL
    council_folder: str     # raw folder name, e.g. "01 - 325 - Niceia I"
    doc_title: str          # document subdirectory, e.g. "Canones e Documentos"
    language: str           # "pt", "en", "la", ...
    document_year: int | None
    source_label: str
    original_filename: str


# ─────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_council_number(folder_name: str) -> int | None:
    m = re.match(r"^\s*(\d+)\s*-", folder_name)
    return int(m.group(1)) if m else None


def _parse_year_from_folder(folder_name: str) -> int | None:
    # Matches "01 - 325 - Niceia I" → 325
    m = re.search(r"-\s*(\d{3,4})\s*-", folder_name)
    if m:
        return int(m.group(1))
    # Matches "Seculo IV (325-381)" style — not used for year extraction
    return None


def _parse_language(filename: str) -> str:
    stem = Path(filename).stem
    m = re.search(r"\s*-\s*([A-Za-z]{2,4})$", stem)
    return m.group(1).lower() if m else "xx"


def _canonical_council(folder_name: str) -> str:
    num = _parse_council_number(folder_name)
    if num is not None and num in COUNCIL_CANONICAL:
        return COUNCIL_CANONICAL[num]
    # Fallback: strip leading "NN - YYYY - " prefix
    cleaned = re.sub(r"^\s*\d+\s*-\s*\d*\s*-\s*", "", folder_name).strip()
    # Remove accent-less characters and normalise
    return f"Concílio {cleaned}" if cleaned else folder_name


def _source_label_for(pdf_path: Path) -> str:
    """Infer source label from any fragment in the path string."""
    path_lower = str(pdf_path).lower()
    for fragment, label in SOURCE_LABEL_MAP.items():
        if fragment in path_lower:
            return label
    return SOURCE_LABEL_DEFAULT


# ─────────────────────────────────────────────────────────────────────────────
# Discovery
# ─────────────────────────────────────────────────────────────────────────────

def _is_council_dir(path: Path) -> bool:
    """Return True if path looks like a council folder (starts with NN -)."""
    return bool(re.match(r"^\s*\d+\s*-", path.name))


def discover_targets(pdf_root: Path) -> list[PdfImportTarget]:
    targets: list[PdfImportTarget] = []

    for pdf_path in sorted(pdf_root.rglob("*.pdf")):
        # Minimum depth: concilios/{century}/{council}/{document}/{file.pdf}
        parts = pdf_path.parts
        # Find the council folder (the one that starts with NN -)
        council_folder_path: Path | None = None
        for ancestor in pdf_path.parents:
            if _is_council_dir(ancestor):
                council_folder_path = ancestor
                break

        if council_folder_path is None:
            continue

        # The document directory is the immediate parent of the PDF
        doc_dir = pdf_path.parent

        # Skip if doc_dir is the council folder itself (no sub-document grouping)
        if doc_dir == council_folder_path:
            doc_title = council_folder_path.name
        else:
            doc_title = doc_dir.name

        council_folder = council_folder_path.name
        council_name = _canonical_council(council_folder)
        document_year = _parse_year_from_folder(council_folder)
        language = _parse_language(pdf_path.name)
        source_label = _source_label_for(pdf_path)

        targets.append(
            PdfImportTarget(
                pdf_path=pdf_path.resolve(),
                council_name=council_name,
                council_folder=council_folder,
                doc_title=doc_title,
                language=language,
                document_year=document_year,
                source_label=source_label,
                original_filename=pdf_path.name,
            )
        )

    return targets


# ─────────────────────────────────────────────────────────────────────────────
# Database helpers
# ─────────────────────────────────────────────────────────────────────────────

def find_existing_book(db, target: PdfImportTarget) -> Book | None:
    return (
        db.query(Book)
        .filter(
            Book.title == target.doc_title,
            Book.author == target.council_name,
            Book.document_type == DOCUMENT_TYPE,
            Book.language == target.language,
            Book.document_year == target.document_year,
        )
        .order_by(Book.id.asc())
        .first()
    )


def has_file(db, book: Book, target: PdfImportTarget) -> bool:
    relative_path = str(target.pdf_path.relative_to(PDF_ROOT_BASE)).replace("\\", "/")
    absolute_path = str(target.pdf_path)
    return (
        db.query(BookFile)
        .filter(
            BookFile.book_id == book.id,
            BookFile.stored_path.in_([relative_path, absolute_path]),
        )
        .first()
        is not None
    )


def ensure_book(db, target: PdfImportTarget) -> tuple[Book, bool]:
    book = find_existing_book(db, target)
    if book is not None:
        changed = False
        if not book.library_section:
            book.library_section = LIBRARY_SECTION
            changed = True
        if not book.canonical_author:
            book.canonical_author = target.council_name
            changed = True
        if not book.canonical_title:
            book.canonical_title = target.doc_title
            changed = True
        if book.document_year is None and target.document_year:
            book.document_year = target.document_year
            changed = True
        if changed:
            db.flush()
        return book, False

    book = Book(
        collection=COLLECTION,
        title=target.doc_title,
        author=target.council_name,
        language=target.language,
        edition_label=f"{target.source_label} PDF {target.language.upper()}",
        source_label=target.source_label,
        is_primary_source=True,
        library_section=LIBRARY_SECTION,
        patristic_tradition=None,
        document_type=DOCUMENT_TYPE,
        canonical_author=target.council_name,
        canonical_title=target.doc_title,
        pope=None,
        document_year=target.document_year,
        is_ecumenical=True,
        document_status="official",
        volume_number=None,
        ingest_status="file_only",
        ingest_error=None,
    )
    db.add(book)
    db.flush()
    return book, True


# ─────────────────────────────────────────────────────────────────────────────
# Main import loop
# ─────────────────────────────────────────────────────────────────────────────

def import_targets(
    targets: list[PdfImportTarget],
    dry_run: bool,
    report_every: int,
) -> dict[str, int]:
    stats: dict[str, int] = {
        "targets": len(targets),
        "books_created": 0,
        "books_reused": 0,
        "files_created": 0,
        "files_skipped": 0,
    }

    with SessionLocal() as db:
        for index, target in enumerate(targets, start=1):
            existing = find_existing_book(db, target)

            if dry_run:
                if existing is None:
                    stats["books_created"] += 1
                    stats["files_created"] += 1
                else:
                    stats["books_reused"] += 1
                    if has_file(db, existing, target):
                        stats["files_skipped"] += 1
                    else:
                        stats["files_created"] += 1
            else:
                book, created = ensure_book(db, target)
                if created:
                    stats["books_created"] += 1
                else:
                    stats["books_reused"] += 1

                if has_file(db, book, target):
                    stats["files_skipped"] += 1
                else:
                    relative_path = str(
                        target.pdf_path.relative_to(PDF_ROOT_BASE)
                    ).replace("\\", "/")
                    db.add(
                        BookFile(
                            book_id=book.id,
                            original_filename=target.original_filename,
                            stored_path=relative_path,
                            volume_number=None,
                            editor=target.source_label,
                            translator=None,
                        )
                    )
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


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cadastra PDFs dos Concílios Ecumênicos no banco para visualização."
    )
    parser.add_argument("--pdf-root", type=Path, default=DEFAULT_PDF_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--report-every", type=int, default=50)
    args = parser.parse_args()

    init_db(reset=False)
    targets = discover_targets(args.pdf_root)
    if args.limit:
        targets = targets[: args.limit]

    print(f"PDF_ROOT={args.pdf_root.resolve()}", flush=True)
    print(f"PDF_TARGETS={len(targets)} dry_run={args.dry_run}", flush=True)

    stats = import_targets(targets, dry_run=args.dry_run, report_every=args.report_every)

    print(
        "DONE " + " ".join(f"{key}={value}" for key, value in stats.items()),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
