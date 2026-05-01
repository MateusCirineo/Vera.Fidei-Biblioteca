"""
Conector Vatican.va — ingere encíclicas e documentos papais.

Quando a fonte tem `pdf_url`, baixa o PDF, armazena como BookFile real e extrai
texto do PDF via PDFExtractor. Sem `pdf_url`, extrai texto do HTML (fallback).

Uso:
    cd vera_fidei_starter/backend
    python scripts/ingest_vatican.py [--dry-run] [--source TITLE]

Flags:
    --dry-run    Exibe o que seria ingerido sem gravar no DB nem nos índices.
    --source     Ingere apenas a fonte com esse título (substring, case-insensitive).
"""
from __future__ import annotations

import argparse
import re
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pdfs")

_DOC_TYPE_FOLDER = {
    "enciclica": "enciclicas",
    "bula": "bulas",
    "constituicao_apostolica": "constituicoes_apostolicas",
    "carta_apostolica": "cartas_apostolicas",
    "concilio": "concilios",
    "catecismo": "catecismos",
    "direito_canonico": "direito_canonico",
    "outro": "outros",
}

def _pdf_subdir(source: dict, work_title: str = "") -> str:
    """Retorna o caminho da subpasta organizada para o PDF da fonte.

    Estrutura: pdfs/{tipo}/Papa {Nome}/{Título da Obra}/
    """
    import re as _re

    def _safe_folder(name: str) -> str:
        return _re.sub(r'[<>:"/\\|?*]', "", name).strip()

    type_folder = _DOC_TYPE_FOLDER.get(source.get("document_type", "outro"), "outros")
    title = _safe_folder(work_title or source.get("title", ""))
    pope = source.get("pope", "").strip()
    if pope:
        pope_folder = pope if pope.startswith("Papa ") else f"Papa {pope}"
        base = os.path.join(PDF_DIR, type_folder, pope_folder)
        return os.path.join(base, title) if title else base
    council = source.get("council_name", "").strip()
    if council:
        base = os.path.join(PDF_DIR, type_folder, _safe_folder(council))
        return os.path.join(base, title) if title else base
    return os.path.join(PDF_DIR, type_folder, title) if title else os.path.join(PDF_DIR, type_folder)

# ---------------------------------------------------------------------------
# Fontes alvo
# ---------------------------------------------------------------------------

