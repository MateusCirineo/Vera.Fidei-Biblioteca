"""
Corrige documentos Vatican.va que ja possuem BookFiles no banco, mas nenhum
chunk. Diferente de fix_zero_chunk_docs.py, este script nao depende do
manifest.jsonl: ele usa diretamente os PDFs vinculados ao Book.

Uso:
    cd vera_fidei_starter/backend
    python scripts/fix_zero_chunk_bookfiles.py --no-semantic
"""
from __future__ import annotations

import argparse
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _language_from_filename(filename: str) -> str:
    match = re.search(r"\s-\s([A-Za-z]{2,4})\.pdf$", filename, flags=re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return "pt"


def run(dry_run: bool, no_semantic: bool, limit: int | None) -> None:
    from ingestion.chunker import Chunker
    from ingestion.pdf_extractor import PDFExtractor
    from models.database import Book, BookFile, Chunk, SessionLocal
    from search.text_search import TextSearchClient
    from utils.language import normalize_lang

    semantic_search = None
    if not no_semantic:
        try:
            from search.semantic_search import SemanticSearchClient

            semantic_search = SemanticSearchClient()
        except Exception as exc:
            print(f"AVISO: ChromaDB indisponivel; seguindo so ES. ({exc.__class__.__name__})")

    with SessionLocal() as db:
        books_with_chunks = {
            row[0]
            for row in (
                db.query(Chunk.book_id)
                .join(Book, Chunk.book_id == Book.id)
                .filter(Book.library_section == "documentos", Book.source_label == "Vatican.va")
                .distinct()
                .all()
            )
        }
        query = (
            db.query(Book)
            .filter(Book.library_section == "documentos", Book.source_label == "Vatican.va")
            .filter(~Book.id.in_(books_with_chunks))
            .order_by(Book.document_year.asc().nulls_last(), Book.id.asc())
        )
        books = query.limit(limit).all() if limit else query.all()

    print(f"Livros Vatican.va sem chunks e com BookFiles: {len(books)}", flush=True)
    if dry_run:
        with SessionLocal() as db:
            for book in books[:20]:
                files = db.query(BookFile).filter(BookFile.book_id == book.id).count()
                print(f"  [{book.id}] {book.title} — {book.pope} ({book.document_type}) files={files}")
            if len(books) > 20:
                print(f"  ... e mais {len(books) - 20}")
        return

    extractor = PDFExtractor()
    chunker = Chunker()
    text_search = TextSearchClient()

    fixed_files = skipped_files = errors = 0

    for index, book in enumerate(books, start=1):
        with SessionLocal() as db:
            current = db.get(Book, book.id)
            if current is None:
                continue
            files = (
                db.query(BookFile)
                .filter(BookFile.book_id == current.id)
                .order_by(BookFile.id.asc())
                .all()
            )
            print(f"\n[{index}/{len(books)}] {current.title} — {current.pope} ({len(files)} PDFs)", flush=True)

        for book_file in files:
            with SessionLocal() as db:
                existing = db.query(Chunk).filter(Chunk.book_file_id == book_file.id).count()
            if existing:
                print(f"  [{book_file.id}] Ja tem {existing} chunks — pulando.", flush=True)
                skipped_files += 1
                continue

            if not os.path.isfile(book_file.stored_path):
                print(f"  [{book_file.id}] Arquivo nao encontrado: {book_file.stored_path}", flush=True)
                skipped_files += 1
                continue

            print(f"  [{book_file.id}] Extraindo: {book_file.original_filename}", flush=True)
            try:
                pages = extractor.extract(book_file.stored_path)
                total_chars = sum(len(page.get("text", "")) for page in pages)
                print(f"         {len(pages)} paginas, {total_chars} chars", flush=True)
                if total_chars < 100:
                    print("         Texto muito curto — pulando.", flush=True)
                    skipped_files += 1
                    continue

                raw_chunks = chunker.chunk(pages, document_meta={})
                print(f"         {len(raw_chunks)} chunks", flush=True)
                if not raw_chunks:
                    skipped_files += 1
                    continue

                with SessionLocal() as db:
                    current = db.get(Book, book_file.book_id)
                    if current is None:
                        skipped_files += 1
                        continue

                    chunk_records: list[Chunk] = []
                    for sequence_index, chunk_data in enumerate(raw_chunks):
                        chunk = Chunk(
                            book_id=current.id,
                            book_file_id=book_file.id,
                            text=chunk_data["text"],
                            sequence_index=sequence_index,
                            pdf_page=chunk_data.get("pdf_page"),
                            char_offset_start=chunk_data.get("char_offset_start"),
                            char_offset_end=chunk_data.get("char_offset_end"),
                        )
                        db.add(chunk)
                        chunk_records.append(chunk)

                    current.ingest_status = "done"
                    current.ingest_error = None
                    db.flush()

                    language = _language_from_filename(book_file.original_filename)
                    semantic_language = normalize_lang(language)
                    author_display = current.author or current.pope or "Vatican.va"

                    es_items = [
                        (
                            chunk.id,
                            {
                                "book_id": current.id,
                                "book_file_id": book_file.id,
                                "text": chunk.text,
                                "author": author_display,
                                "work_title": current.title,
                                "collection": current.collection or "MAG",
                                "language": language,
                                "pdf_page": chunk.pdf_page,
                                "edition_label": current.edition_label or "Vatican.va",
                            },
                        )
                        for chunk in chunk_records
                    ]
                    chroma_items = [
                        (
                            chunk.id,
                            chunk.text,
                            {
                                "book_id": current.id,
                                "author": author_display,
                                "work_title": current.title,
                            },
                        )
                        for chunk in chunk_records
                    ]

                    text_search.index_chunks(es_items)
                    if semantic_search is not None:
                        semantic_search.index_chunks(chroma_items, language=semantic_language)

                    db.commit()

                fixed_files += 1
                print(f"         OK ({len(raw_chunks)} chunks)", flush=True)
            except Exception as exc:
                print(f"         ERRO: {exc}", flush=True)
                errors += 1

    print("\n" + "=" * 60, flush=True)
    print(
        f"Concluido: {fixed_files} arquivos corrigidos, "
        f"{skipped_files} pulados, {errors} erros.",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-semantic", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    run(dry_run=args.dry_run, no_semantic=args.no_semantic, limit=args.limit or None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
