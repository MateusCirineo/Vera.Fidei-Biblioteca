"""
scrape_vatican_pdfs.py — Vera.Fidei Vatican.va Document Scraper
================================================================
Downloads all papal documents from Vatican.va, organized in a folder
hierarchy under pdfs/documentos_pontificios/.

REPLACES the old scraper that produced blank PDFs (the URL+.pdf trick
does not work on Vatican.va — returns a seal-only placeholder PDF).

Strategy:
  1. Fetch the master list from papal_docs_list_po.html
  2. Filter by the document types we care about
  3. For each document: discover available languages via the HTML page
  4. For each language: look for a real PDF link on the page
       - Real PDFs live at content/dam/... URLs
       - If found → download, validate (>300 chars of extractable text)
       - If blank or not found → extract text from HTML → generate PDF via fpdf2
  5. Write manifest.jsonl + errors.jsonl

Usage:
    cd vera_fidei_starter/backend
    python scripts/scrape_vatican_pdfs.py [--dry-run] [--pope "Francisco"] [--resume]

Flags:
    --dry-run   Show what would be downloaded without saving anything
    --pope      Filter by pope name (substring match, e.g. "Francisco")
    --resume    Skip files that already exist on disk (default when --resume given)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

_MISSING: list[str] = []

try:
    import httpx
except ImportError:
    _MISSING.append("httpx")

try:
    from bs4 import BeautifulSoup
except ImportError:
    _MISSING.append("beautifulsoup4")

if _MISSING:
    print(
        f"[ERRO FATAL] Dependências ausentes: {', '.join(_MISSING)}\n"
        f"  Instale com: pip install {' '.join(_MISSING)}"
    )
    sys.exit(1)

try:
    import fitz  # PyMuPDF
    _FITZ_OK = True
except ImportError:
    print(
        "[AVISO] PyMuPDF (fitz) não encontrado — validação de PDFs desativada.\n"
        "  Instale com: pip install pymupdf"
    )
    _FITZ_OK = False

try:
    from fpdf import FPDF
    _FPDF_OK = True
except ImportError:
    print(
        "[AVISO] fpdf2 não encontrado — fallback salvará .txt em vez de .pdf gerado.\n"
        "  Instale com: pip install fpdf2"
    )
    _FPDF_OK = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.vatican.va"
LIST_URL = "https://www.vatican.va/offices/papal_docs_list_po.html"

USER_AGENT = (
    "Mozilla/5.0 (compatible; VeraFideiBot/2.0; "
    "+https://github.com/vera-fidei/vera-fidei)"
)

HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}

# Document types we want (Portuguese label as it appears on the Vatican page → config)
DOC_TYPE_MAP: dict[str, dict] = {
    "Encíclica":                 {"folder": "Enciclicas",               "type_key": "enciclica"},
    "Carta Apostólica":          {"folder": "Cartas Apostolicas",        "type_key": "carta_apostolica"},
    "Bula Papal":                {"folder": "Bulas",                     "type_key": "bula"},
    "Constituição Apostólica":   {"folder": "Constituicoes Apostolicas", "type_key": "constituicao_apostolica"},
    "Motu Proprio":              {"folder": "Motu Proprio",              "type_key": "motu_proprio"},
    "Exortação Apostólica":      {"folder": "Exortacoes Apostolicas",    "type_key": "exortacao_apostolica"},
}

# Normalised pope name → clean folder name (ASCII-safe display label)
POPE_FOLDER_MAP: dict[str, str] = {
    "Leão XIII":       "Papa Leao XIII",
    "Pio X":           "Papa Pio X",
    "Bento XV":        "Papa Bento XV",
    "Pio XI":          "Papa Pio XI",
    "Pio XII":         "Papa Pio XII",
    "João XXIII":      "Papa Joao XXIII",
    "Paulo VI":        "Papa Paulo VI",
    "João Paulo I":    "Papa Joao Paulo I",
    "João Paulo II":   "Papa Joao Paulo II",
    "Bento XVI":       "Papa Bento XVI",
    "Francisco":       "Papa Francisco",
}

# Languages to attempt for each document
LANGUAGES = ["pt", "en", "es", "fr", "de", "it", "la", "pl", "ar"]

# Language-code replacements used by Vatican.va in URL paths
LANG_URL_CODES: dict[str, list[str]] = {
    "pt": ["pt", "po"],
    "en": ["en"],
    "es": ["es"],
    "fr": ["fr"],
    "de": ["de"],
    "it": ["it"],
    "la": ["la"],
    "pl": ["pl"],
    "ar": ["ar"],
}

# Minimum characters of real text a valid PDF must have
MIN_PDF_TEXT_CHARS = 300

# Minimum HTML text length to be worth saving
MIN_HTML_TEXT_CHARS = 500

# ---------------------------------------------------------------------------
# Supplemental document list for Pope Francis (Francisco) — not on the
# Portuguese master list page, but available on Vatican.va under the newer
# /content/francesco/ URL structure.
# These are the principal magisterial documents of Francis.
# ---------------------------------------------------------------------------
FRANCISCO_DOCS: list[dict] = [
    {
        "title": "Lumen Fidei",
        "author": "Francisco",
        "year": 2013,
        "doc_type_pt": "Encíclica",
        "folder": "Enciclicas",
        "type_key": "enciclica",
        "page_url": "https://www.vatican.va/content/francesco/pt/encyclicals/documents/papa-francesco_20130629_enciclica-lumen-fidei.html",
    },
    {
        "title": "Laudato Si",
        "author": "Francisco",
        "year": 2015,
        "doc_type_pt": "Encíclica",
        "folder": "Enciclicas",
        "type_key": "enciclica",
        "page_url": "https://www.vatican.va/content/francesco/pt/encyclicals/documents/papa-francesco_20150524_enciclica-laudato-si.html",
    },
    {
        "title": "Laudate Deum",
        "author": "Francisco",
        "year": 2023,
        "doc_type_pt": "Exortação Apostólica",
        "folder": "Exortacoes Apostolicas",
        "type_key": "exortacao_apostolica",
        "page_url": "https://www.vatican.va/content/francesco/pt/apost_exhortations/documents/20231004-laudate-deum.html",
    },
    {
        "title": "Evangelii Gaudium",
        "author": "Francisco",
        "year": 2013,
        "doc_type_pt": "Exortação Apostólica",
        "folder": "Exortacoes Apostolicas",
        "type_key": "exortacao_apostolica",
        "page_url": "https://www.vatican.va/content/francesco/pt/apost_exhortations/documents/papa-francesco_esortazione-ap_20131124_evangelii-gaudium.html",
    },
    {
        "title": "Amoris Laetitia",
        "author": "Francisco",
        "year": 2016,
        "doc_type_pt": "Exortação Apostólica",
        "folder": "Exortacoes Apostolicas",
        "type_key": "exortacao_apostolica",
        "page_url": "https://www.vatican.va/content/francesco/pt/apost_exhortations/documents/papa-francesco_esortazione-ap_20160319_amoris-laetitia.html",
    },
    {
        "title": "Gaudete et Exsultate",
        "author": "Francisco",
        "year": 2018,
        "doc_type_pt": "Exortação Apostólica",
        "folder": "Exortacoes Apostolicas",
        "type_key": "exortacao_apostolica",
        "page_url": "https://www.vatican.va/content/francesco/pt/apost_exhortations/documents/papa-francesco_esortazione-ap_20180319_gaudete-et-exsultate.html",
    },
    {
        "title": "Christus Vivit",
        "author": "Francisco",
        "year": 2019,
        "doc_type_pt": "Exortação Apostólica",
        "folder": "Exortacoes Apostolicas",
        "type_key": "exortacao_apostolica",
        "page_url": "https://www.vatican.va/content/francesco/pt/apost_exhortations/documents/papa-francesco_esortazione-ap_20190325_christus-vivit.html",
    },
    {
        "title": "Querida Amazonia",
        "author": "Francisco",
        "year": 2020,
        "doc_type_pt": "Exortação Apostólica",
        "folder": "Exortacoes Apostolicas",
        "type_key": "exortacao_apostolica",
        "page_url": "https://www.vatican.va/content/francesco/pt/apost_exhortations/documents/papa-francesco_esortazione-ap_20200202_querida-amazonia.html",
    },
    {
        "title": "Fratelli Tutti",
        "author": "Francisco",
        "year": 2020,
        "doc_type_pt": "Encíclica",
        "folder": "Enciclicas",
        "type_key": "enciclica",
        "page_url": "https://www.vatican.va/content/francesco/pt/encyclicals/documents/papa-francesco_20201003_enciclica-fratelli-tutti.html",
    },
    {
        "title": "Praedicate Evangelium",
        "author": "Francisco",
        "year": 2022,
        "doc_type_pt": "Constituição Apostólica",
        "folder": "Constituicoes Apostolicas",
        "type_key": "constituicao_apostolica",
        "page_url": "https://www.vatican.va/content/francesco/pt/apost_constitutions/documents/20220319-costituzione-ap-praedicate-evangelium.html",
    },
    {
        "title": "Veritatis Gaudium",
        "author": "Francisco",
        "year": 2018,
        "doc_type_pt": "Constituição Apostólica",
        "folder": "Constituicoes Apostolicas",
        "type_key": "constituicao_apostolica",
        "page_url": "https://www.vatican.va/content/francesco/pt/apost_constitutions/documents/papa-francesco_costituzione-ap_20171208_veritatis-gaudium.html",
    },
    {
        "title": "Episcopalis Communio",
        "author": "Francisco",
        "year": 2018,
        "doc_type_pt": "Constituição Apostólica",
        "folder": "Constituicoes Apostolicas",
        "type_key": "constituicao_apostolica",
        "page_url": "https://www.vatican.va/content/francesco/pt/apost_constitutions/documents/papa-francesco_costituzione-ap_20180915_episcopalis-communio.html",
    },
]

SLEEP_BETWEEN_REQUESTS = 1.0  # seconds

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent.parent  # vera_fidei_starter/backend
_OUTPUT_ROOT = _BACKEND_DIR / "pdfs" / "documentos_pontificios"
_MANIFEST_PATH = _OUTPUT_ROOT / "manifest.jsonl"
_ERRORS_PATH = _OUTPUT_ROOT / "errors.jsonl"


def _to_ascii_filename(text: str) -> str:
    """Convert accented characters to ASCII equivalents for filesystem safety."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _sanitize_folder(name: str) -> str:
    """Remove filesystem-unsafe characters and limit length."""
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = name.strip(" .")
    return name[:120]


