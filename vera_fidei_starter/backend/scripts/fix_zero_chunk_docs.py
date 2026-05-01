"""
Corrige livros de documentos_pontificios que foram marcados como 'done'
mas ficaram sem BookFiles nem Chunks (bug do rollback no ingest_pontificios.py).

Uso:
    cd vera_fidei_starter/backend
    python scripts/fix_zero_chunk_docs.py [--dry-run]
"""
from __future__ import annotations
import argparse, json, os, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MANIFEST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pdfs", "documentos_pontificios", "manifest.jsonl"
)

LANG_LABEL = {
    "pt": "Português", "en": "English", "es": "Español",
    "fr": "Français", "de": "Deutsch", "it": "Italiano",
    "la": "Latim", "pl": "Polski", "ar": "العربية",
}

POPE_FOLDER_TO_SHORT = {
    "Papa Leao XIII":     "Leão XIII",
    "Papa Pio X":         "Pio X",
    "Papa Bento XV":      "Bento XV",
    "Papa Pio XI":        "Pio XI",
    "Papa Pio XII":       "Pio XII",
    "Papa Joao XXIII":    "João XXIII",
    "Papa Paulo VI":      "Paulo VI",
    "Papa Joao Paulo I":  "João Paulo I",
    "Papa Joao Paulo II": "João Paulo II",
    "Papa Bento XVI":     "Bento XVI",
    "Papa Francisco":     "Francisco",
}

POPE_FOLDER_TO_CANONICAL = {
    "Papa Leao XIII":     "Papa Leão XIII",
    "Papa Pio X":         "Papa Pio X",
    "Papa Bento XV":      "Papa Bento XV",
    "Papa Pio XI":        "Papa Pio XI",
    "Papa Pio XII":       "Papa Pio XII",
    "Papa Joao XXIII":    "Papa João XXIII",
    "Papa Paulo VI":      "Papa Paulo VI",
    "Papa Joao Paulo I":  "Papa João Paulo I",
    "Papa Joao Paulo II": "Papa João Paulo II",
    "Papa Bento XVI":     "Papa Bento XVI",
    "Papa Francisco":     "Papa Francisco",
}


def _pope_folder_from_path(p: str) -> str:
    for part in p.replace("\\", "/").split("/"):
        if part.startswith("Papa "):
            return part
    return ""


