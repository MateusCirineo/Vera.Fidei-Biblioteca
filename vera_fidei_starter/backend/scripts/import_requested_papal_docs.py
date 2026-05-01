from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

spec = importlib.util.spec_from_file_location(
    "vatican_scraper",
    BACKEND_DIR / "scripts" / "scrape_vatican_pdfs.py",
)
if spec is None or spec.loader is None:
    raise RuntimeError("Nao foi possivel carregar scrape_vatican_pdfs.py")
scraper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scraper)

from ingestion.chunker import Chunker
from ingestion.pdf_extractor import PDFExtractor
from models.database import Book, BookFile, Chunk, SessionLocal, init_db
from search.semantic_search import SemanticSearchClient, _get_model
from search.text_search import ES_INDEX, TextSearchClient
from utils.language import normalize_lang


OUTPUT_ROOT = BACKEND_DIR / "pdfs" / "documentos_pontificios"
MANIFEST_PATH = OUTPUT_ROOT / "manifest_requested_20260419.jsonl"
HTML_TMP_DIR = BACKEND_DIR / ".tmp_vf_pdf"
SOURCE_LABEL = "Vatican.va"
COLLECTION = "MAG"
LIBRARY_SECTION = "documentos"

LANGUAGES = ["pt", "en", "es", "fr", "de", "it", "la", "pl", "ar"]
LANG_LABEL = {
    "pt": "Portugues",
    "en": "English",
    "es": "Espanol",
    "fr": "Francais",
    "de": "Deutsch",
    "it": "Italiano",
    "la": "Latim",
    "pl": "Polski",
    "ar": "Arabic",
}


@dataclass(frozen=True)
class RequestedDoc:
    title: str
    author_short: str
    author_full: str
    pope_folder: str
    year: int
    folder: str
    type_key: str
    base_url: str | None = None
    local_latin_pdf: Path | None = None