def _pope_folder_name(raw_pope: str) -> str:
    """Return the clean folder name for a pope, falling back to ASCII-safe generation."""
    raw = raw_pope.strip()
    if raw in POPE_FOLDER_MAP:
        return POPE_FOLDER_MAP[raw]
    # Best-effort fallback
    ascii_name = _to_ascii_filename(raw)
    ascii_name = re.sub(r"\s+", " ", ascii_name).strip()
    return f"Papa {ascii_name}" if not ascii_name.lower().startswith("papa") else ascii_name


def _doc_output_dir(pope_folder: str, type_folder: str, title: str, year: Optional[int]) -> Path:
    """Return the directory where files for this document go."""
    year_prefix = f"{year} - " if year else ""
    folder_title = _sanitize_folder(f"{year_prefix}{title}")
    return _OUTPUT_ROOT / _sanitize_folder(pope_folder) / _sanitize_folder(type_folder) / folder_title


def _safe_filename(title: str, lang: str, ext: str) -> str:
    """Build a filesystem-safe filename like 'Lumen Fidei - PT.pdf'."""
    safe_title = _sanitize_folder(title)
    return f"{safe_title} - {lang.upper()}{ext}"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_CLIENT: Optional[httpx.Client] = None


def _get_client() -> httpx.Client:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = httpx.Client(
            headers=HEADERS,
            follow_redirects=True,
            timeout=60,
        )
    return _CLIENT


