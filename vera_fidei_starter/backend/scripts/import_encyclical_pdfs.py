from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import PDFExtractor
from models.database import Book, BookFile, Chunk, SessionLocal
from scripts.build_encyclical_pdfs import (
    DEFAULT_OUTPUT_DIR,
    EncyclicalItem,
    filename_title,
    parse_index,
    sanitize_path_part,
)
from search.text_search import TextSearchClient
from utils.language import normalize_lang


SOURCE_LABEL = "Vatican.va"
EDITION_LABEL = "Vatican.va — encíclicas papais em português"
OLD_SOURCE_LABEL = "Católico Orante"
COLLECTION = "MAG"
DOCUMENT_TYPE = "enciclica"
LIBRARY_SECTION = "documentos"
LANGUAGE = "pt"


@dataclass(frozen=True)
class ImportTarget:
    item: EncyclicalItem
    pdf_path: Path
    title: str
    year: int | None


def extract_year(title: str, url: str) -> int | None:
    matches = re.findall(r"\b(18\d{2}|19\d{2}|20\d{2})\b", f"{title} {url}")
    if matches:
        return int(matches[-1])
    return None


def clean_title(title: str) -> str:
    return filename_title(title)


def resolve_targets(pdf_root: Path) -> list[ImportTarget]:
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": "Vera.Fidei Biblioteca/1.0"})
    items = parse_index(session)
    targets: list[ImportTarget] = []

    for item in items:
        pope_dir = pdf_root / sanitize_path_part(item.pope, max_len=80)
        pdf_name = f"{item.index:03d} - {filename_title(item.title)}.pdf"
        pdf_path = pope_dir / pdf_name
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")
        targets.append(
            ImportTarget(
                item=item,
                pdf_path=pdf_path,
                title=clean_title(item.title),
                year=extract_year(item.title, item.url),
            )
        )
    return targets


def already_imported(db, target: ImportTarget) -> Book | None:
    return (
        db.query(Book)
        .filter(
            Book.title == target.title,
            Book.author == target.item.pope,
            Book.collection == COLLECTION,
            Book.document_type == DOCUMENT_TYPE,
            Book.source_label == SOURCE_LABEL,
        )
        .first()
    )


def remove_old_catolico_orante_imports() -> int:
    from search.text_search import TextSearchClient

    try:
        from search.semantic_search import SemanticSearchClient
        semantic_search = SemanticSearchClient()
    except Exception:
        semantic_search = None

    text_search = TextSearchClient()
    removed = 0

    with SessionLocal() as db:
        books = (
            db.query(Book)
            .filter(Book.document_type == DOCUMENT_TYPE, Book.source_label == OLD_SOURCE_LABEL)
            .all()
        )
        for book in books:
            chunk_ids = [chunk.id for chunk in book.chunks]
            for chunk_id in chunk_ids:
                text_search.delete_chunk(chunk_id)
                if semantic_search is not None:
                    semantic_search.delete_chunk(chunk_id)
            db.delete(book)
            removed += 1
        db.commit()
    return removed


def clear_book_content(db, book: Book) -> None:
    from search.text_search import TextSearchClient

    try:
        from search.semantic_search import SemanticSearchClient
        semantic_search = SemanticSearchClient()
    except Exception:
        semantic_search = None

    text_search = TextSearchClient()
    chunk_ids = [chunk.id for chunk in book.chunks]
    for chunk_id in chunk_ids:
        text_search.delete_chunk(chunk_id)
        if semantic_search is not None:
            semantic_search.delete_chunk(chunk_id)

    for chunk in list(book.chunks):
        db.delete(chunk)
    for book_file in list(book.files):
        db.delete(book_file)
    db.flush()


