"""
Redesign user-supplied council PDFs into the Vatican.va style used by Vera.Fidei.

Reads PDFs from a source folder, extracts text, applies the HTML/Edge template
from build_council_pdfs.py, and saves the redesigned PDFs to the correct
backend/pdfs/concilios/ folder structure.

Usage:
    python -m scripts.redesign_user_pdfs --source-dir "C:\\Users\\...\\Concilios" --dry-run
    python -m scripts.redesign_user_pdfs --source-dir "C:\\Users\\...\\Concilios"
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import pdfplumber

# ─── Reuse rendering functions from build_council_pdfs.py ────────────────────
_scripts = Path(__file__).parent
sys.path.insert(0, str(_scripts))
from build_council_pdfs import (
    build_html_document,
    build_pdf_with_edge,
    find_edge,
    paragraph_kind,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
CONCILIOS_DIR = BACKEND_DIR / "pdfs" / "concilios"

# ─── Council output configuration ────────────────────────────────────────────

NICEIA_FOLDER  = CONCILIOS_DIR / "Seculo IV (325-381)" / "01 - 325 - Niceia I"
TRENTO_FOLDER  = CONCILIOS_DIR / "Seculo XVI (1512-1563)" / "19 - 1545 - Trento"

NICEIA_DISPLAY = "Concílio de Nicéia I (325)"
TRENTO_DISPLAY = "Concílio de Trento (1545–1563)"

# Roman numerals for Trento session normalization
_ARABIC_TO_ROMAN = {
    "1": "I", "2": "II", "3": "III", "4": "IV", "5": "V",
    "6": "VI", "7": "VII", "8": "VIII", "9": "IX", "10": "X",
}


# ─── Text extraction ──────────────────────────────────────────────────────────

_REPL_CHAR = chr(0xFFFD)  # Unicode replacement char from broken PDF fonts

# Common Portuguese ligature/encoding fix-ups from broken PDF fonts
_FIXUPS: list[tuple[str, str]] = [
    # uppercase accented
    (r"C\?nones",    "Cânones"),
    (r"C\?nons",     "Cânons"),
    (r"ECUME\? NICO","ECUMÊNICO"),
    (r"ECUMEN\?CO",  "ECUMÊNICO"),
    (r"Sess\?o",     "Sessão"),
    (r"Sac\?ros",    "Sacros"),
    (r"Cat\?lica",   "Católica"),
    (r"dog\?tica",   "dogmática"),
    (r"dog\?tico",   "dogmático"),
    (r"Conc\?lio",   "Concílio"),
    (r"Conc\?",      "Conc"),
]


def _clean_text(raw: str) -> str:
    # Replace Unicode replacement char with ? and strip null bytes
    text = raw.replace(chr(0xFFFD), "?").replace(chr(0), "")
    for pattern, replacement in _FIXUPS:
        text = re.sub(pattern, replacement, text)
    # Normalize Unicode (NFC) to merge combining chars
    text = unicodedata.normalize("NFC", text)
    return text


def extract_paragraphs(pdf_path: Path) -> list[str]:
    """Extract paragraphs from a PDF preserving structure."""
    lines: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            raw = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            cleaned = _clean_text(raw)
            lines.extend(cleaned.splitlines())

    paragraphs: list[str] = []
    buffer: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
        else:
            # Short all-caps lines are headings — flush buffer first
            stripped_ascii = re.sub(r"[^A-Za-z]", "", line.upper())
            is_caps_heading = (
                len(line) <= 90
                and line.upper() == line
                and len(stripped_ascii) > 2
            )
            # Numbered headings like "Canon I.", "CAPÍTULO I", "Sessão VI"
            is_numbered = bool(re.match(
                r"^(C[AÂ]NON|C[AÂ]NONE|CAP[IÍ]TULO|SESS[AÃ]O|DECRETO|DEFINIÇÃO|DE DECRETO|CANON)",
                line, re.IGNORECASE
            ))
            if is_caps_heading or is_numbered:
                if buffer:
                    paragraphs.append(" ".join(buffer))
                    buffer = []
                paragraphs.append(line)
            else:
                buffer.append(line)

    if buffer:
        paragraphs.append(" ".join(buffer))

    # Filter out very short noise lines (page numbers, headers)
    paragraphs = [p for p in paragraphs if len(p.strip()) > 3]
    return paragraphs


# ─── File mapping ─────────────────────────────────────────────────────────────

def _normalize_trento_title(stem: str) -> str:
    """Normalize Trento session titles: 'Sessão 1 - ...' → 'Sessão I - ...'"""
    m = re.match(r"^(Sess[aã]o)\s+(\d+)\s*[–—-]\s*(.*)", stem, re.IGNORECASE)
    if m:
        prefix, num, rest = m.groups()
        roman = _ARABIC_TO_ROMAN.get(num, num)
        return f"Sessão {roman} — {rest.strip()}"
    return stem


def _safe_folder_name(title: str) -> str:
    """Strip characters unsafe for Windows folder names."""
    return re.sub(r'[<>:"/\\|?*]', "", title).strip()


def discover_pdfs(source_dir: Path) -> list[tuple[Path, str, str, str]]:
    """
    Walk source_dir and return list of:
      (pdf_path, council_display_name, doc_title, out_folder_path)
    """
    results = []
    for pdf_path in sorted(source_dir.rglob("*.pdf")):
        parts = [p.name for p in pdf_path.parents]
        path_str = str(pdf_path)

        if "Niceia" in path_str or "Nic" in path_str and "325" in path_str:
            council_name   = NICEIA_DISPLAY
            council_folder = NICEIA_FOLDER
            doc_type       = "Documentos do Concílio"
        elif "Trento" in path_str:
            council_name   = TRENTO_DISPLAY
            council_folder = TRENTO_FOLDER
            doc_type       = "Documentos do Concílio"
        else:
            continue

        stem = pdf_path.stem  # filename without .pdf
        if council_name == TRENTO_DISPLAY:
            doc_title = _normalize_trento_title(stem)
        else:
            doc_title = stem

        safe_title = _safe_folder_name(doc_title)
        out_folder = council_folder / safe_title
        out_path   = out_folder / f"{safe_title} - PT.pdf"
        results.append((pdf_path, council_name, doc_title, out_path))

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Redesign user council PDFs to Vatican.va style")
    parser.add_argument("--source-dir", required=True, type=Path,
                        help="Folder containing the user's council PDFs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be generated without generating")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip if output PDF already exists (default: True)")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing output PDFs")
    args = parser.parse_args()

    skip_existing = args.skip_existing and not args.force
    source_dir = args.source_dir.resolve()
    if not source_dir.exists():
        print(f"ERROR: source dir not found: {source_dir}")
        sys.exit(1)

    items = discover_pdfs(source_dir)
    if not items:
        print("No PDFs found matching Nicéia or Trento.")
        sys.exit(0)

    edge_path = find_edge()
    if not edge_path and not args.dry_run:
        print("ERROR: Microsoft Edge not found. Install Edge or use --dry-run.")
        sys.exit(1)

    print(f"Found {len(items)} PDFs to process")
    print(f"Edge: {edge_path}")
    print()

    ok = 0
    skip = 0
    err = 0

    for idx, (pdf_path, council_name, doc_title, out_path) in enumerate(items, 1):
        label = f"[{idx:02d}/{len(items)}]"
        print(f"{label} {doc_title}")
        print(f"         src: {pdf_path.name}")
        print(f"         out: {out_path.relative_to(BACKEND_DIR)}")

        if args.dry_run:
            print("         DRY RUN — skip\n")
            continue

        if skip_existing and out_path.exists():
            print(f"         EXISTS — skip (use --force to overwrite)\n")
            skip += 1
            continue

        # Extract text
        try:
            paragraphs = extract_paragraphs(pdf_path)
            print(f"         extracted {len(paragraphs)} paragraphs", end=" ... ", flush=True)
        except Exception as e:
            print(f"         ERROR extracting text: {e}\n")
            err += 1
            continue

        if len(paragraphs) < 3:
            print(f"WARN: very few paragraphs ({len(paragraphs)}) — check PDF")

        # Determine doc_type from title context
        stem_lower = doc_title.lower()
        if "credo" in stem_lower:
            doc_type = "Símbolo de Fé"
        elif "canon" in stem_lower or "cânon" in stem_lower:
            doc_type = "Cânones Disciplinares"
        elif "bula" in stem_lower:
            doc_type = "Bula Papal"
        elif "sess" in stem_lower:
            doc_type = "Ata e Decretos"
        elif "carta" in stem_lower:
            doc_type = "Correspondência Conciliar"
        elif "documentos" in stem_lower and "sacrossanto" in stem_lower:
            doc_type = "Documentos Conciliares — Edição Completa"
        else:
            doc_type = "Documentos do Concílio"

        # Generate PDF via Edge
        try:
            build_pdf_with_edge(
                out_path=out_path,
                council_name=council_name,
                title=doc_title,
                doc_type=doc_type,
                source_label="Arquivo Vera.Fidei — Tradução Portuguesa",
                paragraphs=paragraphs,
                edge_path=edge_path,
                lang_code="pt",
                html_dir=BACKEND_DIR / ".tmp_council_html",
                index=idx,
            )
            size_kb = out_path.stat().st_size // 1024
            print(f"OK ({size_kb} KB)\n")
            ok += 1
        except Exception as e:
            print(f"ERROR generating PDF: {e}\n")
            err += 1

    print("=" * 55)
    print(f"Generated : {ok}")
    print(f"Skipped   : {skip}")
    print(f"Errors    : {err}")
    if not args.dry_run and ok > 0:
        print()
        print("Next step: run import_council_pdfs.py to register in DB")


if __name__ == "__main__":
    main()