def _fetch_html(url: str, retries: int = 3) -> Optional[str]:
    client = _get_client()
    for attempt in range(1, retries + 1):
        try:
            r = client.get(url)
            r.raise_for_status()
            return r.text
        except Exception as exc:
            if attempt == retries:
                return None
            wait = 2 ** attempt
            print(f"    [retry {attempt}/{retries}] {exc} — aguardando {wait}s")
            time.sleep(wait)
    return None


def _fetch_bytes(url: str, retries: int = 3) -> Optional[bytes]:
    client = _get_client()
    for attempt in range(1, retries + 1):
        try:
            r = client.get(url)
            r.raise_for_status()
            return r.content
        except Exception as exc:
            if attempt == retries:
                return None
            wait = 2 ** attempt
            print(f"    [retry {attempt}/{retries}] {exc} — aguardando {wait}s")
            time.sleep(wait)
    return None


# ---------------------------------------------------------------------------
# PDF validation
# ---------------------------------------------------------------------------

def _pdf_text_length(pdf_bytes: bytes) -> int:
    """Return total character count of extractable text in a PDF. Returns 0 on error."""
    if not _FITZ_OK:
        # Can't validate — assume it might be ok if large enough (>150 KB)
        return len(pdf_bytes) // 10
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total = sum(len(page.get_text()) for page in doc)
        doc.close()
        return total
    except Exception:
        return 0


def _is_real_pdf(pdf_bytes: bytes) -> bool:
    """Returns True if the PDF contains enough real text content."""
    return _pdf_text_length(pdf_bytes) >= MIN_PDF_TEXT_CHARS


# ---------------------------------------------------------------------------
# HTML text extraction
# ---------------------------------------------------------------------------

_REMOVE_SELECTORS = [
    "header", "footer", "nav", "aside", ".breadcrumb", ".toolbar",
    ".social", ".share", "#breadcrumb", "#toolbar", "script", "style",
    "noscript", ".language-selector", "#language-selector",
    ".sidebar", "#sidebar", ".related", ".news-list",
    # Vatican-specific chrome
    ".box-link", ".link-arrow", ".arrow-link", ".document-list",
    "#header", "#footer", ".topbar", ".back-to-top",
]


