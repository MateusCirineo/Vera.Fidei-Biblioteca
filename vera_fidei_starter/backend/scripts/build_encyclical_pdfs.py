from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import textwrap
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests


INDEX_URL = "https://www.catolicoorante.com.br/docs/enciclicas/index.html"

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "pdfs" / "enciclicas"
DEFAULT_HTML_DIR = BACKEND_DIR / ".tmp_encyclical_html"


@dataclass(frozen=True)
class EncyclicalItem:
    pope: str
    pope_heading: str
    title: str
    url: str
    index: int


class IndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[EncyclicalItem] = []
        self.current_pope_heading = "Enciclicas Papais"
        self.current_pope = "Enciclicas Papais"
        self._capture_tag: str | None = None
        self._capture_href: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "h3":
            self._capture_tag = tag
            self._buffer = []
            return
        if tag == "a" and attrs_dict.get("href"):
            self._capture_tag = tag
            self._capture_href = attrs_dict["href"]
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture_tag:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self._capture_tag:
            return

        text = clean_inline_text(" ".join(self._buffer))
        if tag == "h3" and text:
            self.current_pope_heading = text
            self.current_pope = canonical_pope_name(text)
        elif tag == "a" and text and self._capture_href:
            self.items.append(
                EncyclicalItem(
                    pope=self.current_pope,
                    pope_heading=self.current_pope_heading,
                    title=text,
                    url=urljoin(INDEX_URL, self._capture_href),
                    index=len(self.items) + 1,
                )
            )

        self._capture_tag = None
        self._capture_href = None
        self._buffer = []