REQUESTED_DOCS: list[RequestedDoc] = [
    RequestedDoc(
        title="Pastoralis",
        author_short="Leão XIII",
        author_full="Papa Leão XIII",
        pope_folder="Papa Leao XIII",
        year=1891,
        folder="Enciclicas",
        type_key="enciclica",
        base_url="https://www.vatican.va/content/leo-xiii/la/encyclicals/documents/hf_l-xiii_enc_18910625_pastoralis.html",
        local_latin_pdf=Path(r"C:\Users\Kryptonian-PC\Downloads\Patrologia\Obras que faltam\Pastoralis (1891) Latim.pdf"),
    ),
    RequestedDoc(
        title="Miserentissimus Redemptor",
        author_short="Pio XI",
        author_full="Papa Pio XI",
        pope_folder="Papa Pio XI",
        year=1928,
        folder="Enciclicas",
        type_key="enciclica",
        base_url="https://www.vatican.va/content/pius-xi/la/encyclicals/documents/hf_p-xi_enc_19280508_miserentissimus-redemptor.html",
        local_latin_pdf=Path(r"C:\Users\Kryptonian-PC\Downloads\Patrologia\Obras que faltam\Miserentissimus Redemptor (1928) Latim.pdf"),
    ),
    RequestedDoc(
        title="Mens Nostra",
        author_short="Pio XI",
        author_full="Papa Pio XI",
        pope_folder="Papa Pio XI",
        year=1929,
        folder="Enciclicas",
        type_key="enciclica",
        base_url="https://www.vatican.va/content/pius-xi/la/encyclicals/documents/hf_p-xi_enc_19291220_mens-nostra.html",
        local_latin_pdf=Path(r"C:\Users\Kryptonian-PC\Downloads\Patrologia\Obras que faltam\Mens Nostra (1929) Latim.pdf"),
    ),
    RequestedDoc(
        title="Casti Connubii",
        author_short="Pio XI",
        author_full="Papa Pio XI",
        pope_folder="Papa Pio XI",
        year=1930,
        folder="Enciclicas",
        type_key="enciclica",
        base_url="https://www.vatican.va/content/pius-xi/pt/encyclicals/documents/hf_p-xi_enc_19301231_casti-connubii.html",
        local_latin_pdf=Path(r"C:\Users\Kryptonian-PC\Downloads\Patrologia\Obras que faltam\Casti Connubii (1930) Latim.pdf"),
    ),
    RequestedDoc(
        title="Euntes in Mundum Universum",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1988,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/la/apost_letters/1988/documents/hf_jp-ii_apl_19880125_euntes-in-mundum-universum.html",
    ),
    RequestedDoc(
        title="Mulieris Dignitatem",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1988,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/en/apost_letters/1988/documents/hf_jp-ii_apl_19880815_mulieris-dignitatem.html",
    ),
    RequestedDoc(
        title="Vicesimus Quintus Annus",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1988,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/en/apost_letters/1988/documents/hf_jp-ii_apl_19881204_vicesimus-quintus-annus.html",
    ),
    RequestedDoc(
        title="Ordinatio Sacerdotalis",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1994,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/en/apost_letters/1994/documents/hf_jp-ii_apl_19940522_ordinatio-sacerdotalis.html",
    ),
    RequestedDoc(
        title="Tertio Millennio Adveniente",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1994,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/en/apost_letters/1994/documents/hf_jp-ii_apl_19941110_tertio-millennio-adveniente.html",
    ),
    RequestedDoc(
        title="Orientale Lumen",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1995,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/en/apost_letters/1995/documents/hf_jp-ii_apl_19950502_orientale-lumen.html",
    ),
    RequestedDoc(
        title="União de Brest",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1995,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/en/apost_letters/1995/documents/hf_jp-ii_apl_19951112_iv-cent-union-brest.html",
    ),
    RequestedDoc(
        title="Operosam Diem",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1996,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/la/apost_letters/1996/documents/hf_jp-ii_apl_01121996_operosam-diem.html",
    ),
    RequestedDoc(
        title="Divini Amoris Scientia",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1997,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/la/apost_letters/1997/documents/hf_jp-ii_apl_19101997_divini-amoris.html",
    ),
    RequestedDoc(
        title="Laetamur Magnopere",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1997,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/la/apost_letters/1997/documents/hf_jp-ii_apl_15081997_laetamur.html",
    ),
    RequestedDoc(
        title="Dies Domini",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1998,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/en/apost_letters/1998/documents/hf_jp-ii_apl_05071998_dies-domini.html",
    ),
    RequestedDoc(
        title="Inter Munera Academiarum",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=1999,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/la/apost_letters/1999/documents/hf_jp-ii_apl_19990128_inter-munera-academiarum.html",
    ),
    RequestedDoc(
        title="Novo Millennio Ineunte",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=2001,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/en/apost_letters/2001/documents/hf_jp-ii_apl_20010106_novo-millennio-ineunte.html",
    ),
    RequestedDoc(
        title="Spiritus et Sponsa",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=2003,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/la/apost_letters/2003/documents/hf_jp-ii_apl_20031204_spiritus-et-sponsa.html",
    ),
    RequestedDoc(
        title="Mane Nobiscum Domine",
        author_short="João Paulo II",
        author_full="Papa João Paulo II",
        pope_folder="Papa Joao Paulo II",
        year=2004,
        folder="Cartas Apostolicas",
        type_key="carta_apostolica",
        base_url="https://www.vatican.va/content/john-paul-ii/en/apost_letters/2004/documents/hf_jp-ii_apl_20041008_mane-nobiscum-domine.html",
    ),
    RequestedDoc(
        title="Humanae Salutis",
        author_short="João XXIII",
        author_full="Papa João XXIII",
        pope_folder="Papa Joao XXIII",
        year=1961,
        folder="Constituicoes Apostolicas",
        type_key="constituicao_apostolica",
        base_url="https://www.vatican.va/content/john-xxiii/la/apost_constitutions/1961/documents/hf_j-xxiii_apc_19611225_humanae-salutis.html",
    ),
]


def output_dir_for(doc: RequestedDoc) -> Path:
    return OUTPUT_ROOT / doc.pope_folder / doc.folder / f"{doc.year} - {doc.title}"


def output_pdf_path(doc: RequestedDoc, lang: str) -> Path:
    return output_dir_for(doc) / f"{doc.title} - {lang.upper()}.pdf"


