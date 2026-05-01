"""
Ingere os PDFs de documentos_pontificios no banco de dados Vera.Fidei.

Lê o manifest.jsonl gerado pelo scrape_vatican_pdfs.py e para cada entrada:
  1. Cria (ou reutiliza) o Book correspondente
  2. Registra o PDF como BookFile
  3. Extrai texto via PDFExtractor
  4. Chunkeia e indexa no Elasticsearch + ChromaDB

Uso:
    cd vera_fidei_starter/backend
    python scripts/ingest_pontificios.py [--dry-run] [--resume] [--pope "Francisco"]

Flags:
    --dry-run   Mostra o que seria ingerido sem gravar nada
    --resume    Pula BookFiles já registrados no banco (por stored_path)
    --pope      Filtra por papa (substring, ex: "Pio XII")
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(BACKEND_DIR, "pdfs", "documentos_pontificios", "manifest.jsonl")

LANG_LABEL = {
    "pt": "Português",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "la": "Latim",
    "pl": "Polski",
    "ar": "العربية",
}

POPE_FOLDER_TO_CANONICAL = {
    "Papa Leao XIII":      "Papa Leão XIII",
    "Papa Pio X":          "Papa Pio X",
    "Papa Bento XV":       "Papa Bento XV",
    "Papa Pio XI":         "Papa Pio XI",
    "Papa Pio XII":        "Papa Pio XII",
    "Papa Joao XXIII":     "Papa João XXIII",
    "Papa Paulo VI":       "Papa Paulo VI",
    "Papa Joao Paulo I":   "Papa João Paulo I",
    "Papa Joao Paulo II":  "Papa João Paulo II",
    "Papa Bento XVI":      "Papa Bento XVI",
    "Papa Francisco":      "Papa Francisco",
}

POPE_FOLDER_TO_SHORT = {
    "Papa Leao XIII":      "Leão XIII",
    "Papa Pio X":          "Pio X",
    "Papa Bento XV":       "Bento XV",
    "Papa Pio XI":         "Pio XI",
    "Papa Pio XII":        "Pio XII",
    "Papa Joao XXIII":     "João XXIII",
    "Papa Paulo VI":       "Paulo VI",
    "Papa Joao Paulo I":   "João Paulo I",
    "Papa Joao Paulo II":  "João Paulo II",
    "Papa Bento XVI":      "Bento XVI",
    "Papa Francisco":      "Francisco",
}

TYPE_KEY_TO_SECTION = {
    "enciclica":              "documentos",
    "carta_apostolica":       "documentos",
    "bula":                   "documentos",
    "constituicao_apostolica":"documentos",
    "motu_proprio":           "documentos",
    "exortacao_apostolica":   "documentos",
}


def _load_manifest(path: str) -> list[dict]:
    entries = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    return entries


def _pope_folder_from_path(stored_path: str) -> str:
    """Extract 'Papa Leao XIII' from the stored path."""
    parts = stored_path.replace("\\", "/").split("/")
    for i, p in enumerate(parts):
        if p.startswith("Papa "):
            return p
    return ""


def _get_or_create_book(db, entry: dict, pope_folder: str, dry_run: bool):
    from models.database import Book

    title = entry["title"]
    pope_short = POPE_FOLDER_TO_SHORT.get(pope_folder, entry.get("author", ""))
    author_full = POPE_FOLDER_TO_CANONICAL.get(pope_folder, f"Papa {pope_short}")
    type_key = entry.get("type_key", "outro")
    year = entry.get("year")

    existing = (
        db.query(Book)
        .filter(Book.title == title, Book.pope == pope_short, Book.document_type == type_key)
        .first()
    )
    if existing:
        return existing, False

    if dry_run:
        return None, True

    book = Book(
        title=title,
        author=author_full,
        canonical_author=author_full,
        canonical_title=title,
        language="pt",           # primary language; files are per-language
        collection="MAG",
        library_section="documentos",
        document_type=type_key,
        pope=pope_short,
        document_year=year,
        is_primary_source=True,
        edition_label="Vatican.va",
        source_label="Vatican.va",
        ingest_status="indexing",
    )
    db.add(book)
    db.flush()
    return book, True


def ingest(dry_run: bool = False, resume: bool = False, pope_filter: str = "") -> None:
    entries = _load_manifest(MANIFEST_PATH)
    print(f"Manifesto: {len(entries)} entradas")

    if pope_filter:
        entries = [e for e in entries if pope_filter.lower() in e.get("author", "").lower()]
        print(f"Filtro '{pope_filter}': {len(entries)} entradas")

    if dry_run:
        print("[dry-run] Nenhuma gravacao sera feita.\n")

    from models.database import SessionLocal, Book, BookFile, Chunk
    from ingestion.pdf_extractor import PDFExtractor
    from ingestion.chunker import Chunker
    from search.text_search import TextSearchClient
    from utils.language import normalize_lang

    try:
        from search.semantic_search import SemanticSearchClient
        semantic_ok = True
    except Exception as exc:
        print(f"AVISO: ChromaDB indisponivel ({exc.__class__.__name__}) — so ES.")
        semantic_ok = False

    extractor = PDFExtractor()
    chunker = Chunker()
    text_search = TextSearchClient()
    semantic_search = SemanticSearchClient() if semantic_ok and not dry_run else None

    # Build set of already-registered stored_paths for resume
    existing_paths: set[str] = set()
    if resume and not dry_run:
        with SessionLocal() as db:
            rows = db.query(BookFile.stored_path).all()
            existing_paths = {os.path.normpath(r[0]) for r in rows if r[0]}
        print(f"[Resume] {len(existing_paths)} BookFiles ja no banco.\n")

    total = len(entries)
    saved = skipped = errors = 0

    # Group entries by (title, pope_folder) to process all languages of a book together
    from collections import defaultdict
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in entries:
        pope_folder = _pope_folder_from_path(e.get("path", ""))
        groups[(e["title"], pope_folder)].append(e)

    print(f"Documentos unicos: {len(groups)}")
    print("=" * 60)

    doc_num = 0
    for (title, pope_folder), doc_entries in groups.items():
        doc_num += 1
        author_display = POPE_FOLDER_TO_CANONICAL.get(pope_folder, pope_folder)
        type_key = doc_entries[0].get("type_key", "outro")
        year = doc_entries[0].get("year", "?")
        print(f"\n[{doc_num}/{len(groups)}] {title} ({year}) — {author_display}")

        with SessionLocal() as db:
            book, created = _get_or_create_book(db, doc_entries[0], pope_folder, dry_run)

            if dry_run:
                for e in doc_entries:
                    lang = e.get("language", "?").upper()
                    print(f"  [dry] {lang}: {os.path.basename(e.get('path',''))}")
                    saved += 1
                continue

            if book is None:
                errors += 1
                continue

            book_id = book.id

            for entry in doc_entries:
                stored_path = entry.get("path", "")
                lang = entry.get("language", "pt")
                fname = os.path.basename(stored_path)

                # Resume check
                if resume and os.path.normpath(stored_path) in existing_paths:
                    print(f"  [{lang.upper()}] Ja no banco — pulando.")
                    skipped += 1
                    continue

                if not os.path.isfile(stored_path):
                    print(f"  [{lang.upper()}] ARQUIVO NAO ENCONTRADO: {stored_path}")
                    errors += 1
                    continue

                print(f"  [{lang.upper()}] Extraindo: {fname}")

                # Extract text
                try:
                    pages = extractor.extract(stored_path)
                    total_chars = sum(len(p.get("text", "")) for p in pages)
                    print(f"         {len(pages)} paginas, {total_chars} chars")
                except Exception as exc:
                    print(f"         ERRO na extracao: {exc}")
                    errors += 1
                    continue

                if total_chars < 100:
                    print(f"         AVISO: texto muito curto — pulando.")
                    errors += 1
                    continue

                # Chunk
                raw_chunks = chunker.chunk(pages, document_meta={})
                print(f"         {len(raw_chunks)} chunks")

                # Create BookFile
                book_file = BookFile(
                    book_id=book_id,
                    original_filename=fname,
                    stored_path=stored_path,
                    volume_number=None,
                    editor="Vatican.va",
                    translator=None,
                )
                db.add(book_file)
                db.flush()
                book_file_id = book_file.id

                # Create Chunk records
                chunk_records: list[Chunk] = []
                for i, cd in enumerate(raw_chunks):
                    c = Chunk(
                        book_id=book_id,
                        book_file_id=book_file_id,
                        text=cd["text"],
                        sequence_index=i,
                        pdf_page=cd.get("pdf_page"),
                        char_offset_start=cd.get("char_offset_start"),
                        char_offset_end=cd.get("char_offset_end"),
                    )
                    db.add(c)
                    chunk_records.append(c)

                db.flush()

                # Index
                es_items = []
                chroma_items = []
                semantic_lang = normalize_lang(lang)
                for chunk in chunk_records:
                    doc_es = {
                        "book_id": book_id,
                        "book_file_id": book_file_id,
                        "text": chunk.text,
                        "author": author_display,
                        "work_title": title,
                        "collection": "MAG",
                        "language": lang,
                        "pdf_page": chunk.pdf_page,
                        "edition_label": f"Vatican.va {LANG_LABEL.get(lang, lang.upper())}",
                    }
                    es_items.append((chunk.id, doc_es))
                    chroma_items.append((
                        chunk.id,
                        chunk.text,
                        {"book_id": book_id, "author": author_display, "work_title": title},
                    ))

                try:
                    text_search.index_chunks(es_items)
                    if semantic_search:
                        semantic_search.index_chunks(chroma_items, language=semantic_lang)
                    print(f"         Indexado OK ({len(chunk_records)} chunks)")
                    saved += 1
                except Exception as exc:
                    print(f"         ERRO na indexacao: {exc}")
                    db.rollback()
                    errors += 1
                    continue

            # Mark book as done
            if not dry_run and book:
                db_book = db.query(Book).filter(Book.id == book_id).first()
                if db_book:
                    db_book.ingest_status = "done"
            db.commit()

    print("\n" + "=" * 60)
    print(f"Concluido: {saved} arquivos ingeridos, {skipped} pulados, {errors} erros.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingere PDFs pontificios no Vera.Fidei")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Pula BookFiles ja no banco")
    parser.add_argument("--pope", default="", help="Filtra por papa (substring)")
    args = parser.parse_args()
    ingest(dry_run=args.dry_run, resume=args.resume, pope_filter=args.pope)


if __name__ == "__main__":
    main()