def index_records(
    book: Book,
    book_file: BookFile,
    chunks: list[Chunk],
    target: ImportTarget,
    skip_chroma: bool,
    chroma_batch_size: int,
) -> None:
    text_search = TextSearchClient()
    es_items: list[tuple[int, dict]] = []
    chroma_items: list[tuple[int, str, dict]] = []

    for chunk in chunks:
        doc = {
            "book_id": book.id,
            "book_file_id": book_file.id,
            "text": chunk.text,
            "author": book.author,
            "work_title": book.title,
            "collection": COLLECTION,
            "language": LANGUAGE,
            "pdf_page": chunk.pdf_page,
            "edition_label": EDITION_LABEL,
            "chapter_or_section": chunk.chapter_or_section,
            "char_offset_start": chunk.char_offset_start,
            "char_offset_end": chunk.char_offset_end,
        }
        es_items.append((chunk.id, doc))
        chroma_items.append(
            (
                chunk.id,
                chunk.text,
                {
                    "book_id": book.id,
                    "book_file_id": book_file.id,
                    "author": book.author,
                    "work_title": book.title,
                    "collection": COLLECTION,
                    "document_type": DOCUMENT_TYPE,
                    "source_label": SOURCE_LABEL,
                    "pope": target.item.pope,
                },
            )
        )

    text_search.index_chunks(es_items)

    if skip_chroma:
        return

    from search.semantic_search import SemanticSearchClient

    semantic_search = SemanticSearchClient()
    semantic_search.index_chunks(
        chroma_items,
        language=normalize_lang(LANGUAGE),
        batch_size=chroma_batch_size,
    )