VATICAN_SOURCES: list[dict] = [
    # ── Encíclicas antigas — sem PDF no Vatican.va, indexadas via HTML ────────
    {
        "url": "https://www.vatican.va/content/leo-xiii/pt/encyclicals/documents/hf_l-xiii_enc_15051891_rerum-novarum.html",
        "title": "Rerum Novarum",
        "author": "Papa Leão XIII",
        "pope": "Leão XIII",
        "year": 1891,
        "language": "pt",
        "collection": "MAG",
        "document_type": "enciclica",
        "edition_label": "Vatican.va — tradução oficial PT",
        "source_label": "Vatican.va",
    },
    {
        "url": "https://www.vatican.va/content/pius-xi/pt/encyclicals/documents/hf_p-xi_enc_19310515_quadragesimo-anno.html",
        "title": "Quadragesimo Anno",
        "author": "Papa Pio XI",
        "pope": "Pio XI",
        "year": 1931,
        "language": "pt",
        "collection": "MAG",
        "document_type": "enciclica",
        "edition_label": "Vatican.va — tradução oficial PT",
        "source_label": "Vatican.va",
    },
    {
        "url": "https://www.vatican.va/content/john-xxiii/pt/encyclicals/documents/hf_j-xxiii_enc_11041963_pacem.html",
        "title": "Pacem in Terris",
        "author": "Papa João XXIII",
        "pope": "João XXIII",
        "year": 1963,
        "language": "pt",
        "collection": "MAG",
        "document_type": "enciclica",
        "edition_label": "Vatican.va — tradução oficial PT",
        "source_label": "Vatican.va",
    },
    {
        "url": "https://www.vatican.va/content/paul-vi/pt/encyclicals/documents/hf_p-vi_enc_25071968_humanae-vitae.html",
        "title": "Humanae Vitae",
        "author": "Papa Paulo VI",
        "pope": "Paulo VI",
        "year": 1968,
        "language": "pt",
        "collection": "MAG",
        "document_type": "enciclica",
        "edition_label": "Vatican.va — tradução oficial PT",
        "source_label": "Vatican.va",
    },
    {
        "url": "https://www.vatican.va/content/john-paul-ii/pt/encyclicals/documents/hf_jp-ii_enc_04031979_redemptor-hominis.html",
        "title": "Redemptor Hominis",
        "author": "Papa João Paulo II",
        "pope": "João Paulo II",
        "year": 1979,
        "language": "pt",
        "collection": "MAG",
        "document_type": "enciclica",
        "edition_label": "Vatican.va — tradução oficial PT",
        "source_label": "Vatican.va",
    },
    # ── Encíclicas de Francisco — com PDF real disponível no Vatican.va ───────
    {
        "url": "https://www.vatican.va/content/francesco/pt/encyclicals/documents/papa-francesco_20130629_enciclica-lumen-fidei.html",
        "pdf_url": "https://www.vatican.va/content/dam/francesco/pdf/encyclicals/documents/papa-francesco_20130629_enciclica-lumen-fidei_po.pdf",
        "pdf_filename": "lumen-fidei_francisco_2013_pt.pdf",
        "title": "Lumen Fidei",
        "author": "Papa Francisco",
        "pope": "Francisco",
        "year": 2013,
        "language": "pt",
        "collection": "MAG",
        "document_type": "enciclica",
        "edition_label": "Vatican.va — PDF oficial PT",
        "source_label": "Vatican.va",
    },
    {
        "url": "https://www.vatican.va/content/francesco/pt/encyclicals/documents/papa-francesco_20150524_enciclica-laudato-si.html",
        "pdf_url": "https://www.vatican.va/content/dam/francesco/pdf/encyclicals/documents/papa-francesco_20150524_enciclica-laudato-si_po.pdf",
        "pdf_filename": "laudato-si_francisco_2015_pt.pdf",
        "title": "Laudato Si",
        "author": "Papa Francisco",
        "pope": "Francisco",
        "year": 2015,
        "language": "pt",
        "collection": "MAG",
        "document_type": "enciclica",
        "edition_label": "Vatican.va — PDF oficial PT",
        "source_label": "Vatican.va",
    },
]

# ---------------------------------------------------------------------------
# HTML extraction (fallback para fontes sem pdf_url)
# ---------------------------------------------------------------------------

_USER_AGENT = "Mozilla/5.0 (compatible; VeraFideiBot/1.0; +https://verafidei.example.com)"

_REMOVE_SELECTORS = [
    "header", "footer", "nav", "aside",
    ".breadcrumb", ".toolbar", ".social", ".share",
    "#breadcrumb", "#toolbar",
    "script", "style", "noscript",
]