def run(dry_run: bool, no_semantic: bool = False) -> None:
    from models.database import SessionLocal, Book, BookFile, Chunk
    from ingestion.pdf_extractor import PDFExtractor
    from ingestion.chunker import Chunker
    from search.text_search import TextSearchClient
    from utils.language import normalize_lang

    try:
        from search.semantic_search import SemanticSearchClient
        semantic_ok = True
    except Exception as e:
        print(f"AVISO: ChromaDB indisponivel — so ES. ({e.__class__.__name__})")
        semantic_ok = False

    # Find broken books (done + 0 chunks + in documentos)
    with SessionLocal() as db:
        all_with_chunks = set(r[0] for r in db.query(Chunk.book_id).distinct().all())
        broken = db.query(Book).filter(
            Book.library_section == "documentos",
            ~Book.id.in_(all_with_chunks),
        ).all()
        broken_info = [(b.id, b.title, b.pope, b.document_type) for b in broken]

    print(f"Livros sem chunks: {len(broken_info)}")
    if dry_run:
        for bid, title, pope, dtype in broken_info[:10]:
            print(f"  [{bid}] {title} — {pope} ({dtype})")
        if len(broken_info) > 10:
            print(f"  ... e mais {len(broken_info)-10}")
        return

    # Load manifest grouped by (title, pope_folder)
    from collections import defaultdict
    groups: dict[tuple, list[dict]] = defaultdict(list)
    with open(MANIFEST, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                pope_folder = _pope_folder_from_path(e.get("path", ""))
                groups[(e["title"], pope_folder)].append(e)
            except Exception:
                pass

    extractor = PDFExtractor()
    chunker = Chunker()
    text_search = TextSearchClient()
    semantic_search = SemanticSearchClient() if semantic_ok else None

    broken_set = {(title, pope) for _, title, pope, _ in broken_info}

    processed = fixed = skipped = errors = 0

    for (title, pope_folder), entries in groups.items():
        pope_short = POPE_FOLDER_TO_SHORT.get(pope_folder, "")
        if (title, pope_short) not in broken_set:
            continue

        processed += 1
        author_display = POPE_FOLDER_TO_CANONICAL.get(pope_folder, pope_folder)
        year = entries[0].get("year", "?")
        print(f"\n[{processed}] {title} ({year}) — {author_display}")

        # Find book in DB
        with SessionLocal() as db:
            book = db.query(Book).filter(
                Book.title == title,
                Book.pope == pope_short,
            ).first()

            if not book:
                print(f"  AVISO: livro nao encontrado no DB — pulando.")
                skipped += 1
                continue

            book_id = book.id

            for entry in entries:
                stored_path = entry.get("path", "")
                lang = entry.get("language", "pt")
                fname = os.path.basename(stored_path)

                if not os.path.isfile(stored_path):
                    print(f"  [{lang.upper()}] Arquivo nao encontrado — pulando.")
                    continue

                # Check if BookFile already exists for this path
                existing_bf = db.query(BookFile).filter(
                    BookFile.stored_path == stored_path
                ).first()
                if existing_bf:
                    # Check if it has chunks
                    n_chunks = db.query(Chunk).filter(
                        Chunk.book_file_id == existing_bf.id
                    ).count()
                    if n_chunks > 0:
                        print(f"  [{lang.upper()}] Ja tem {n_chunks} chunks — pulando.")
                        continue

                print(f"  [{lang.upper()}] Extraindo: {fname}")
                try:
                    pages = extractor.extract(stored_path)
                    total_chars = sum(len(p.get("text", "")) for p in pages)
                    print(f"         {len(pages)} paginas, {total_chars} chars")
                    if total_chars < 100:
                        print(f"         Texto muito curto — pulando.")
                        continue
                except Exception as exc:
                    print(f"         ERRO extracao: {exc}")
                    errors += 1
                    continue

                raw_chunks = chunker.chunk(pages, document_meta={})
                print(f"         {len(raw_chunks)} chunks")

                # Use separate session per file to avoid rollback cascade
                try:
                    with SessionLocal() as db2:
                        if existing_bf:
                            bf_id = existing_bf.id
                        else:
                            bf = BookFile(
                                book_id=book_id,
                                original_filename=fname,
                                stored_path=stored_path,
                                volume_number=None,
                                editor="Vatican.va",
                            )
                            db2.add(bf)
                            db2.flush()
                            bf_id = bf.id

                        chunk_records = []
                        for i, cd in enumerate(raw_chunks):
                            c = Chunk(
                                book_id=book_id,
                                book_file_id=bf_id,
                                text=cd["text"],
                                sequence_index=i,
                                pdf_page=cd.get("pdf_page"),
                                char_offset_start=cd.get("char_offset_start"),
                                char_offset_end=cd.get("char_offset_end"),
                            )
                            db2.add(c)
                            chunk_records.append(c)
                        db2.flush()

                        semantic_lang = normalize_lang(lang)
                        es_items = [(c.id, {
                            "book_id": book_id, "book_file_id": bf_id,
                            "text": c.text, "author": author_display,
                            "work_title": title, "collection": "MAG",
                            "language": lang, "pdf_page": c.pdf_page,
                            "edition_label": f"Vatican.va {LANG_LABEL.get(lang, lang.upper())}",
                        }) for c in chunk_records]
                        chroma_items = [(c.id, c.text, {
                            "book_id": book_id, "author": author_display, "work_title": title
                        }) for c in chunk_records]

                        text_search.index_chunks(es_items)
                        if semantic_search and not no_semantic:
                            semantic_search.index_chunks(chroma_items, language=semantic_lang)

                        db2.commit()
                        print(f"         OK ({len(chunk_records)} chunks)")
                        fixed += 1

                except Exception as exc:
                    print(f"         ERRO indexacao: {exc}")
                    errors += 1
                    continue

            # Mark book as done and update language
            with SessionLocal() as db3:
                b = db3.query(Book).filter(Book.id == book_id).first()
                if b:
                    b.ingest_status = "done"
                    b.language = "pt"
                db3.commit()

    print(f"\n{'='*60}")
    print(f"Concluido: {fixed} arquivos corrigidos, {skipped} pulados, {errors} erros.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-semantic", action="store_true", help="Pula indexacao ChromaDB (mais rapido)")
    args = p.parse_args()
    run(dry_run=args.dry_run, no_semantic=args.no_semantic)


if __name__ == "__main__":
    main()