def import_target(
    target: ImportTarget,
    skip_chroma: bool,
    chroma_batch_size: int,
    force: bool,
    upgrade_html_only: bool,
) -> tuple[str, int, int | None]:
    extractor = PDFExtractor()
    chunker = Chunker()

    with SessionLocal() as db:
        existing = already_imported(db, target)
        if existing and not force:
            if not upgrade_html_only or existing.files:
                return "skip", 0, existing.id
            book = existing
            clear_book_content(db, book)
            book.ingest_status = "indexing"
            book.ingest_error = None
            book.edition_label = EDITION_LABEL
        elif existing and force:
            db.delete(existing)
            db.commit()
            existing = None

        if existing is None:
            book = Book(
                title=target.title,
                author=target.item.pope,
                canonical_author=target.item.pope,
                canonical_title=target.title,
                language=LANGUAGE,
                collection=COLLECTION,
                library_section=LIBRARY_SECTION,
                document_type=DOCUMENT_TYPE,
                pope=target.item.pope.replace("Papa ", ""),
                document_year=target.year,
                is_primary_source=True,
                edition_label=EDITION_LABEL,
                source_label=SOURCE_LABEL,
                ingest_status="indexing",
            )
            db.add(book)
            db.flush()
        else:
            book.title = target.title
            book.author = target.item.pope
            book.canonical_author = target.item.pope
            book.canonical_title = target.title
            book.language = LANGUAGE
            book.collection = COLLECTION
            book.library_section = LIBRARY_SECTION
            book.document_type = DOCUMENT_TYPE
            book.pope = target.item.pope.replace("Papa ", "")
            book.document_year = target.year
            book.is_primary_source = True
            book.source_label = SOURCE_LABEL

        book_file = BookFile(
            book_id=book.id,
            original_filename=target.pdf_path.name,
            stored_path=str(target.pdf_path.resolve()),
            volume_number=None,
        )
        db.add(book_file)
        db.flush()

        pages = extractor.extract(str(target.pdf_path))
        raw_chunks = chunker.chunk(pages, document_meta={})
        if not raw_chunks:
            book.ingest_status = "failed"
            book.ingest_error = "PDF extraído sem chunks"
            db.commit()
            return "failed", 0, book.id

        chunk_records: list[Chunk] = []
        for sequence_index, chunk_data in enumerate(raw_chunks):
            chunk = Chunk(
                book_id=book.id,
                book_file_id=book_file.id,
                text=chunk_data["text"],
                sequence_index=sequence_index,
                chunk_author=target.item.pope,
                pdf_page=chunk_data.get("pdf_page"),
                char_offset_start=chunk_data.get("char_offset_start"),
                char_offset_end=chunk_data.get("char_offset_end"),
                column_start=chunk_data.get("column_start") or None,
                column_end=chunk_data.get("column_end") or None,
            )
            db.add(chunk)
            chunk_records.append(chunk)

        db.flush()

        try:
            index_records(
                book=book,
                book_file=book_file,
                chunks=chunk_records,
                target=target,
                skip_chroma=skip_chroma,
                chroma_batch_size=chroma_batch_size,
            )
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            raise RuntimeError(f"falha ao indexar {target.title}: {exc}") from exc

        if skip_chroma:
            book.ingest_status = "processing"
            book.ingest_error = "Parcial: DB e Elasticsearch completos; Chroma pendente."
        else:
            book.ingest_status = "done"
            book.ingest_error = None
        db.commit()
        return ("upgraded" if existing is not None else "ok"), len(chunk_records), book.id


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa PDFs de encíclicas gerados para a biblioteca.")
    parser.add_argument("--pdf-root", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--only", default="", help="Filtra por título ou papa.")
    parser.add_argument("--pope", default="", help="Filtra por Papa com igualdade exata, ex: 'Papa Pio XI'.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-chroma", action="store_true")
    parser.add_argument("--chroma-batch-size", type=int, default=32)
    parser.add_argument("--force", action="store_true", help="Remove e reimporta entradas Vatican.va já existentes.")
    parser.add_argument(
        "--upgrade-html-only",
        action="store_true",
        help="Se já existir como Vatican.va sem BookFile/PDF, substitui chunks por chunks extraídos do PDF gerado.",
    )
    parser.add_argument(
        "--remove-old-catolico-orante",
        action="store_true",
        help="Remove importações antigas feitas com source_label Católico Orante antes de importar.",
    )
    args = parser.parse_args()

    if args.remove_old_catolico_orante:
        removed = remove_old_catolico_orante_imports()
        print(f"Removidas {removed} encíclica(s) antigas com source_label={OLD_SOURCE_LABEL!r}.")

    targets = resolve_targets(args.pdf_root)
    if args.only:
        needle = args.only.casefold()
        targets = [
            target
            for target in targets
            if needle in target.title.casefold() or needle in target.item.pope.casefold()
        ]
    if args.pope:
        pope = args.pope.casefold()
        targets = [target for target in targets if target.item.pope.casefold() == pope]
    if args.limit:
        targets = targets[: args.limit]

    if not targets:
        print("Nenhuma encíclica encontrada para importar.")
        return 1

    print(f"Importando {len(targets)} encíclica(s) de {args.pdf_root}")
    ok = skipped = failed = total_chunks = 0

    for index, target in enumerate(targets, start=1):
        print(f"[{index}/{len(targets)}] {target.item.pope} — {target.title}", flush=True)
        try:
            status, chunks, book_id = import_target(
                target,
                skip_chroma=args.skip_chroma,
                chroma_batch_size=args.chroma_batch_size,
                force=args.force,
                upgrade_html_only=args.upgrade_html_only,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  falha: {exc}", flush=True)
            failed += 1
            continue

        if status == "ok":
            print(f"  ok: book_id={book_id}, chunks={chunks}", flush=True)
            ok += 1
            total_chunks += chunks
        elif status == "upgraded":
            print(f"  atualizado com PDF: book_id={book_id}, chunks={chunks}", flush=True)
            ok += 1
            total_chunks += chunks
        elif status == "skip":
            print(f"  já importada: book_id={book_id}", flush=True)
            skipped += 1
        else:
            print(f"  falha: book_id={book_id}", flush=True)
            failed += 1

    print()
    print(f"Concluído: {ok} importada(s), {skipped} já existiam, {failed} falha(s), {total_chunks} chunks novos.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
