"""
Baixa documentos específicos do Vatican.va que estão faltando no banco.
Reutiliza toda a lógica de download/fallback do scrape_vatican_pdfs.py.

Uso:
    cd vera_fidei_starter/backend
    python scripts/scrape_missing_docs.py [--dry-run] [--ingest]

Flags:
    --dry-run   Mostra o que seria baixado sem salvar
    --ingest    Após baixar, ingere no banco automaticamente
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import helpers from the main scraper
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "scraper",
    Path(__file__).resolve().parent / "scrape_vatican_pdfs.py"
)
scraper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scraper)

# ---------------------------------------------------------------------------
# The 21 missing documents found on Vatican.va
# ---------------------------------------------------------------------------
MISSING_DOCS = [
    {
        "title": "Vi e Ben Noto",
        "author": "Leão XIII",
        "year": 1887,
        "doc_type_pt": "Encíclica",
        "folder": "Enciclicas",
        "type_key": "enciclica",
        "page_url": "https://www.vatican.va/holy_father/leo_xiii/encyclicals/documents/hf_l-xiii_enc_20091887_vi-e-ben-noto_en.html",
    },
    {
        "title": "Pastoralis",
        "author": "Leão XIII",
        "year": 1891,
        "doc_type_pt": "Encíclica",
        "folder": "Enciclicas",
        "type_key": "enciclica",
        "page_url": "https://www.vatican.va/holy_father/leo_xiii/encyclicals/documents/hf_l-xiii_enc_25071891_pastoralis_en.html",
    },
    {
        "title": "Tertio Millennio Adveniente",
        "author": "João Paulo II",
        "year": 1994,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_10111994_tertio-millennio-adveniente_po.html",
    },
    {
        "title": "Orientale Lumen",
        "author": "João Paulo II",
        "year": 1995,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_02051995_orientale-lumen_po.html",
    },
    {
        "title": "Uniao de Brest",
        "author": "João Paulo II",
        "year": 1995,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_19951112_iv-cent-union-brest_po.html",
    },
    {
        "title": "Operosam Diem",
        "author": "João Paulo II",
        "year": 1996,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_01121996_operosam-diem_lt.html",
    },
    {
        "title": "Divini Amoris Scientia",
        "author": "João Paulo II",
        "year": 1997,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_19101997_divini-amoris_po.html",
    },
    {
        "title": "Laetamur Magnopere",
        "author": "João Paulo II",
        "year": 1997,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_15081997_laetamur_it.html",
    },
    {
        "title": "Dies Domini",
        "author": "João Paulo II",
        "year": 1998,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_05071998_dies-domini_po.html",
    },
    {
        "title": "Inter Munera Academiarum",
        "author": "João Paulo II",
        "year": 1999,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_19990128_inter-munera-academiarum_po.html",
    },
    {
        "title": "Novo Millennio Ineunte",
        "author": "João Paulo II",
        "year": 2001,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_20010106_novo-millennio-ineunte_po.html",
    },
    {
        "title": "Spiritus et Sponsa",
        "author": "João Paulo II",
        "year": 2003,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_20031204_sacra-liturgia_po.html",
    },
    {
        "title": "Mane Nobiscum Domine",
        "author": "João Paulo II",
        "year": 2004,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_20041008_mane-nobiscum-domine_po.html",
    },
    {
        "title": "Miserentissimus Redemptor",
        "author": "Pio XI",
        "year": 1928,
        "doc_type_pt": "Encíclica",
        "folder": "Enciclicas",
        "type_key": "enciclica",
        "page_url": "https://www.vatican.va/holy_father/pius_xi/encyclicals/documents/hf_p-xi_enc_08051928_miserentissimus-redemptor_en.html",
    },
    {
        "title": "Mens Nostra",
        "author": "Pio XI",
        "year": 1929,
        "doc_type_pt": "Encíclica",
        "folder": "Enciclicas",
        "type_key": "enciclica",
        "page_url": "https://www.vatican.va/holy_father/pius_xi/encyclicals/documents/hf_p-xi_enc_20121929_mens-nostra_en.html",
    },
    {
        "title": "Casti Connubii",
        "author": "Pio XI",
        "year": 1930,
        "doc_type_pt": "Encíclica",
        "folder": "Enciclicas",
        "type_key": "enciclica",
        "page_url": "https://www.vatican.va/holy_father/pius_xi/encyclicals/documents/hf_p-xi_enc_31121930_casti-connubii_en.html",
    },
    {
        "title": "Humanae Salutis",
        "author": "João XXIII",
        "year": 1961,
        "doc_type_pt": "Constituição Apostólica",
        "folder": "Constituicoes Apostolicas",
        "type_key": "constituicao_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_xxiii/apost_constitutions/documents/hf_j-xxiii_apc_19611225_humanae-salutis_po.html",
    },
    {
        "title": "Euntes in Mundum Universum",
        "author": "João Paulo II",
        "year": 1988,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_25011988_euntes-in-mundum-universum_it.html",
    },
    {
        "title": "Mulieris Dignitatem",
        "author": "João Paulo II",
        "year": 1988,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_15081988_mulieris-dignitatem_po.html",
    },
    {
        "title": "Vicesimus Quintus Annus",
        "author": "João Paulo II",
        "year": 1988,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_04121988_vicesimus-quintus-annus_it.html",
    },
    {
        "title": "Ordinatio Sacerdotalis",
        "author": "João Paulo II",
        "year": 1994,
        "doc_type_pt": "Carta Apostólica",
        "folder": "Cartas Apostolicas",
        "type_key": "carta_apostolica",
        "page_url": "https://www.vatican.va/holy_father/john_paul_ii/apost_letters/documents/hf_jp-ii_apl_22051994_ordinatio-sacerdotalis_po.html",
    },
]

POPE_SHORT = {
    "Leão XIII": "Leão XIII",
    "Pio X": "Pio X",
    "Bento XV": "Bento XV",
    "Pio XI": "Pio XI",
    "Pio XII": "Pio XII",
    "João XXIII": "João XXIII",
    "Paulo VI": "Paulo VI",
    "João Paulo I": "João Paulo I",
    "João Paulo II": "João Paulo II",
    "Bento XVI": "Bento XVI",
    "Francisco": "Francisco",
}

POPE_CANONICAL = {k: f"Papa {k}" for k in POPE_SHORT}

LANG_LABEL = {
    "pt": "Português", "en": "English", "es": "Español",
    "fr": "Français", "de": "Deutsch", "it": "Italiano",
    "la": "Latim", "pl": "Polski", "ar": "العربية",
}


# Vatican old-style URL suffix codes for each language
_OLD_LANG_CODES = {
    "pt": ["po", "pt"],
    "en": ["en"],
    "es": ["es", "sp"],
    "fr": ["fr"],
    "de": ["de", "ge"],
    "it": ["it"],
    "la": ["la"],
    "pl": ["pl"],
    "ar": ["ar"],
}


def _discover_old_style_langs(page_url: str) -> dict[str, str]:
    """
    For old Vatican URLs like /holy_father/.../xxx_po.html,
    generate language variants by replacing the suffix code.
    Returns only languages where the page actually exists (HTTP 200).
    """
    import re
    from urllib.parse import urlparse

    path = urlparse(page_url).path
    # Only handle old-style /holy_father/ URLs
    if "/holy_father/" not in path and "/roman_curia/" not in path:
        return {}

    # Detect current lang code suffix
    m = re.search(r"_([a-z]{2,3})\.html?$", path, re.IGNORECASE)
    if not m:
        return {}

    base_path = path[: m.start()]  # everything before _XX.html
    ext = path[m.end() - len(".html"):]  # ".html" or ".htm"

    found: dict[str, str] = {}
    client = scraper._get_client()

    for lang, codes in _OLD_LANG_CODES.items():
        for code in codes:
            candidate = f"https://www.vatican.va{base_path}_{code}{ext}"
            try:
                r = client.head(candidate, follow_redirects=True)
                if r.status_code == 200:
                    found[lang] = candidate
                    break
            except Exception:
                pass

    return found


def _wayback_url(original_url: str) -> str | None:
    """Query Wayback Machine API for the most recent snapshot of a URL."""
    import json as _json
    api = f"https://archive.org/wayback/available?url={original_url}"
    try:
        client = scraper._get_client()
        r = client.get(api, timeout=15)
        data = _json.loads(r.text)
        snapshot = data.get("archived_snapshots", {}).get("closest", {})
        if snapshot.get("available") and snapshot.get("url"):
            return snapshot["url"]
    except Exception:
        pass
    return None


def _wayback_lang_url(original_url: str, lang_code: str, orig_lang_code: str) -> str | None:
    """Get Wayback Machine URL for a language variant of an old-style Vatican URL."""
    import re
    # Replace language suffix in the original URL
    new_url = re.sub(
        rf"_{re.escape(orig_lang_code)}(\.html?)$",
        f"_{lang_code}\\1",
        original_url,
        flags=re.IGNORECASE,
    )
    if new_url == original_url:
        return None
    return _wayback_url(new_url)


def _discover_old_style_langs_with_wayback(original_url: str, effective_url: str) -> dict[str, str]:
    """
    For old Vatican URLs, discover available languages.
    First tries Vatican.va direct access, then Wayback Machine for each language variant.
    """
    import re

    path = original_url
    m = re.search(r"_([a-z]{2,3})\.html?$", path, re.IGNORECASE)
    if not m:
        return {}

    orig_code = m.group(1).lower()
    base_path = path[: m.start()]
    ext = ".html"

    # Map Vatican URL lang codes to our lang codes
    code_to_lang = {
        "po": "pt", "pt": "pt",
        "en": "en",
        "es": "es", "sp": "es",
        "fr": "fr",
        "de": "de", "ge": "de",
        "it": "it",
        "la": "la", "lt": "la",
        "pl": "pl",
        "ar": "ar",
    }
    base_lang = code_to_lang.get(orig_code, orig_code)

    # All codes to try per language
    lang_codes = {
        "pt": ["po", "pt"],
        "en": ["en"],
        "es": ["es", "sp"],
        "fr": ["fr"],
        "de": ["de", "ge"],
        "it": ["it"],
        "la": ["la", "lt"],
        "pl": ["pl"],
        "ar": ["ar"],
    }

    found: dict[str, str] = {}
    client = scraper._get_client()

    for lang, codes in lang_codes.items():
        for code in codes:
            vatican_url = f"https://www.vatican.va{base_path}_{code}{ext}"
            # Try Vatican.va first (no redirect follow to avoid 404 loop)
            try:
                r = client.get(vatican_url, follow_redirects=False, timeout=10)
                if r.status_code == 200:
                    found[lang] = vatican_url
                    break
                elif r.status_code in (301, 302, 303, 307, 308):
                    # Follow redirect once manually
                    loc = r.headers.get("location", "")
                    if loc:
                        if loc.startswith("/"):
                            loc = f"https://www.vatican.va{loc}"
                        r2 = client.get(loc, follow_redirects=True, timeout=10)
                        if r2.status_code == 200 and len(r2.text) > 500:
                            found[lang] = loc
                            break
            except Exception:
                pass

            # Fallback: Wayback Machine
            wb = _wayback_url(vatican_url)
            if wb:
                found[lang] = wb
                break

        if lang not in found and lang == base_lang:
            # At minimum add the effective_url for the base language
            found[lang] = effective_url

    return found


def run(dry_run: bool, do_ingest: bool) -> None:
    import time

    total_saved = total_skipped = total_errors = 0

    for doc_num, doc in enumerate(MISSING_DOCS, 1):
        title = doc["title"]
        author = doc["author"]
        year = doc["year"]
        folder = doc["folder"]
        type_key = doc["type_key"]
        page_url = doc["page_url"]

        pope_folder = scraper._pope_folder_name(author)
        out_dir = scraper._doc_output_dir(pope_folder, folder, title, year)

        print(f"\n[{doc_num}/{len(MISSING_DOCS)}] {title} ({year}) — {author}")

        if dry_run:
            print(f"  [dry] -> {out_dir}")
            continue

        # Fetch the document page — try Vatican.va first, then Wayback Machine
        html = scraper._fetch_html(page_url)
        effective_url = page_url
        if not html:
            print(f"  Vatican.va indisponivel — tentando Wayback Machine...")
            wb_url = _wayback_url(page_url)
            if wb_url:
                print(f"  Wayback: {wb_url[-80:]}")
                html = scraper._fetch_html(wb_url)
                effective_url = wb_url
        if not html:
            print(f"  ERRO: documento inacessivel em Vatican.va e Wayback Machine")
            total_errors += 1
            continue

        # For old Vatican URLs (/holy_father/...), discover languages via old-style suffix
        lang_urls = _discover_old_style_langs_with_wayback(page_url, effective_url)
        if not lang_urls:
            lang_code = scraper._detect_lang_in_url(page_url) or "pt"
            lang_urls = {lang_code: effective_url}

        print(f"  Idiomas encontrados: {list(lang_urls.keys())}")
        out_dir.mkdir(parents=True, exist_ok=True)

        for lang, lang_page_url in lang_urls.items():
            filename = scraper._safe_filename(title, lang, ".pdf")
            out_path = out_dir / filename

            if out_path.exists() and out_path.stat().st_size > 1000:
                print(f"  [{lang.upper()}] Já existe — pulando.")
                total_skipped += 1
                continue

            # Fetch the language page
            lang_html = scraper._fetch_html(lang_page_url)
            if not lang_html:
                print(f"  [{lang.upper()}] ERRO: não foi possível baixar página")
                total_errors += 1
                continue

            pdf_bytes = None

            # Try real PDF links first
            pdf_links = scraper._find_pdf_links_on_page(lang_html, lang_page_url)
            for pdf_url in pdf_links:
                raw = scraper._fetch_bytes(pdf_url)
                if raw and scraper._is_real_pdf(raw):
                    pdf_bytes = raw
                    print(f"  [{lang.upper()}] PDF real: {len(raw)//1024}KB")
                    break
                time.sleep(0.3)

            # Fallback: generate from HTML
            if not pdf_bytes:
                text = scraper._clean_text(scraper._extract_text_from_html(lang_html))
                if len(text) < scraper.MIN_HTML_TEXT_CHARS:
                    print(f"  [{lang.upper()}] Texto muito curto ({len(text)}c) — pulando")
                    total_skipped += 1
                    continue
                author_display = POPE_CANONICAL.get(author, f"Papa {author}")
                pdf_bytes = scraper._text_to_pdf_bytes(title, author_display, lang, text)
                if not pdf_bytes:
                    print(f"  [{lang.upper()}] ERRO: não foi possível gerar PDF")
                    total_errors += 1
                    continue
                print(f"  [{lang.upper()}] Gerado do HTML ({len(text)} chars)")

            # Save PDF
            out_path.write_bytes(pdf_bytes)
            print(f"  [{lang.upper()}] Salvo: {filename}")

            # Append to manifest
            scraper._append_jsonl(scraper._MANIFEST_PATH, {
                "title": title,
                "author": author,
                "year": year,
                "language": lang,
                "type_key": type_key,
                "path": str(out_path),
            })
            total_saved += 1
            time.sleep(scraper.SLEEP_BETWEEN_REQUESTS)

    print(f"\n{'='*60}")
    print(f"Concluido: {total_saved} salvos, {total_skipped} pulados, {total_errors} erros")

    if do_ingest and not dry_run:
        print("\nIngerindo no banco...")
        _ingest_downloaded(MISSING_DOCS)


def _ingest_downloaded(docs: list[dict]) -> None:
    from models.database import SessionLocal, Book, BookFile, Chunk
    from ingestion.pdf_extractor import PDFExtractor
    from ingestion.chunker import Chunker
    from search.text_search import TextSearchClient
    from utils.language import normalize_lang

    extractor = PDFExtractor()
    chunker = Chunker()
    text_search = TextSearchClient()

    for doc in docs:
        title = doc["title"]
        author = doc["author"]
        year = doc["year"]
        folder = doc["folder"]
        type_key = doc["type_key"]

        pope_folder = scraper._pope_folder_name(author)
        pope_short = POPE_SHORT.get(author, author)
        pope_canonical = POPE_CANONICAL.get(author, f"Papa {author}")
        out_dir = scraper._doc_output_dir(pope_folder, folder, title, year)

        pdf_files = list(out_dir.glob("*.pdf")) if out_dir.exists() else []
        if not pdf_files:
            continue

        with SessionLocal() as db:
            book = db.query(Book).filter(
                Book.title == title, Book.pope == pope_short
            ).first()

            if not book:
                book = Book(
                    title=title,
                    author=pope_canonical,
                    canonical_author=pope_canonical,
                    canonical_title=title,
                    language="pt",
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
                db.commit()
                print(f"  Criado Book: {title}")
            else:
                print(f"  Book existente id={book.id}: {title}")

            book_id = book.id

        for pdf_path in pdf_files:
            import re as _re
            m = _re.search(r"- ([A-Z]{2,3})\.pdf$", pdf_path.name)
            lang = m.group(1).lower() if m else "pt"

            try:
                with SessionLocal() as db2:
                    existing = db2.query(BookFile).filter(
                        BookFile.stored_path == str(pdf_path)
                    ).first()
                    if existing:
                        nc = db2.query(Chunk).filter(Chunk.book_file_id == existing.id).count()
                        if nc > 0:
                            print(f"  [{lang.upper()}] Já indexado ({nc} chunks)")
                            continue

                    pages = extractor.extract(str(pdf_path))
                    total_chars = sum(len(p.get("text", "")) for p in pages)
                    if total_chars < 100:
                        print(f"  [{lang.upper()}] Texto muito curto — pulando")
                        continue

                    raw_chunks = chunker.chunk(pages, document_meta={})
                    print(f"  [{lang.upper()}] {len(raw_chunks)} chunks")

                    if not existing:
                        bf = BookFile(
                            book_id=book_id,
                            original_filename=pdf_path.name,
                            stored_path=str(pdf_path),
                            editor="Vatican.va",
                        )
                        db2.add(bf)
                        db2.flush()
                        bf_id = bf.id
                    else:
                        bf_id = existing.id

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
                        "text": c.text, "author": pope_canonical,
                        "work_title": title, "collection": "MAG",
                        "language": lang, "pdf_page": c.pdf_page,
                        "edition_label": f"Vatican.va {LANG_LABEL.get(lang, lang.upper())}",
                    }) for c in chunk_records]

                    text_search.index_chunks(es_items)
                    db2.commit()
                    print(f"  [{lang.upper()}] OK ({len(chunk_records)} chunks)")

            except Exception as exc:
                print(f"  [{lang.upper()}] ERRO: {exc}")

        with SessionLocal() as db3:
            b = db3.query(Book).filter(Book.id == book_id).first()
            if b:
                b.ingest_status = "done"
            db3.commit()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ingest", action="store_true", help="Ingere no banco após baixar")
    args = p.parse_args()
    run(dry_run=args.dry_run, do_ingest=args.ingest)


if __name__ == "__main__":
    main()