def _extract_text_from_html(html: str) -> str:
    """Extract clean document text from a Vatican HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    for sel in _REMOVE_SELECTORS:
        for tag in soup.select(sel):
            tag.decompose()

    # Vatican document pages use several possible content wrappers
    main = (
        soup.find("div", id=re.compile(r"^testo", re.I))
        or soup.find("div", class_=re.compile(r"\btesto\b", re.I))
        or soup.find("div", class_=re.compile(r"\bcontent[-_]?text\b", re.I))
        or soup.find("div", class_=re.compile(r"\bdocument\b", re.I))
        or soup.find("article")
        or soup.find("main")
        or soup.body
    )

    if main is None:
        return soup.get_text(separator="\n")

    paragraphs: list[str] = []
    for tag in main.find_all(["p", "h1", "h2", "h3", "h4", "h5", "blockquote", "li"]):
        text = tag.get_text(separator=" ", strip=True)
        if len(text) >= 30:
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
# Language link discovery
# ---------------------------------------------------------------------------

def _discover_language_urls(page_html: str, base_page_url: str) -> dict[str, str]:
    """
    Parse the Vatican document page to find language variant URLs.

    Vatican pages show a language bar/selector with links like:
      <a href="/content/.../documents/papa-xxx_20130629_xxx.html">Português</a>
    or use a pattern where only the language segment changes in the URL.

    Returns a dict: {lang_code: url}
    """
    soup = BeautifulSoup(page_html, "html.parser")

    # Map of text labels → lang code (Vatican.va uses full language names)
    label_to_code = {
        "português": "pt", "portuguese": "pt",
        "english": "en", "inglese": "en", "inglés": "en",
        "español": "es", "spagnolo": "es", "espanhol": "es",
        "français": "fr", "french": "fr", "francês": "fr",
        "deutsch": "de", "german": "de", "alemão": "de",
        "italiano": "it", "italian": "it", "italiano": "it",
        "latin": "la", "latim": "la", "latino": "la",
        "polski": "pl", "polish": "pl",
        "العربية": "ar", "arabic": "ar",
    }

    found: dict[str, str] = {}

    # Strategy 1: look for explicit language links in known Vatican containers
    for container_sel in [
        ".box-language", "#box-language", ".language-bar", ".lang-list",
        ".doc-languages", "#languages", ".languages",
        "ul.languages", "div.languages",
    ]:
        container = soup.select_one(container_sel)
        if container:
            for a in container.find_all("a", href=True):
                label = a.get_text(strip=True).lower()
                href = a["href"]
                for key, code in label_to_code.items():
                    if key in label and code not in found:
                        full_url = urljoin(BASE_URL, href)
                        found[code] = full_url
                        break

    # Strategy 2: scan all links on the page for Vatican document URLs
    # Vatican uses /{lang}/ in the path, so we can detect language from URL
    if not found:
        parsed_base = urlparse(base_page_url)
        base_path = parsed_base.path

        # Find the language segment in the base URL
        # e.g. /content/francesco/pt/encyclicals/.../xxx.html → lang="pt"
        lang_in_url = _detect_lang_in_url(base_path)
        if lang_in_url:
            # Add the base URL itself
            found[lang_in_url] = base_page_url

            # Try to synthesise URLs for other languages by replacing the segment
            for lang in LANGUAGES:
                if lang == lang_in_url:
                    continue
                for code_variant in LANG_URL_CODES.get(lang, [lang]):
                    candidate_path = _replace_lang_in_path(base_path, lang_in_url, code_variant)
                    if candidate_path and candidate_path != base_path:
                        found[lang] = urljoin(BASE_URL, candidate_path)
                        break  # only record first variant per language

    # Strategy 3: brute-force path replacement if we have at least the base lang
    if not found:
        # Just record the base page
        base_lang = _detect_lang_in_url(urlparse(base_page_url).path) or "pt"
        found[base_lang] = base_page_url

    return found


def _detect_lang_in_url(path: str) -> Optional[str]:
    """
    Detect language code in a Vatican URL path.

    Handles two Vatican URL structures:
      Modern: /content/francesco/pt/encyclicals/.../xxx.html   (lang in path segment)
      Old:    /holy_father/pius_xii/.../hf_p-xii_enc_..._po.html  (lang in filename suffix)
    """
    # Modern: /content/{pope-slug}/{lang}/...
    m = re.search(r"/content/[^/]+/([a-z]{2,3})/", path)
    if m:
        code = m.group(1)
        if code == "po":
            return "pt"
        resolved = code if code in LANGUAGES else _url_code_to_lang(code)
        if resolved:
            return resolved

    # Old-style: filename ends with _{lang_code}.html  e.g. ..._po.html, ..._en.html
    m2 = re.search(r"_([a-z]{2,3})\.html?$", path, re.IGNORECASE)
    if m2:
        code = m2.group(1).lower()
        if code == "po":
            return "pt"
        resolved = code if code in LANGUAGES else _url_code_to_lang(code)
        if resolved:
            return resolved

    return None


def _url_code_to_lang(code: str) -> Optional[str]:
    for lang, variants in LANG_URL_CODES.items():
        if code in variants:
            return lang
    return None


def _replace_lang_in_path(path: str, old_lang: str, new_lang: str) -> Optional[str]:
    """
    Replace the language segment in a Vatican path.

    Modern: /content/francesco/pt/... → /content/francesco/es/...
    Old:    /holy_father/.../xxx_po.html → /holy_father/.../xxx_en.html
    """
    old_variants = LANG_URL_CODES.get(old_lang, [old_lang])
    new_variants = LANG_URL_CODES.get(new_lang, [new_lang])
    new_code = new_variants[0]  # primary code for new lang

    # Modern path: lang in directory segment
    for old_code in old_variants:
        pattern = rf"(/content/[^/]+/){re.escape(old_code)}(/)"
        new_path = re.sub(pattern, rf"\g<1>{new_code}\2", path)
        if new_path != path:
            return new_path

    # Old-style path: lang suffix in filename _XX.html
    for old_code in old_variants:
        pattern = rf"_{re.escape(old_code)}(\.html?)$"
        new_path = re.sub(pattern, f"_{new_code}\\1", path, flags=re.IGNORECASE)
        if new_path != path:
            return new_path

    return None


# ---------------------------------------------------------------------------
# PDF link discovery on a document page
# ---------------------------------------------------------------------------

def _find_pdf_links_on_page(html: str, page_url: str) -> list[str]:
    """
    Find real PDF download links on a Vatican document HTML page.

    Real PDFs are usually at:
      https://www.vatican.va/content/dam/...
    or linked explicitly with <a href="...\.pdf">

    Returns a list of absolute PDF URLs (best candidates first).
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.lower().endswith(".pdf"):
            continue
        full = urljoin(page_url, href)
        # Prefer content/dam URLs (these are the "real" documents)
        if "content/dam" in full:
            candidates.insert(0, full)
        else:
            candidates.append(full)

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for url in candidates:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