def append_manifest(row: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def find_edge() -> str | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("msedge") or shutil.which("chrome") or shutil.which("chromium")


def candidate_language_urls(base_url: str) -> dict[str, str]:
    parsed = urlparse(base_url)
    base_lang = scraper._detect_lang_in_url(parsed.path) or "pt"
    found: dict[str, str] = {base_lang: base_url}

    for lang in LANGUAGES:
        if lang == base_lang:
            continue
        for code in scraper.LANG_URL_CODES.get(lang, [lang]):
            candidate = scraper._replace_lang_in_path(parsed.path, base_lang, code)
            if candidate:
                found[lang] = urljoin("https://www.vatican.va", candidate)
                break
    return found


def fetch_html_once(url: str) -> str | None:
    try:
        response = scraper._get_client().get(url, timeout=25)
        if response.status_code != 200:
            return None
        if not response.text or len(response.text) < 500:
            return None
        return response.text
    except Exception:
        return None


def extract_clean_text(html_text: str) -> str:
    text = scraper._clean_text(scraper._extract_text_from_html(html_text))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def html_document(doc: RequestedDoc, lang: str, source_url: str, text: str) -> str:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    body = []
    for paragraph in paragraphs:
        escaped = html.escape(paragraph)
        if len(paragraph) <= 90 and paragraph.upper() == paragraph and re.search(r"[A-Z]", paragraph, re.I):
            body.append(f"<h2>{escaped}</h2>")
        else:
            body.append(f"<p>{escaped}</p>")
    return f"""<!doctype html>
<html lang="{html.escape(lang)}">
<head>
  <meta charset="utf-8">
  <title>{html.escape(doc.title)} - {html.escape(lang.upper())}</title>
  <style>
    @page {{ size: A4; margin: 22mm 20mm; }}
    body {{
      color: #1b1b1b;
      font-family: Georgia, "Times New Roman", "Noto Serif", serif;
      font-size: 11.3pt;
      line-height: 1.48;
      margin: 0;
    }}
    .cover {{
      break-after: page;
      min-height: 245mm;
      display: flex;
      flex-direction: column;
      justify-content: center;
      text-align: center;
      border-top: 1.4pt solid #b08d2c;
      border-bottom: 1.4pt solid #b08d2c;
      padding: 14mm 8mm;
    }}
    .source {{
      color: #8a6d1d;
      font-family: Arial, sans-serif;
      font-size: 10pt;
      margin-bottom: 12mm;
    }}
    .pope {{ font-size: 15pt; font-variant: small-caps; margin-bottom: 8mm; }}
    h1 {{ font-size: 24pt; line-height: 1.15; margin: 0 0 9mm; text-transform: uppercase; }}
    .lang {{ font-size: 11pt; font-style: italic; }}
    main {{ max-width: 166mm; margin: 0 auto; }}
    h2 {{
      break-after: avoid;
      font-size: 13.5pt;
      line-height: 1.28;
      margin: 8mm 0 4mm;
      text-align: center;
    }}
    p {{ margin: 0 0 3.3mm; text-align: justify; orphans: 3; widows: 3; }}
    .footer-source {{
      border-top: .6pt solid #d5c48d;
      color: #777;
      font-family: Arial, sans-serif;
      font-size: 8.5pt;
      margin-top: 12mm;
      padding-top: 3mm;
      text-align: center;
    }}
  </style>
</head>
<body>
  <section class="cover">
    <div class="source">Vatican.va</div>
    <div class="pope">{html.escape(doc.author_full)}</div>
    <h1>{html.escape(doc.title)}</h1>
    <div class="lang">{html.escape(LANG_LABEL.get(lang, lang.upper()))}</div>
  </section>
  <main>
    {''.join(body)}
    <div class="footer-source">Fonte: {html.escape(source_url)}</div>
  </main>
</body>
</html>
"""


def generate_pdf_with_edge(
    doc: RequestedDoc,
    lang: str,
    source_url: str,
    text: str,
    pdf_path: Path,
    edge_path: str,
) -> None:
    HTML_TMP_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(f"{doc.year}:{doc.title}:{lang}".encode("utf-8")).hexdigest()[:10]
    safe_stem = f"vf_{doc.year}_{lang}_{digest}"
    html_path = HTML_TMP_DIR / f"{safe_stem}.html"
    temp_pdf_path = HTML_TMP_DIR / f"{safe_stem}.pdf"
    profile_dir = HTML_TMP_DIR / f"p_{digest}"
    html_path.write_text(html_document(doc, lang, source_url, text), encoding="utf-8")
    if temp_pdf_path.exists():
        temp_pdf_path.unlink()
    command = [
        edge_path,
        "--headless",
        "--disable-gpu",
        "--disable-crash-reporter",
        "--disable-crashpad",
        "--no-pdf-header-footer",
        f"--user-data-dir={profile_dir}",
        f"--print-to-pdf={temp_pdf_path}",
        html_path.resolve().as_uri(),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode != 0 or not temp_pdf_path.exists() or temp_pdf_path.stat().st_size < 1000:
        raise RuntimeError(f"Edge falhou ao gerar PDF: {result.stderr[-500:]}")
    if pdf_path.exists():
        pdf_path.unlink()
    shutil.move(str(temp_pdf_path), str(pdf_path))


def save_generated_pdf(
    doc: RequestedDoc,
    lang: str,
    source_url: str,
    html_text: str,
    pdf_path: Path,
    edge_path: str | None,
) -> tuple[bool, str, int]:
    pdf_links = scraper._find_pdf_links_on_page(html_text, source_url)
    for pdf_url in pdf_links:
        raw = scraper._fetch_bytes(pdf_url, retries=1)
        if raw and scraper._is_real_pdf(raw):
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(raw)
            return True, "pdf_real", scraper._pdf_text_length(raw)

    clean_text = extract_clean_text(html_text)
    if len(clean_text) < scraper.MIN_HTML_TEXT_CHARS:
        return False, "html_text_short", len(clean_text)

    if edge_path:
        generate_pdf_with_edge(doc, lang, source_url, clean_text, pdf_path, edge_path)
        return True, "pdf_generated_edge", len(clean_text)

    generate_pdf_with_fpdf(doc, lang, source_url, clean_text, pdf_path)
    return True, "pdf_generated_fpdf", len(clean_text)


def fpdf_font_paths() -> tuple[str | None, str | None]:
    regular_candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\times.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
    ]
    bold_candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\timesbd.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
    ]
    regular = next((str(path) for path in regular_candidates if path.exists()), None)
    bold = next((str(path) for path in bold_candidates if path.exists()), regular)
    return regular, bold