def _fetch_html(url: str, timeout: int = 30) -> str:
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx não instalado — rode: pip install httpx")
    resp = httpx.get(url, timeout=timeout, headers={"User-Agent": _USER_AGENT}, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _fetch_pdf_bytes(url: str, timeout: int = 120) -> bytes:
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx não instalado — rode: pip install httpx")
    resp = httpx.get(url, timeout=timeout, headers={"User-Agent": _USER_AGENT}, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def _extract_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("beautifulsoup4 não instalado — rode: pip install beautifulsoup4")

    soup = BeautifulSoup(html, "html.parser")
    for selector in _REMOVE_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()

    main = (
        soup.find("div", class_=re.compile(r"testo|content|body|document", re.I))
        or soup.find("article")
        or soup.find("main")
        or soup.body
    )

    if main is None:
        return soup.get_text(separator="\n")

    paragraphs = []
    for tag in main.find_all(["p", "h1", "h2", "h3", "h4", "blockquote"]):
        text = tag.get_text(separator=" ", strip=True)
        if len(text) >= 40:
            paragraphs.append(text)

    if paragraphs:
        return "\n\n".join(paragraphs)
    return main.get_text(separator="\n")


def _clean_text(text: str) -> str:
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def _already_ingested(title: str, collection: str, db) -> bool:
    from models.database import Book
    existing = db.query(Book).filter(
        Book.title == title,
        Book.collection == collection,
    ).first()
    return existing is not None


def _ingest_from_pdf(source: dict, book_id: int, db) -> tuple[list, int | None]:
    """
    Baixa o PDF, salva em disco, cria BookFile e extrai chunks via PDFExtractor.
    Retorna (raw_chunks, book_file_id).
    """
    from models.database import BookFile
    from ingestion.pdf_extractor import PDFExtractor
    from ingestion.chunker import Chunker

    pdf_url = source["pdf_url"]
    title = source.get("title", f"doc_{book_id}")
    lang = source.get("language", "pt")

    # Build clean filename: {slug}_{lang}.pdf
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().strip()).strip("-")
    pdf_filename = f"{slug}_{lang}.pdf"

    print(f"  Baixando PDF: {pdf_url}")
    try:
        pdf_bytes = _fetch_pdf_bytes(pdf_url)
    except Exception as exc:
        print(f"  ERRO ao baixar PDF: {exc} — caindo para extração HTML.")
        return [], None

    subdir = _pdf_subdir(source, work_title=title)
    os.makedirs(subdir, exist_ok=True)
    stored_path = os.path.join(subdir, pdf_filename)
    with open(stored_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"  PDF salvo: {stored_path} ({len(pdf_bytes)//1024} KB)")

    book_file = BookFile(
        book_id=book_id,
        original_filename=pdf_filename,
        stored_path=stored_path,
        volume_number=None,
    )
    db.add(book_file)
    db.flush()
    book_file_id = book_file.id

    extractor = PDFExtractor()
    pages = extractor.extract(stored_path)
    chunker = Chunker()
    raw_chunks = chunker.chunk(pages, document_meta={})
    print(f"  Extraído do PDF: {len(pages)} páginas, {len(raw_chunks)} chunks")
    return raw_chunks, book_file_id


def _ingest_from_html(source: dict) -> list:
    """Extrai texto do HTML e retorna chunks como lista de dicts (sem book_file_id)."""
    from ingestion.chunker import Chunker

    print(f"  Buscando HTML de {source['url']}")
    try:
        html = _fetch_html(source["url"])
    except Exception as exc:
        print(f"  ERRO ao baixar HTML: {exc}")
        return []
    time.sleep(1)

    raw_text = _clean_text(_extract_text(html))
    if len(raw_text) < 500:
        print(f"  AVISO: texto extraído muito curto ({len(raw_text)} chars) — pulando.")
        return []

    word_count = len(raw_text.split())
    print(f"  Texto extraído do HTML: {len(raw_text)} chars / {word_count} palavras")

    chunker = Chunker()
    pages = [{"page_number": 1, "text": raw_text}]
    return chunker.chunk(pages, document_meta={})


def ingest_source(source: dict, dry_run: bool = False) -> int:
    """Returns number of chunks indexed."""
    title = source["title"]
    has_pdf = bool(source.get("pdf_url"))
    print(f"\n[Vatican.va] Ingerindo: {title} ({source['year']}) [{'PDF' if has_pdf else 'HTML'}]")

    if dry_run:
        print(f"  [dry-run] URL: {source['url']}")
        if has_pdf:
            print(f"  [dry-run] PDF: {source['pdf_url']}")
        return 0

    from models.database import SessionLocal, Book, Chunk
    from search.text_search import TextSearchClient
    from utils.language import normalize_lang

    try:
        from search.semantic_search import SemanticSearchClient
        _semantic_available = True
    except Exception as exc:
        print(f"  AVISO: indexação semântica desativada ({exc.__class__.__name__}). Só ES.")
        _semantic_available = False

    with SessionLocal() as db:
        if _already_ingested(title, source["collection"], db):
            print(f"  Já ingerido — pulando.")
            return 0

        book = Book(
            title=title,
            author=source["author"],
            canonical_author=source["author"],
            canonical_title=title,
            language=source["language"],
            collection=source["collection"],
            library_section="documentos",
            document_type=source["document_type"],
            pope=source.get("pope"),
            document_year=source.get("year"),
            is_primary_source=True,
            edition_label=source.get("edition_label", ""),
            source_label=source.get("source_label", "Vatican.va"),
            ingest_status="indexing",
        )
        db.add(book)
        db.flush()
        book_id = book.id
        print(f"  Book ID: {book_id}")

        book_file_id: int | None = None

        if has_pdf:
            raw_chunks, book_file_id = _ingest_from_pdf(source, book_id, db)
            if not raw_chunks:
                # Fallback para HTML se PDF falhar
                raw_chunks = _ingest_from_html(source)
        else:
            raw_chunks = _ingest_from_html(source)

        if not raw_chunks:
            db.rollback()
            print(f"  ERRO: nenhum chunk extraído — revertendo.")
            return 0

        for i, chunk_data in enumerate(raw_chunks):
            chunk_data["sequence_index"] = i

        print(f"  Chunks: {len(raw_chunks)}")

        chunk_records: list[Chunk] = []
        for chunk_data in raw_chunks:
            chunk = Chunk(
                book_id=book_id,
                book_file_id=book_file_id,
                text=chunk_data["text"],
                sequence_index=chunk_data.get("sequence_index"),
                pdf_page=chunk_data.get("pdf_page"),
                char_offset_start=chunk_data.get("char_offset_start"),
                char_offset_end=chunk_data.get("char_offset_end"),
            )
            db.add(chunk)
            chunk_records.append(chunk)

        db.flush()

        semantic_language = normalize_lang(source["language"])
        text_search = TextSearchClient()
        semantic_search = SemanticSearchClient() if _semantic_available else None

        es_items: list[tuple[int, dict]] = []
        chroma_items: list[tuple[int, str, dict]] = []

        for chunk in chunk_records:
            es_doc = {
                "book_id": book_id,
                "book_file_id": book_file_id,
                "text": chunk.text,
                "author": source["author"],
                "work_title": title,
                "collection": source["collection"],
                "language": source["language"],
                "pdf_page": chunk.pdf_page,
                "edition_label": source.get("edition_label", ""),
            }
            es_items.append((chunk.id, es_doc))
            chroma_items.append((
                chunk.id,
                chunk.text,
                {"book_id": book_id, "author": source["author"], "work_title": title},
            ))

        try:
            text_search.index_chunks(es_items)
            if semantic_search is not None:
                semantic_search.index_chunks(chroma_items, language=semantic_language)
            else:
                print("  AVISO: ChromaDB pulado — re-indexe via backend quando disponível.")
        except Exception as exc:
            db.rollback()
            print(f"  ERRO ao indexar: {exc}")
            return 0

        book.ingest_status = "done"
        db.commit()
        tipo = f"book_file_id={book_file_id}" if book_file_id else "sem BookFile (HTML)"
        print(f"  OK — {len(chunk_records)} chunks indexados (book_id={book_id}, {tipo})")
        return len(chunk_records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingere encíclicas do Vatican.va no Vera.Fidei")
    parser.add_argument("--dry-run", action="store_true", help="Não gravar — apenas mostrar o que seria feito")
    parser.add_argument("--source", default="", help="Filtrar por título (substring)")
    args = parser.parse_args()

    sources = VATICAN_SOURCES
    if args.source:
        sources = [s for s in sources if args.source.lower() in s["title"].lower()]
        if not sources:
            print(f"Nenhuma fonte com título contendo '{args.source}'.")
            sys.exit(1)

    total_chunks = 0
    for source in sources:
        total_chunks += ingest_source(source, dry_run=args.dry_run)

    print(f"\n{'[dry-run] ' if args.dry_run else ''}Total: {total_chunks} chunks ingeridos de {len(sources)} fontes.")


if __name__ == "__main__":
    main()