# ---------------------------------------------------------------------------
# fpdf2 PDF generation from plain text
# ---------------------------------------------------------------------------

def _text_to_pdf_bytes(title: str, author: str, lang: str, text: str) -> Optional[bytes]:
    """Generate a PDF from plain text using fpdf2. Returns None if fpdf2 is unavailable."""
    if not _FPDF_OK:
        return None

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title block
    pdf.set_font("Helvetica", style="B", size=14)
    # fpdf2 requires latin-1 safe strings for the built-in fonts;
    # replace chars outside latin-1 with closest ASCII equivalent
    def _safe(s: str) -> str:
        return s.encode("latin-1", errors="replace").decode("latin-1")

    pdf.multi_cell(0, 8, _safe(title))
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, _safe(f"{author} — {lang.upper()}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6)

    # Body text
    pdf.set_font("Helvetica", size=11)
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        try:
            pdf.multi_cell(0, 6, _safe(paragraph))
        except Exception:
            # Skip unrenderable paragraphs
            pass
        pdf.ln(3)

    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Manifest / error logging
# ---------------------------------------------------------------------------

def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_existing_paths(manifest_path: Path) -> set[str]:
    """Return set of 'path' values from an existing manifest (for resume support)."""
    existing: set[str] = set()
    if not manifest_path.exists():
        return existing
    with manifest_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if "path" in rec:
                    existing.add(rec["path"])
            except json.JSONDecodeError:
                pass
    return existing


# ---------------------------------------------------------------------------
# Master list parsing
# ---------------------------------------------------------------------------

def _fetch_document_list(dry_run: bool = False) -> list[dict]:
    """
    Fetch and parse the Vatican papal documents list page.

    The page at papal_docs_list_po.html contains a large table (Table index 1)
    with 425+ rows, and a series of per-letter sub-tables (Table index 2+).
    Each sub-table has columns: Título | Autor | Ano | Documento
    The title cell (col 0) carries the link to the document page.

    Returns a list of dicts with keys:
        title, author, year, doc_type_pt, folder, type_key, page_url
    """
    print(f"[1/4] Buscando lista mestre: {LIST_URL}")
    html = _fetch_html(LIST_URL)
    if not html:
        print("[ERRO] Não foi possível baixar a lista de documentos.")
        sys.exit(1)

    soup = BeautifulSoup(html, "html.parser")
    documents: list[dict] = []
    seen_urls: set[str] = set()

    all_tables = soup.find_all("table")
    print(f"    {len(all_tables)} tabelas encontradas na página.")

    for table in all_tables:
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        # Identify the header row: look for a row whose cells contain
        # "Título" / "Autor" / "Ano" keywords
        header_row_idx = -1
        col_title = col_author = col_year = col_type = -1

        for row_idx, row in enumerate(rows[:5]):  # header is always in first few rows
            cells = row.find_all(["th", "td"])
            if len(cells) < 3:
                continue
            texts = [c.get_text(strip=True).lower() for c in cells]
            # Check for known column header keywords
            found_title = found_author = found_year = found_type = False
            for i, t in enumerate(texts):
                if any(k in t for k in ["título", "titolo", "title"]):
                    col_title = i; found_title = True
                elif any(k in t for k in ["autor", "author"]):
                    col_author = i; found_author = True
                elif any(k in t for k in ["ano", "year", "anno", "data"]):
                    col_year = i; found_year = True
                elif any(k in t for k in ["tipo", "type", "documento", "documento"]):
                    col_type = i; found_type = True
            if found_title and found_author:
                header_row_idx = row_idx
                break

        if header_row_idx == -1 or col_title == -1:
            # Try fixed column order: col 0=Title, 1=Author, 2=Year, 3=Type
            # (This is the actual structure of the Vatican page sub-tables)
            header_row_idx = 0
            col_title, col_author, col_year, col_type = 0, 1, 2, 3

        for row in rows[header_row_idx + 1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue

            def _cell_text(idx: int) -> str:
                if idx < 0 or idx >= len(cells):
                    return ""
                return re.sub(r"\s+", " ", cells[idx].get_text(separator=" ", strip=True)).strip()

            title = _cell_text(col_title)
            author = _cell_text(col_author)
            year_raw = _cell_text(col_year)
            doc_type_pt = _cell_text(col_type)

            # Skip header-repeat rows
            if title.lower() in ("título", "titolo", "title", ""):
                continue
            # Skip rows where type is a non-document category description
            if not title or len(title) < 3:
                continue

            # Parse year
            year: Optional[int] = None
            m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", year_raw)
            if m:
                year = int(m.group(1))

            # Match document type
            type_cfg = _match_doc_type(doc_type_pt)
            if type_cfg is None:
                continue

            # Extract the link from the title cell
            title_cell = cells[col_title] if col_title < len(cells) else cells[0]
            a_tag = title_cell.find("a", href=True)
            if not a_tag:
                # Try other cells
                for cell in cells:
                    a_tag = cell.find("a", href=True)
                    if a_tag:
                        break
            if not a_tag:
                continue

            href = a_tag["href"].strip()
            # Vatican list page sometimes has bare hrefs without scheme
            link_url = urljoin(BASE_URL, href)

            # De-duplicate
            if link_url in seen_urls:
                continue
            seen_urls.add(link_url)

            documents.append({
                "title": title,
                "author": author,
                "year": year,
                "doc_type_pt": doc_type_pt,
                "folder": type_cfg["folder"],
                "type_key": type_cfg["type_key"],
                "page_url": link_url,
            })

    # Fallback: scan all links if no table-based results
    if not documents:
        print("    [AVISO] Nenhuma tabela válida encontrada — tentando fallback por links.")
        documents = _parse_link_fallback(soup)

    print(f"    {len(documents)} documentos encontrados na lista.")
    return documents


def _match_doc_type(raw_type: str) -> Optional[dict]:
    """Match a raw type string from the page to our DOC_TYPE_MAP."""
    raw_normalized = raw_type.strip().lower()
    if not raw_normalized:
        return None
    # Exact match first
    for pt_label, cfg in DOC_TYPE_MAP.items():
        if pt_label.lower() == raw_normalized:
            return cfg
    # Substring match (the page may have extra qualifiers or accent variants)
    for pt_label, cfg in DOC_TYPE_MAP.items():
        if pt_label.lower() in raw_normalized or raw_normalized in pt_label.lower():
            return cfg
    return None


def _parse_link_fallback(soup: BeautifulSoup) -> list[dict]:
    """
    Fallback parser: scan all hyperlinks on the page and infer type from context.
    Used when the table structure cannot be parsed.
    """
    documents: list[dict] = []
    seen_urls: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"\.html?$", href, re.I):
            continue
        full_url = urljoin(BASE_URL, href)
        if "vatican.va" not in full_url:
            continue
        if full_url in seen_urls:
            continue

        title = a.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        # Look at the table row or parent for type/year context
        parent_row = a.find_parent("tr")
        context_text = ""
        if parent_row:
            context_text = parent_row.get_text(separator=" ", strip=True)
        elif a.parent:
            context_text = a.parent.get_text(separator=" ", strip=True)

        year: Optional[int] = None
        m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", context_text)
        if m:
            year = int(m.group(1))

        doc_type_pt = ""
        for pt_label in DOC_TYPE_MAP:
            if pt_label.lower() in context_text.lower():
                doc_type_pt = pt_label
                break

        type_cfg = _match_doc_type(doc_type_pt)
        if type_cfg is None:
            continue

        seen_urls.add(full_url)
        documents.append({
            "title": title,
            "author": "",
            "year": year,
            "doc_type_pt": doc_type_pt,
            "folder": type_cfg["folder"],
            "type_key": type_cfg["type_key"],
            "page_url": full_url,
        })

    return documents


# ---------------------------------------------------------------------------
# Per-document processing
# ---------------------------------------------------------------------------

def _process_document(
    doc: dict,
    dry_run: bool,
    resume: bool,
    existing_paths: set[str],
    manifest_path: Path,
    errors_path: Path,
) -> int:
    """
    Download all language variants of a single document.
    Returns number of files actually saved.
    """
    title = doc["title"]
    author = doc["author"]
    year = doc["year"]
    type_folder = doc["folder"]
    type_key = doc["type_key"]
    page_url = doc["page_url"]

    pope_folder = _pope_folder_name(author) if author else "Papa Desconhecido"
    out_dir = _doc_output_dir(pope_folder, type_folder, title, year)

    print(f"\n  [{type_key}] {title} ({year}) — {author}")
    print(f"    URL: {page_url}")

    if dry_run:
        print(f"    [dry-run] Pasta: {out_dir}")
        print(f"    [dry-run] Idiomas a tentar: {', '.join(LANGUAGES)}")
        return 0

    # Fetch the base document page (Portuguese or whatever is the canonical URL)
    base_html = _fetch_html(page_url)
    time.sleep(SLEEP_BETWEEN_REQUESTS)

    if not base_html:
        _append_jsonl(errors_path, {
            "title": title, "page_url": page_url,
            "error": "Não foi possível baixar a página base",
        })
        return 0

    # Discover language URLs
    lang_urls = _discover_language_urls(base_html, page_url)
    print(f"    Idiomas descobertos: {list(lang_urls.keys())}")

    files_saved = 0

    for lang in LANGUAGES:
        lang_url = lang_urls.get(lang)
        if not lang_url:
            continue

        # Build target file path
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / _safe_filename(title, lang, ".pdf")
        txt_path = out_dir / _safe_filename(title, lang, ".txt")

        str_pdf_path = str(pdf_path)
        str_txt_path = str(txt_path)

        if resume and (str_pdf_path in existing_paths or str_txt_path in existing_paths):
            print(f"      [{lang.upper()}] Já existe — pulando.")
            continue

        # Also check file system directly for resumability
        if resume and (pdf_path.exists() or txt_path.exists()):
            existing_file = str_pdf_path if pdf_path.exists() else str_txt_path
            print(f"      [{lang.upper()}] Arquivo existe no disco — pulando.")
            continue

        print(f"      [{lang.upper()}] Processando: {lang_url}")

        # Fetch the language-specific page (may be same as base for pt)
        if lang_url == page_url:
            lang_html = base_html
        else:
            lang_html = _fetch_html(lang_url)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            if not lang_html:
                print(f"      [{lang.upper()}] AVISO: página não acessível — pulando.")
                continue

        # Try to find a real PDF link on this page
        pdf_links = _find_pdf_links_on_page(lang_html, lang_url)
        print(f"      [{lang.upper()}] Links PDF encontrados: {len(pdf_links)}")

        saved_path: Optional[str] = None
        saved_status: str = ""
        used_pdf_url: Optional[str] = None

        for pdf_url in pdf_links:
            print(f"        Tentando PDF: {pdf_url}")
            pdf_bytes = _fetch_bytes(pdf_url)
            time.sleep(SLEEP_BETWEEN_REQUESTS)

            if not pdf_bytes:
                print(f"        Download falhou.")
                continue

            if _is_real_pdf(pdf_bytes):
                # Save the real PDF
                pdf_path.write_bytes(pdf_bytes)
                print(f"        PDF real salvo: {pdf_path.name} ({len(pdf_bytes)//1024} KB)")
                saved_path = str_pdf_path
                saved_status = "pdf_real"
                used_pdf_url = pdf_url
                break
            else:
                char_count = _pdf_text_length(pdf_bytes)
                print(f"        PDF inválido/em branco ({char_count} chars) — tentando próximo.")

        # If no real PDF found, fall back to HTML text extraction
        if saved_path is None:
            print(f"      [{lang.upper()}] Sem PDF real — extraindo texto do HTML.")
            raw_text = _clean_text(_extract_text_from_html(lang_html))

            if len(raw_text) < MIN_HTML_TEXT_CHARS:
                print(f"      [{lang.upper()}] Texto HTML muito curto ({len(raw_text)} chars) — pulando.")
                _append_jsonl(errors_path, {
                    "title": title, "lang": lang, "page_url": lang_url,
                    "error": f"Texto HTML muito curto: {len(raw_text)} chars",
                })
                continue

            print(f"      [{lang.upper()}] Texto extraído: {len(raw_text)} chars")

            # Try to generate a PDF from the text
            pdf_bytes_generated = _text_to_pdf_bytes(title, author, lang, raw_text)

            if pdf_bytes_generated:
                pdf_path.write_bytes(pdf_bytes_generated)
                print(f"        PDF gerado salvo: {pdf_path.name}")
                saved_path = str_pdf_path
                saved_status = "pdf_generated"
            else:
                # Last resort: save as .txt
                txt_path.write_text(raw_text, encoding="utf-8")
                print(f"        TXT salvo: {txt_path.name}")
                saved_path = str_txt_path
                saved_status = "html_only"

        if saved_path:
            _append_jsonl(manifest_path, {
                "title": title,
                "author": author,
                "year": year,
                "type": doc["doc_type_pt"],
                "type_key": type_key,
                "language": lang,
                "page_url": lang_url,
                "pdf_url": used_pdf_url,
                "path": saved_path,
                "status": saved_status,
            })
            existing_paths.add(saved_path)
            files_saved += 1

    return files_saved


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vera.Fidei — Scraper de documentos papais do Vatican.va"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar o que seria baixado sem salvar nada",
    )
    parser.add_argument(
        "--pope",
        default="",
        help="Filtrar por papa (substring, ex: 'Francisco', 'João Paulo II')",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Pular arquivos que já existem no disco (usa manifest.jsonl + verificação direta)",
    )
    parser.add_argument(
        "--type",
        default="",
        dest="doc_type",
        help="Filtrar por tipo de documento (substring, ex: 'Encíclica', 'Motu Proprio')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limitar número de documentos processados (0 = sem limite)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  Vera.Fidei — Vatican.va Document Scraper")
    print("=" * 70)
    print(f"  Saída: {_OUTPUT_ROOT}")
    print(f"  Dry-run: {args.dry_run}")
    print(f"  Resume: {args.resume}")
    if args.pope:
        print(f"  Filtro papa: {args.pope}")
    if args.doc_type:
        print(f"  Filtro tipo: {args.doc_type}")
    print()

    # Ensure output dirs exist
    if not args.dry_run:
        _OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    # Load existing paths for resume support
    existing_paths: set[str] = set()
    if args.resume and not args.dry_run:
        existing_paths = _load_existing_paths(_MANIFEST_PATH)
        print(f"[Resume] {len(existing_paths)} arquivos já no manifesto.")

    # Step 1: Fetch document list from the master Vatican page
    documents = _fetch_document_list(dry_run=args.dry_run)

    if not documents:
        print("\n[ERRO] Nenhum documento encontrado. Verifique a URL da lista.")
        print(f"  URL: {LIST_URL}")
        print("  Possível causa: a estrutura da página mudou. Inspecione o HTML.")
        sys.exit(1)

    # Merge supplemental Francisco documents (not on the Portuguese list page)
    existing_urls = {d["page_url"] for d in documents}
    francisco_added = 0
    for fdoc in FRANCISCO_DOCS:
        if fdoc["page_url"] not in existing_urls:
            documents.append(fdoc)
            existing_urls.add(fdoc["page_url"])
            francisco_added += 1
    if francisco_added:
        print(f"    + {francisco_added} documentos de Francisco adicionados (lista suplementar).")

    # Step 2: Apply filters
    if args.pope:
        filter_pope = args.pope.strip().lower()
        documents = [
            d for d in documents
            if filter_pope in d.get("author", "").lower()
            or filter_pope in _pope_folder_name(d.get("author", "")).lower()
        ]
        print(f"[Filtro papa] {len(documents)} documentos após filtro '{args.pope}'.")

    if args.doc_type:
        filter_type = args.doc_type.strip().lower()
        documents = [
            d for d in documents
            if filter_type in d.get("doc_type_pt", "").lower()
            or filter_type in d.get("type_key", "").lower()
        ]
        print(f"[Filtro tipo] {len(documents)} documentos após filtro '{args.doc_type}'.")

    if args.limit and args.limit > 0:
        documents = documents[: args.limit]
        print(f"[Limite] Processando apenas {len(documents)} documentos.")

    print(f"\n[2/4] Total a processar: {len(documents)} documentos")
    print("[3/4] Iniciando downloads...\n")

    total_files = 0
    total_docs = 0

    for i, doc in enumerate(documents, 1):
        print(f"[{i}/{len(documents)}]", end=" ")
        try:
            n = _process_document(
                doc=doc,
                dry_run=args.dry_run,
                resume=args.resume,
                existing_paths=existing_paths,
                manifest_path=_MANIFEST_PATH,
                errors_path=_ERRORS_PATH,
            )
            total_files += n
            total_docs += 1
        except KeyboardInterrupt:
            print("\n\n[INTERROMPIDO] Progresso salvo no manifesto.")
            break
        except Exception as exc:
            print(f"  [ERRO INESPERADO] {exc}")
            if not args.dry_run:
                _append_jsonl(_ERRORS_PATH, {
                    "title": doc.get("title", "?"),
                    "page_url": doc.get("page_url", "?"),
                    "error": str(exc),
                })

    print(f"\n[4/4] Concluído.")
    print(f"  Documentos processados : {total_docs}")
    print(f"  Arquivos salvos        : {total_files}")
    if not args.dry_run:
        print(f"  Manifesto             : {_MANIFEST_PATH}")
        print(f"  Erros                 : {_ERRORS_PATH}")
        print(f"  Pasta raiz            : {_OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
