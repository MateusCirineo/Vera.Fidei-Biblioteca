"""Ingere os PDFs dos Concílios Ecumênicos já registrados no banco.

Processa todos os Books com document_type='concilio' e ingest_status='file_only',
extrai texto via PDFExtractor, chunkeia e indexa no Elasticsearch + ChromaDB.

Uso:
    cd vera_fidei_starter/backend
    python -m scripts.ingest_councils [--dry-run] [--resume] [--council SUBSTR]

Flags:
    --dry-run   Mostra o que seria ingerido sem gravar nada.
    --resume    Pula books com ingest_status='done'.
    --council   Filtra por nome do concílio (substring).
"""
from __future__ import annotations

import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_ROOT = os.path.join(BACKEND_DIR, "pdfs")


def _resolve_path(stored_path: str) -> str:
    """Return absolute filesystem path from stored_path (relative or absolute)."""
    if os.path.isabs(stored_path):
        return stored_path
    candidate = os.path.join(PDF_ROOT, stored_path)
    if os.path.exists(candidate):
        return candidate
    # Windows backslash variant
    return os.path.join(PDF_ROOT, stored_path.replace("/", os.sep))


def ingest(dry_run: bool = False, resume: bool = False, council_filter: str = "") -> None:
    from models.database import SessionLocal, Book, BookFile, Chunk
    from ingestion.pdf_extractor import PDFExtractor
    from ingestion.chunker import Chunker
    from search.text_search import TextSearchClient
    from utils.language import normalize_lang

    semantic_ok = False
    try:
        from search.semantic_search import SemanticSearchClient
        semantic_ok = True
    except Exception as exc:
        print(f"[AVISO] Indexação semântica desativada: {exc.__class__.__name__}. Só ES.")

    with SessionLocal() as db:
        query = db.query(Book).filter(Book.document_type == "concilio")
        if council_filter:
            query = query.filter(Book.author.ilike(f"%{council_filter}%"))
        if resume:
            query = query.filter(Book.ingest_status != "done")
        else:
            query = query.filter(Book.ingest_status == "file_only")

        books = query.order_by(Book.id.asc()).all()

    print(f"Books para ingerir: {len(books)}")
    if not books:
        print("Nenhum book pendente.")
        return

    extractor = PDFExtractor()
    chunker = Chunker()
    text_search = TextSearchClient()
    semantic_search = SemanticSearchClient() if semantic_ok and not dry_run else None

    total_chunks = 0
    errors = 0

    for book in books:
        print(f"\n[{book.id}] {book.author} / {book.title} [{book.language}]")

        with SessionLocal() as db:
            files = db.query(BookFile).filter(BookFile.book_id == book.id).all()

        if not files:
            print("  Sem BookFiles — pulando.")
            errors += 1
            continue

        book_file = files[0]
        abs_path = _resolve_path(book_file.stored_path)

        if not os.path.exists(abs_path):
            print(f"  Arquivo não encontrado: {abs_path} — pulando.")
            errors += 1
            continue

        size_kb = os.path.getsize(abs_path) // 1024
        print(f"  PDF: {abs_path} ({size_kb} KB)")

        if dry_run:
            print(f"  [dry-run] seria ingerido.")
            continue

        try:
            pages = extractor.extract(abs_path)
            raw_chunks = chunker.chunk(pages, document_meta={})
        except Exception as exc:
            print(f"  ERRO ao extrair/chunkear: {exc}")
            errors += 1
            with SessionLocal() as db:
                db.query(Book).filter(Book.id == book.id).update(
                    {"ingest_status": "error", "ingest_error": str(exc)[:500]}
                )
                db.commit()
            continue

        if not raw_chunks:
            print("  Nenhum chunk extraído — pulando.")
            errors += 1
            continue

        print(f"  {len(pages)} páginas → {len(raw_chunks)} chunks")

        with SessionLocal() as db:
            # Remove chunks antigos se houver (re-ingestão)
            db.query(Chunk).filter(Chunk.book_id == book.id).delete()
            db.flush()

            db.query(Book).filter(Book.id == book.id).update({"ingest_status": "indexing"})
            db.flush()

            chunk_records: list[Chunk] = []
            for i, cd in enumerate(raw_chunks):
                c = Chunk(
                    book_id=book.id,
                    book_file_id=book_file.id,
                    text=cd["text"],
                    sequence_index=i,
                    pdf_page=cd.get("pdf_page"),
                    char_offset_start=cd.get("char_offset_start"),
                    char_offset_end=cd.get("char_offset_end"),
                )
                db.add(c)
                chunk_records.append(c)

            db.flush()

            lang = normalize_lang(book.language)
            es_items: list[tuple[int, dict]] = []
            chroma_items: list[tuple[int, str, dict]] = []

            for chunk in chunk_records:
                es_doc = {
                    "book_id": book.id,
                    "book_file_id": book_file.id,
                    "text": chunk.text,
                    "author": book.author,
                    "work_title": book.title,
                    "collection": book.collection,
                    "language": book.language,
                    "pdf_page": chunk.pdf_page,
                    "edition_label": book.edition_label or "",
                    "document_type": "concilio",
                    "is_ecumenical": True,
                }
                es_items.append((chunk.id, es_doc))
                chroma_items.append((
                    chunk.id,
                    chunk.text,
                    {"book_id": book.id, "author": book.author, "work_title": book.title},
                ))

            try:
                text_search.index_chunks(es_items)
                if semantic_search is not None:
                    semantic_search.index_chunks(chroma_items, language=lang)
            except Exception as exc:
                db.rollback()
                print(f"  ERRO ao indexar: {exc}")
                errors += 1
                continue

            db.query(Book).filter(Book.id == book.id).update({"ingest_status": "done", "ingest_error": None})
            db.commit()

        total_chunks += len(raw_chunks)
        print(f"  OK — {len(raw_chunks)} chunks indexados")

    print(f"\n{'[dry-run] ' if dry_run else ''}CONCLUIDO")
    print(f"  Chunks indexados : {total_chunks}")
    print(f"  Erros            : {errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingere PDFs dos Concílios Ecumênicos no Vera.Fidei")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Inclui books com status != done")
    parser.add_argument("--council", default="", help="Filtra por nome do concílio (substring)")
    args = parser.parse_args()

    ingest(dry_run=args.dry_run, resume=args.resume, council_filter=args.council)


if __name__ == "__main__":
    main()