def generate_pdf_with_fpdf(
    doc: RequestedDoc,
    lang: str,
    source_url: str,
    text: str,
    pdf_path: Path,
) -> None:
    from fpdf import FPDF

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    regular_font, bold_font = fpdf_font_paths()

    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    if regular_font:
        pdf.add_font("VF", "", regular_font)
        pdf.add_font("VF", "B", bold_font or regular_font)
        font_name = "VF"
    else:
        font_name = "Helvetica"

    pdf.add_page()
    pdf.set_font(font_name, "B", 18)
    pdf.multi_cell(0, 10, doc.title, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font(font_name, "", 12)
    pdf.multi_cell(0, 7, doc.author_full, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(
        0,
        7,
        f"Vatican.va - {LANG_LABEL.get(lang, lang.upper())}",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(8)
    pdf.set_draw_color(176, 141, 44)
    pdf.line(30, pdf.get_y(), 180, pdf.get_y())
    pdf.ln(10)

    pdf.set_font(font_name, "", 10.5)
    for paragraph in [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]:
        lines = textwrap.wrap(
            re.sub(r"\s+", " ", paragraph),
            width=96,
            break_long_words=True,
            break_on_hyphens=True,
            replace_whitespace=True,
        ) or [paragraph]
        if len(paragraph) <= 90 and paragraph.upper() == paragraph and re.search(r"[A-Z]", paragraph, re.I):
            pdf.ln(2)
            pdf.set_font(font_name, "B", 11)
            for line in lines:
                pdf.multi_cell(0, 6, line, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_name, "", 10.5)
            pdf.ln(1)
        else:
            for line in lines:
                pdf.multi_cell(0, 5.8, line, align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.2)

    pdf.ln(4)
    pdf.set_font(font_name, "", 8)
    pdf.multi_cell(0, 4.5, f"Fonte: {source_url}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(pdf_path))


def download_docs(force: bool, renderer: str) -> dict[str, int]:
    edge_path = find_edge() if renderer == "edge" else None
    print(f"PDF renderer: {'Edge/Chromium' if edge_path else 'fpdf2'}", flush=True)
    stats = {
        "docs": len(REQUESTED_DOCS),
        "files_saved": 0,
        "files_reused": 0,
        "local_copied": 0,
        "lang_skipped": 0,
        "errors": 0,
    }

    for index, doc in enumerate(REQUESTED_DOCS, start=1):
        print(f"\n[{index}/{len(REQUESTED_DOCS)}] {doc.title} ({doc.year}) - {doc.author_full}", flush=True)
        out_dir = output_dir_for(doc)
        out_dir.mkdir(parents=True, exist_ok=True)

        if doc.local_latin_pdf and doc.local_latin_pdf.exists() and not doc.base_url:
            target = output_pdf_path(doc, "la")
            if force or not target.exists() or target.stat().st_size < 1000:
                shutil.copyfile(doc.local_latin_pdf, target)
                stats["local_copied"] += 1
                stats["files_saved"] += 1
                print(f"  [LA] local -> {target.name}", flush=True)
                append_manifest({
                    "title": doc.title,
                    "author": doc.author_short,
                    "year": doc.year,
                    "type_key": doc.type_key,
                    "language": "la",
                    "source": "local_latin_pdf",
                    "path": str(target.resolve()),
                    "status": "local_pdf",
                })
            else:
                stats["files_reused"] += 1
                print("  [LA] local ja existe - reutilizando.", flush=True)

        if not doc.base_url:
            continue

        lang_urls = candidate_language_urls(doc.base_url)
        for lang in LANGUAGES:
            if doc.local_latin_pdf and lang == "la" and not doc.base_url:
                continue
            lang_url = lang_urls.get(lang)
            if not lang_url:
                continue

            target = output_pdf_path(doc, lang)
            if not force and target.exists() and target.stat().st_size > 1000:
                stats["files_reused"] += 1
                print(f"  [{lang.upper()}] ja existe - reutilizando.", flush=True)
                continue

            page_html = fetch_html_once(lang_url)
            if not page_html:
                stats["lang_skipped"] += 1
                continue

            try:
                ok, status, chars = save_generated_pdf(doc, lang, lang_url, page_html, target, edge_path)
            except Exception as exc:
                stats["errors"] += 1
                print(f"  [{lang.upper()}] ERRO ao gerar PDF: {exc}", flush=True)
                continue
            if not ok:
                stats["lang_skipped"] += 1
                print(f"  [{lang.upper()}] pulado: {status} ({chars} chars)", flush=True)
                continue

            stats["files_saved"] += 1
            print(f"  [{lang.upper()}] salvo: {target.name} ({status}, {chars} chars)", flush=True)
            append_manifest({
                "title": doc.title,
                "author": doc.author_short,
                "year": doc.year,
                "type_key": doc.type_key,
                "language": lang,
                "page_url": lang_url,
                "source": "vatican",
                "path": str(target.resolve()),
                "status": status,
            })
            time.sleep(0.2)

    return stats


def find_book(db, doc: RequestedDoc) -> Book | None:
    return (
        db.query(Book)
        .filter(
            Book.title == doc.title,
            Book.document_type == doc.type_key,
            Book.document_year == doc.year,
        )
        .order_by(Book.id.asc())
        .first()
    )


def ensure_book(db, doc: RequestedDoc) -> Book:
    book = find_book(db, doc)
    if book is None:
        book = Book(
            collection=COLLECTION,
            title=doc.title,
            author=doc.author_full,
            language="multi",
            edition_label="Vatican.va PDFs multilingues",
            source_label=SOURCE_LABEL,
            is_primary_source=True,
            library_section=LIBRARY_SECTION,
            patristic_tradition=None,
            document_type=doc.type_key,
            canonical_author=doc.author_full,
            canonical_title=doc.title,
            pope=doc.author_short,
            document_year=doc.year,
            is_ecumenical=False,
            document_status="official",
            volume_number=None,
            ingest_status="indexing",
            ingest_error=None,
        )
        db.add(book)
        db.flush()
        return book

    book.collection = book.collection or COLLECTION
    book.author = doc.author_full
    book.canonical_author = doc.author_full
    book.canonical_title = doc.title
    book.source_label = SOURCE_LABEL
    book.is_primary_source = True
    book.library_section = LIBRARY_SECTION
    book.document_type = doc.type_key
    book.pope = doc.author_short
    book.document_year = doc.year
    book.document_status = book.document_status or "official"
    if book.ingest_status != "done":
        book.ingest_status = "indexing"
    db.flush()
    return book


def pdf_language(pdf_path: Path) -> str:
    match = re.search(r" - ([A-Z]{2,3})\.pdf$", pdf_path.name)
    return match.group(1).lower() if match else "xx"


def chroma_read_collections(semantic_search: SemanticSearchClient) -> list:
    collections = [semantic_search.collection]
    delta_collection = getattr(semantic_search, "delta_collection", None)
    if delta_collection is not None and delta_collection is not semantic_search.collection:
        collections.append(delta_collection)
    return collections


def chroma_write_collection(semantic_search: SemanticSearchClient):
    return getattr(semantic_search, "delta_collection", semantic_search.collection)


def existing_chroma_ids(semantic_search: SemanticSearchClient, book_id: int) -> set[str]:
    ids: set[str] = set()
    for collection in chroma_read_collections(semantic_search):
        try:
            result = collection.get(
                where={"book_id": book_id},
                limit=100000,
                include=["metadatas"],
            )
            ids.update(result.get("ids", []))
        except Exception:
            continue
    return ids


def index_chroma_items(
    semantic_search: SemanticSearchClient,
    items: list[tuple[int, str, dict]],
    batch_size: int,
    cooldown_seconds: float,
) -> int:
    if not items:
        return 0

    model = _get_model()
    indexed = 0
    starts = range(0, len(items), batch_size)
    total_batches = (len(items) + batch_size - 1) // batch_size
    for batch_num, start in enumerate(starts, start=1):
        batch = items[start:start + batch_size]
        ids = [str(chunk_id) for chunk_id, _, _ in batch]
        texts = [text for _, text, _ in batch]
        metadatas = [metadata for _, _, metadata in batch]
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
        ).tolist()
        chroma_write_collection(semantic_search).add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        indexed += len(batch)
        print(f"      Chroma batch {batch_num}/{total_batches}: {indexed}/{len(items)}", flush=True)
        if cooldown_seconds > 0 and batch_num < total_batches:
            time.sleep(cooldown_seconds)
    return indexed


def es_count(text_search: TextSearchClient, book_id: int) -> int:
    try:
        return int(
            text_search.es.count(
                index=ES_INDEX,
                body={"query": {"term": {"book_id": book_id}}},
            ).get("count", 0)
        )
    except Exception:
        return 0


def chroma_count(semantic_search: SemanticSearchClient, book_id: int) -> int:
    return len(existing_chroma_ids(semantic_search, book_id))


def update_book_language_and_status(
    db,
    book_id: int,
    text_search: TextSearchClient,
    semantic_search: SemanticSearchClient | None,
) -> tuple[int, int, int, str]:
    book = db.get(Book, book_id)
    if book is None:
        return 0, 0, 0, "missing"

    files = db.query(BookFile).filter(BookFile.book_id == book_id).all()
    langs = sorted({pdf_language(Path(f.original_filename)) for f in files if f.original_filename})
    if len(langs) > 1:
        book.language = "multi"
        book.edition_label = "Vatican.va PDFs multilingues"
    elif langs:
        book.language = langs[0]
        book.edition_label = f"Vatican.va PDF {langs[0].upper()}"

    db_chunks = db.query(Chunk).filter(Chunk.book_id == book_id).count()
    es_docs = es_count(text_search, book_id)
    chroma_docs = chroma_count(semantic_search, book_id) if semantic_search is not None else 0
    if db_chunks > 0 and es_docs >= db_chunks and chroma_docs >= db_chunks:
        book.ingest_status = "done"
        book.ingest_error = None
        status = "done"
    else:
        book.ingest_status = "processing"
        if semantic_search is None:
            book.ingest_error = f"Parcial: DB={db_chunks}, ES={es_docs}, Chroma=pulado"
        else:
            book.ingest_error = f"Parcial: DB={db_chunks}, ES={es_docs}, Chroma={chroma_docs}"
        status = "processing"
    db.flush()
    return db_chunks, es_docs, chroma_docs, status


def ingest_docs(batch_size: int, cooldown_seconds: float, skip_chroma: bool) -> dict[str, int]:
    init_db(reset=False)

    extractor = PDFExtractor()
    chunker = Chunker()
    text_search = TextSearchClient()
    semantic_search = None if skip_chroma else SemanticSearchClient()

    stats = {
        "books": 0,
        "files_indexed": 0,
        "files_skipped": 0,
        "chunks_created": 0,
        "chroma_indexed": 0,
        "errors": 0,
    }

    for index, doc in enumerate(REQUESTED_DOCS, start=1):
        pdf_files = sorted(output_dir_for(doc).glob("*.pdf"))
        print(f"\nINGEST [{index}/{len(REQUESTED_DOCS)}] {doc.title}: {len(pdf_files)} PDF(s)", flush=True)
        if not pdf_files:
            stats["errors"] += 1
            print("  ERRO: nenhum PDF encontrado.", flush=True)
            continue

        with SessionLocal() as db:
            book = ensure_book(db, doc)
            db.commit()
            book_id = book.id
        stats["books"] += 1

        for pdf_path in pdf_files:
            lang = pdf_language(pdf_path)
            stored_path = str(pdf_path.resolve())
            try:
                with SessionLocal() as db:
                    book_file = (
                        db.query(BookFile)
                        .filter(BookFile.book_id == book_id, BookFile.stored_path == stored_path)
                        .first()
                    )
                    if book_file is not None:
                        existing_chunks = (
                            db.query(Chunk)
                            .filter(Chunk.book_file_id == book_file.id)
                            .order_by(Chunk.id.asc())
                            .all()
                        )
                        if existing_chunks:
                            print(f"  [{lang.upper()}] ja tinha {len(existing_chunks)} chunks - conferindo indices.", flush=True)
                            chunk_records = existing_chunks
                        else:
                            chunk_records = []
                    else:
                        book_file = BookFile(
                            book_id=book_id,
                            original_filename=pdf_path.name,
                            stored_path=stored_path,
                            volume_number=None,
                            editor=SOURCE_LABEL,
                            translator=None,
                        )
                        db.add(book_file)
                        db.flush()
                        chunk_records = []

                    if not chunk_records:
                        print(f"  [{lang.upper()}] extraindo: {pdf_path.name}", flush=True)
                        pages = extractor.extract(stored_path)
                        total_chars = sum(len(page.get("text", "")) for page in pages)
                        if total_chars < 100:
                            raise RuntimeError(f"texto extraido muito curto ({total_chars} chars)")
                        raw_chunks = chunker.chunk(pages, document_meta={})
                        print(f"      {len(pages)} paginas, {total_chars} chars, {len(raw_chunks)} chunks", flush=True)
                        chunk_records = []
                        for seq, chunk_data in enumerate(raw_chunks):
                            chunk = Chunk(
                                book_id=book_id,
                                book_file_id=book_file.id,
                                text=chunk_data["text"],
                                sequence_index=seq,
                                pdf_page=chunk_data.get("pdf_page"),
                                char_offset_start=chunk_data.get("char_offset_start"),
                                char_offset_end=chunk_data.get("char_offset_end"),
                            )
                            db.add(chunk)
                            chunk_records.append(chunk)
                        db.flush()
                        stats["chunks_created"] += len(chunk_records)

                    db.commit()
                    chunk_ids = [chunk.id for chunk in chunk_records]

                with SessionLocal() as db:
                    chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).order_by(Chunk.id.asc()).all()

                es_items = []
                chroma_items = []
                existing_ids = existing_chroma_ids(semantic_search, book_id) if semantic_search else set()
                for chunk in chunks:
                    edition = f"Vatican.va {LANG_LABEL.get(lang, lang.upper())}"
                    es_doc = {
                        "book_id": book_id,
                        "book_file_id": chunk.book_file_id,
                        "text": chunk.text,
                        "author": doc.author_full,
                        "work_title": doc.title,
                        "collection": COLLECTION,
                        "language": lang,
                        "pdf_page": chunk.pdf_page,
                        "edition_label": edition,
                        "chapter_or_section": chunk.chapter_or_section or "",
                        "char_offset_start": chunk.char_offset_start,
                        "char_offset_end": chunk.char_offset_end,
                    }
                    es_items.append((chunk.id, es_doc))
                    if semantic_search and str(chunk.id) not in existing_ids:
                        chroma_items.append((
                            chunk.id,
                            chunk.text,
                            {
                                "chunk_id": str(chunk.id),
                                "book_id": book_id,
                                "book_file_id": chunk.book_file_id or 0,
                                "author": doc.author_full,
                                "work_title": doc.title,
                                "collection": COLLECTION,
                                "document_type": doc.type_key,
                                "source_label": SOURCE_LABEL,
                                "pope": doc.author_short,
                                "language": normalize_lang(lang),
                            },
                        ))

                text_search.index_chunks(es_items)
                indexed = 0
                if semantic_search:
                    indexed = index_chroma_items(
                        semantic_search,
                        chroma_items,
                        batch_size=batch_size,
                        cooldown_seconds=cooldown_seconds,
                    )
                stats["chroma_indexed"] += indexed
                stats["files_indexed"] += 1
                print(f"      indices OK: ES={len(es_items)} Chroma novos={indexed}", flush=True)
                if cooldown_seconds > 0:
                    time.sleep(cooldown_seconds)

            except Exception as exc:
                stats["errors"] += 1
                print(f"  [{lang.upper()}] ERRO: {exc}", flush=True)
                with SessionLocal() as db:
                    book = db.get(Book, book_id)
                    if book:
                        book.ingest_status = "processing"
                        book.ingest_error = str(exc)[:1000]
                    db.commit()

        with SessionLocal() as db:
            db_chunks, es_docs, chroma_docs, status = update_book_language_and_status(
                db,
                book_id,
                text_search,
                semantic_search,
            )
            db.commit()
        print(f"  STATUS {status}: DB={db_chunks} ES={es_docs} Chroma={chroma_docs}", flush=True)

    return stats


def report_requested_state() -> None:
    semantic_search = SemanticSearchClient()
    text_search = TextSearchClient()
    titles = [doc.title for doc in REQUESTED_DOCS]
    with SessionLocal() as db:
        rows = (
            db.query(Book)
            .filter(Book.title.in_(titles))
            .order_by(Book.document_year.asc(), Book.title.asc(), Book.id.asc())
            .all()
        )
        print("\nRELATORIO FINAL")
        print(f"Livros encontrados: {len(rows)}/{len(REQUESTED_DOCS)}")
        for book in rows:
            files = db.query(BookFile).filter(BookFile.book_id == book.id).count()
            chunks = db.query(Chunk).filter(Chunk.book_id == book.id).count()
            es_docs = es_count(text_search, book.id)
            chroma_docs = chroma_count(semantic_search, book.id)
            print(
                f"  id={book.id} {book.title} ({book.document_year}) "
                f"files={files} chunks={chunks} ES={es_docs} Chroma={chroma_docs} "
                f"status={book.ingest_status}",
                flush=True,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Baixa e ingere os documentos papais pedidos em 2026-04-19.")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--ingest-only", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--cooldown-seconds", type=float, default=0.75)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="cuda")
    parser.add_argument("--renderer", choices=["fpdf", "edge"], default="fpdf")
    parser.add_argument("--skip-chroma", action="store_true", help="Importa DB/Elasticsearch sem carregar embeddings.")
    args = parser.parse_args()

    os.environ["VERA_EMBEDDING_DEVICE"] = args.device
    os.environ["OMP_NUM_THREADS"] = str(args.threads)
    os.environ["MKL_NUM_THREADS"] = str(args.threads)
    try:
        import torch

        torch.set_num_threads(args.threads)
        torch.set_num_interop_threads(max(1, min(args.threads, 4)))
        print(
            f"Torch {torch.__version__}; cuda={torch.cuda.is_available()}; "
            f"device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'}",
            flush=True,
        )
    except Exception as exc:
        print(f"AVISO: nao foi possivel configurar torch: {exc}", flush=True)

    if not args.ingest_only:
        download_stats = download_docs(force=args.force_download, renderer=args.renderer)
        print("DOWNLOAD_STATS " + " ".join(f"{k}={v}" for k, v in download_stats.items()), flush=True)

    if not args.download_only:
        ingest_stats = ingest_docs(
            batch_size=args.batch_size,
            cooldown_seconds=args.cooldown_seconds,
            skip_chroma=args.skip_chroma,
        )
        print("INGEST_STATS " + " ".join(f"{k}={v}" for k, v in ingest_stats.items()), flush=True)
        report_requested_state()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