class TextHTMLParser(HTMLParser):
    block_tags = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "center",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "title",
        "tr",
        "ul",
    }

    skip_tags = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._in_body = False
        self._seen_body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "body":
            self._in_body = True
            self._seen_body = True
        if tag in self.skip_tags:
            self._skip_depth += 1
        if self._accept_text() and tag in self.block_tags:
            self._newline()
            if tag == "li":
                self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip_tags and self._skip_depth:
            self._skip_depth -= 1
        if self._accept_text() and tag in self.block_tags:
            self._newline()
        if tag == "body":
            self._in_body = False

    def handle_data(self, data: str) -> None:
        if not self._accept_text():
            return
        data = data.replace("\xa0", " ")
        data = re.sub(r"\s+", " ", data)
        if data.strip():
            self.parts.append(data)

    def _accept_text(self) -> bool:
        return self._skip_depth == 0 and (self._in_body or not self._seen_body)

    def _newline(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")
        if self.parts and self.parts[-1] != "\n\n":
            self.parts.append("\n")

    def paragraphs(self) -> list[str]:
        raw = "".join(self.parts).replace("\ufeff", "")
        raw = html.unescape(raw)
        lines = [clean_inline_text(line) for line in raw.splitlines()]
        paragraphs: list[str] = []
        current: list[str] = []
        for line in lines:
            if not line:
                if current:
                    paragraphs.append(clean_inline_text(" ".join(current)))
                    current = []
                continue
            current.append(line)
        if current:
            paragraphs.append(clean_inline_text(" ".join(current)))
        return [p for p in paragraphs if p and not should_drop_paragraph(p)]


def clean_inline_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def should_drop_paragraph(text: str) -> bool:
    lowered = text.lower()
    return lowered in {"enciclicas papais", "enciclicas papais "} or lowered.startswith("javascript:")


def canonical_pope_name(heading: str) -> str:
    normalized = normalize_ascii(heading)
    patterns = [
        ("BENTO XVI", "Papa Bento XVI"),
        ("JOAO PAULO II", "Papa Jo\u00e3o Paulo II"),
        ("PAULO VI", "Papa Paulo VI"),
        ("JOAO XXIII", "Papa Jo\u00e3o XXIII"),
        ("PIO XII", "Papa Pio XII"),
        ("PIO XI", "Papa Pio XI"),
        ("SAO PIO X", "Papa S\u00e3o Pio X"),
        ("LEAO XIII", "Papa Le\u00e3o XIII"),
    ]
    for token, display in patterns:
        if token in normalized:
            return display
    text = re.sub(r"^PAPA\s+", "", heading, flags=re.I)
    text = re.split(r"\s+\(", text)[0]
    return f"Papa {titlecase_name(text)}"


def titlecase_name(text: str) -> str:
    minor = {"de", "da", "do", "dos", "das", "e"}
    words = []
    for word in text.lower().split():
        words.append(word if word in minor else word.capitalize())
    return " ".join(words)


def normalize_ascii(text: str) -> str:
    replacements = {
        "\u00c1": "A",
        "\u00c0": "A",
        "\u00c2": "A",
        "\u00c3": "A",
        "\u00c9": "E",
        "\u00ca": "E",
        "\u00cd": "I",
        "\u00d3": "O",
        "\u00d4": "O",
        "\u00d5": "O",
        "\u00da": "U",
        "\u00c7": "C",
        "\u00e1": "a",
        "\u00e0": "a",
        "\u00e2": "a",
        "\u00e3": "a",
        "\u00e9": "e",
        "\u00ea": "e",
        "\u00ed": "i",
        "\u00f3": "o",
        "\u00f4": "o",
        "\u00f5": "o",
        "\u00fa": "u",
        "\u00e7": "c",
    }
    return "".join(replacements.get(c, c) for c in text).upper()


def filename_title(title: str) -> str:
    main = re.split(r"\s+[(-]\d|\s+\u2013|\s+-", title, maxsplit=1)[0]
    main = smart_title(clean_inline_text(main))
    main = re.sub(r"\s+", " ", main)
    return sanitize_path_part(main, max_len=110)


def smart_title(text: str) -> str:
    """Title-case Latin document names without turning every small word into caps."""
    small_words = {"a", "as", "ao", "aos", "da", "das", "de", "do", "dos", "e", "em", "et", "in", "o", "os"}
    roman_tokens = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI"}
    words = re.split(r"(\s+)", text.lower())
    result: list[str] = []
    word_index = 0
    for part in words:
        if not part.strip():
            result.append(part)
            continue
        upper = part.upper()
        if upper in roman_tokens:
            result.append(upper)
        elif word_index > 0 and part in small_words:
            result.append(part)
        else:
            result.append(part[:1].upper() + part[1:])
        word_index += 1
    return "".join(result)


def sanitize_path_part(text: str, max_len: int = 120) -> str:
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r'[<>:"/\\|?*]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if len(text) > max_len:
        text = text[:max_len].rstrip(" .")
    return text or "sem titulo"


def fetch_text(url: str, session: requests.Session) -> str:
    response = session.get(url, timeout=45)
    response.raise_for_status()
    content = response.content
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        response.encoding = response.apparent_encoding or response.encoding
        return response.text


def parse_index(session: requests.Session) -> list[EncyclicalItem]:
    parser = IndexParser()
    parser.feed(fetch_text(INDEX_URL, session))
    return parser.items


def parse_body_paragraphs(html_text: str) -> list[str]:
    parser = TextHTMLParser()
    parser.feed(html_text)
    return parser.paragraphs()


class SimplePDF:
    width = 595.28
    height = 841.89
    margin_left = 62
    margin_right = 62
    top = 760
    bottom = 72
    body_size = 11.5
    line_height = 15.5

    def __init__(self, title: str, pope: str, source_url: str) -> None:
        self.title = title
        self.pope = pope
        self.source_url = source_url
        self.pages: list[list[tuple[str, float, float, float, str]]] = []
        self.current: list[tuple[str, float, float, float, str]] = []
        self.y = self.top
        self.page_number = 0
        self._new_page()

    def add_title_page(self) -> None:
        self._draw_text(self.pope, self.margin_left, 690, 14, "bold")
        for i, line in enumerate(wrap_text(self.title, 50)):
            self._draw_text(line, self.margin_left, 650 - i * 24, 21, "title")
        self._draw_text("Carta Enc\u00edclica", self.margin_left, 560, 13, "italic")
        self._draw_text("Fonte: Vatican.va", self.margin_left, 520, 10.5, "body")
        self.y = 455

    def add_paragraphs(self, paragraphs: Iterable[str]) -> None:
        for paragraph in paragraphs:
            kind = paragraph_kind(paragraph)
            if kind == "heading":
                self._space(10)
                self._add_wrapped(paragraph, 13.5, "bold", width=58, line_height=18)
                self._space(4)
            elif kind == "subheading":
                self._space(6)
                self._add_wrapped(paragraph, 12.5, "bold", width=66, line_height=17)
                self._space(2)
            else:
                self._add_wrapped(paragraph, self.body_size, "body", width=88, line_height=self.line_height)
                self._space(6)

    def save(self, path: Path) -> None:
        if self.current:
            self.pages.append(self.current)
            self.current = []
        objects: list[bytes] = []

        def add_object(data: bytes) -> int:
            objects.append(data)
            return len(objects)

        font_body = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>")
        font_bold = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>")
        font_italic = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic /Encoding /WinAnsiEncoding >>")
        font_title = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

        page_object_ids: list[int] = []
        content_object_ids: list[int] = []
        for page_index, page_lines in enumerate(self.pages, start=1):
            content = self._page_content(page_lines, page_index, len(self.pages))
            stream = b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream"
            content_id = add_object(stream)
            content_object_ids.append(content_id)
            page_id = add_object(b"")
            page_object_ids.append(page_id)

        pages_id = add_object(b"")
        catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii"))

        for page_id, content_id in zip(page_object_ids, content_object_ids):
            page = (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Resources << /Font << /F1 {font_body} 0 R /F2 {font_bold} 0 R /F3 {font_italic} 0 R /F4 {font_title} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            )
            objects[page_id - 1] = page.encode("ascii")

        kids = " ".join(f"{obj_id} 0 R" for obj_id in page_object_ids)
        objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode("ascii")

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            fh.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
            offsets = [0]
            for obj_id, data in enumerate(objects, start=1):
                offsets.append(fh.tell())
                fh.write(f"{obj_id} 0 obj\n".encode("ascii"))
                fh.write(data)
                fh.write(b"\nendobj\n")
            xref = fh.tell()
            fh.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
            fh.write(b"0000000000 65535 f \n")
            for offset in offsets[1:]:
                fh.write(f"{offset:010d} 00000 n \n".encode("ascii"))
            fh.write(
                (
                    f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
                    f"startxref\n{xref}\n%%EOF\n"
                ).encode("ascii")
            )

    def _new_page(self) -> None:
        if self.current:
            self.pages.append(self.current)
        self.current = []
        self.page_number += 1
        self.y = self.top

    def _draw_text(self, text: str, x: float, y: float, size: float, style: str) -> None:
        self.current.append((text, x, y, size, style))

    def _space(self, amount: float) -> None:
        self.y -= amount
        if self.y < self.bottom:
            self._new_page()

    def _add_wrapped(self, paragraph: str, size: float, style: str, width: int, line_height: float) -> None:
        for line in wrap_text(paragraph, width):
            if self.y < self.bottom:
                self._new_page()
            self._draw_text(line, self.margin_left, self.y, size, style)
            self.y -= line_height

    def _page_content(
        self, lines: list[tuple[str, float, float, float, str]], page_index: int, page_count: int
    ) -> bytes:
        chunks: list[bytes] = []
        if page_index == 1:
            chunks.append(b"0.88 0.72 0.28 rg\n0 810 595.28 31.89 re f\n")
        chunks.append(b"0.12 0.12 0.12 rg\n")
        for text, x, y, size, style in lines:
            font = {"body": "F1", "bold": "F2", "italic": "F3", "title": "F4"}[style]
            escaped = pdf_escape(text)
            chunks.append(f"BT /{font} {size:.2f} Tf {x:.2f} {y:.2f} Td ".encode("ascii"))
            chunks.append(b"(" + escaped + b") Tj ET\n")
        footer = f"{self.pope} | {page_index}/{page_count}"
        chunks.append(b"0.45 0.45 0.45 rg\n")
        chunks.append(f"BT /F1 8.5 Tf {self.margin_left:.2f} 38 Td ".encode("ascii"))
        chunks.append(b"(" + pdf_escape(footer) + b") Tj ET\n")
        return b"".join(chunks)


def wrap_text(text: str, width: int) -> list[str]:
    text = clean_inline_text(text)
    if not text:
        return []
    return textwrap.wrap(text, width=width, break_long_words=False, replace_whitespace=True) or [text]


def paragraph_kind(text: str) -> str:
    stripped = text.strip()
    if len(stripped) <= 90 and stripped.upper() == stripped and re.search(r"[A-Z]", normalize_ascii(stripped)):
        return "heading"
    if len(stripped) <= 70 and re.match(r"^(CAPITULO|INTRODUCAO|CONCLUSAO|I\.|II\.|III\.|IV\.|V\.|VI\.)", normalize_ascii(stripped)):
        return "subheading"
    return "body"


def pdf_escape(text: str) -> bytes:
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text.encode("cp1252", errors="replace")


def find_edge() -> str | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("msedge") or shutil.which("chrome") or shutil.which("chromium")


def build_html_document(item: EncyclicalItem, paragraphs: list[str]) -> str:
    title = html.escape(item.title)
    pope = html.escape(item.pope)
    body_parts = []
    for paragraph in paragraphs:
        kind = paragraph_kind(paragraph)
        escaped = html.escape(paragraph)
        if kind == "heading":
            body_parts.append(f"<h2>{escaped}</h2>")
        elif kind == "subheading":
            body_parts.append(f"<h3>{escaped}</h3>")
        else:
            body_parts.append(f"<p>{escaped}</p>")

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    @page {{
      size: A4;
      margin: 22mm 20mm 22mm 20mm;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      color: #1b1b1b;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 11.4pt;
      line-height: 1.48;
      margin: 0;
      text-rendering: optimizeLegibility;
    }}
    .cover {{
      break-after: page;
      min-height: 245mm;
      display: flex;
      flex-direction: column;
      justify-content: center;
      text-align: center;
      border-top: 1.5pt solid #b08d2c;
      border-bottom: 1.5pt solid #b08d2c;
      padding: 18mm 7mm;
    }}
    .source {{
      color: #9a7a21;
      font-family: Arial, sans-serif;
      font-size: 10pt;
      letter-spacing: .04em;
      margin-bottom: 16mm;
    }}
    .pope {{
      font-size: 15pt;
      font-variant: small-caps;
      letter-spacing: .03em;
      margin-bottom: 9mm;
    }}
    h1 {{
      font-size: 24pt;
      line-height: 1.16;
      margin: 0 0 10mm;
      overflow-wrap: anywhere;
      text-transform: uppercase;
    }}
    .doc-type {{
      font-size: 12pt;
      font-style: italic;
    }}
    .content {{
      margin: 0 auto;
      max-width: 166mm;
    }}
    .content h2 {{
      break-after: avoid;
      font-size: 14.5pt;
      line-height: 1.25;
      margin: 10mm 0 4mm;
      text-align: center;
      text-transform: uppercase;
    }}
    .content h3 {{
      break-after: avoid;
      font-size: 12.6pt;
      margin: 7mm 0 3mm;
      text-align: center;
      text-transform: uppercase;
    }}
    .content p {{
      margin: 0 0 3.4mm;
      orphans: 3;
      text-align: justify;
      widows: 3;
    }}
    .content p:first-child {{
      margin-top: 0;
    }}
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
    <div class="pope">{pope}</div>
    <h1>{title}</h1>
    <div class="doc-type">Carta Encíclica</div>
  </section>
  <main class="content">
    {''.join(body_parts)}
    <div class="footer-source">Fonte: Vatican.va</div>
  </main>
</body>
</html>
"""


def build_pdf_with_edge(
    item: EncyclicalItem,
    paragraphs: list[str],
    output_dir: Path,
    edge_path: str,
    html_dir: Path = DEFAULT_HTML_DIR,
) -> Path:
    pope_dir = output_dir / sanitize_path_part(item.pope, max_len=80)
    name = f"{item.index:03d} - {filename_title(item.title)}.pdf"
    path = pope_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)

    html_dir.mkdir(parents=True, exist_ok=True)
    html_path = html_dir / f"{item.index:03d}_{sanitize_path_part(filename_title(item.title), max_len=80)}.html"
    profile_dir = html_dir / f"profile_{item.index:03d}"
    html_path.write_text(build_html_document(item, paragraphs), encoding="utf-8")
    if path.exists():
        path.unlink()

    command = [
        edge_path,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--user-data-dir={profile_dir}",
        f"--print-to-pdf={path}",
        html_path.resolve().as_uri(),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not path.exists():
        raise RuntimeError(f"Edge falhou ao gerar PDF: {result.stderr[-500:]}")
    return path


def build_pdf(
    item: EncyclicalItem,
    paragraphs: list[str],
    output_dir: Path,
    edge_path: str | None = None,
) -> Path:
    if edge_path:
        return build_pdf_with_edge(item, paragraphs, output_dir, edge_path)
    pope_dir = output_dir / sanitize_path_part(item.pope, max_len=80)
    name = f"{item.index:03d} - {filename_title(item.title)}.pdf"
    path = pope_dir / name
    pdf = SimplePDF(title=item.title, pope=item.pope, source_url=item.url)
    pdf.add_title_page()
    pdf.add_paragraphs(paragraphs)
    pdf.save(path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Download papal encyclicals and build readable PDFs.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=0, help="Limit number of encyclicals, for testing.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing PDFs.")
    parser.add_argument("--clean-output", action="store_true", help="Remove existing generated encyclical PDFs before writing.")
    parser.add_argument("--delay", type=float, default=0.25, help="Delay between requests.")
    parser.add_argument(
        "--renderer",
        choices=["auto", "edge", "simple"],
        default="auto",
        help="PDF renderer. Edge gives better margins and typography.",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Vera.Fidei Biblioteca/1.0 (+local research archive; contact: local)",
        }
    )

    items = parse_index(session)
    if args.limit:
        items = items[: args.limit]

    if args.clean_output and args.output_dir.exists():
        for pdf in args.output_dir.rglob("*.pdf"):
            pdf.unlink()

    edge_path = find_edge() if args.renderer in {"auto", "edge"} else None
    if args.renderer == "edge" and edge_path is None:
        print("ERRO: Microsoft Edge/Chrome não encontrado para renderer=edge.")
        return 1
    if edge_path:
        print(f"Renderer: Edge/Chromium ({edge_path})")
    else:
        print("Renderer: simples interno")

    print(f"Encontradas {len(items)} enciclicas.")
    created = 0
    skipped = 0
    failed: list[tuple[EncyclicalItem, str]] = []

    for item in items:
        pope_dir = args.output_dir / sanitize_path_part(item.pope, max_len=80)
        target = pope_dir / f"{item.index:03d} - {filename_title(item.title)}.pdf"
        if target.exists() and not args.force:
            print(f"[skip] {target}")
            skipped += 1
            continue
        try:
            html_text = fetch_text(item.url, session)
            paragraphs = parse_body_paragraphs(html_text)
            if not paragraphs:
                raise RuntimeError("nenhum texto extraido da pagina")
            path = build_pdf(item, paragraphs, args.output_dir, edge_path=edge_path)
            print(f"[ok] {item.pope} - {filename_title(item.title)} -> {path}")
            created += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[falha] {item.title}: {exc}")
            failed.append((item, str(exc)))
        time.sleep(args.delay)

    print()
    print(f"PDFs criados: {created}")
    print(f"PDFs pulados: {skipped}")
    print(f"Falhas: {len(failed)}")
    if failed:
        for item, reason in failed:
            print(f" - {item.index:03d} {item.title}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
