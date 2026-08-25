"""Carrossel no padrão visual fornecido pelo proprietário do Vera.Fidei."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.social.content_guard import normalize_text
from app.social.daily_card import format_reference
from app.social.post_model import SocialPostCandidate
from core.config import settings


CANVAS_SIZE = (1856, 2304)
_ASSETS = Path(__file__).resolve().parent / "assets"
_PAGE_TEMPLATE = _ASSETS / "templates" / "page_with_logo.png"
_COVER_REFERENCE = _ASSETS / "references" / "cover_saint_ambrose.png"
_CTA_REFERENCE = _ASSETS / "references" / "cta_saint_ambrose.jpg"

_NAVY = (2, 31, 49)
_GOLD = (202, 151, 58)
_INK = (8, 7, 5)
_REFERENCE_INK = (82, 24, 14)
_HIGHLIGHT = (102, 29, 20)


class BrandAssetError(RuntimeError):
    pass


@dataclass(slots=True)
class CarouselContent:
    candidate: SocialPostCandidate
    portrait_bytes: bytes
    pdf_page_bytes: bytes
    pdf_title_page_bytes: bytes | None = None
    pdf_excerpt_bytes: list[bytes] | None = None
    part_label: str = "PARTE 1"


def _require_file(path: str | Path, description: str) -> Path:
    file_path = Path(path)
    if not file_path.is_file():
        raise BrandAssetError(f"{description} não encontrado: {file_path}")
    return file_path


def _font(path: str | Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_require_file(path, "fonte obrigatória")), size)


def _serif(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/georgiab.ttf" if bold else "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/timesbd.ttf" if bold else "C:/Windows/Fonts/times.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    raise BrandAssetError("fonte serif da capa não encontrada")


def _body_font(size: int) -> ImageFont.FreeTypeFont:
    # A fonte real existe neste Windows como ARLRDBD.TTF. Não há fallback
    # visual silencioso: usar outra fonte descaracterizaria a arte aprovada.
    return _font(settings.social_body_font_path, size)


def _open_fit(path: Path) -> Image.Image:
    return ImageOps.fit(Image.open(_require_file(path, "asset de referência")).convert("RGB"), CANVAS_SIZE, Image.Resampling.LANCZOS)


def _wrap_by_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if current and draw.textlength(trial, font=font) > width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def _center_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    y: int,
    *,
    fill: tuple[int, int, int],
    spacing: int,
) -> int:
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        x = (CANVAS_SIZE[0] - (box[2] - box[0])) // 2
        draw.text((x, y), line, font=font, fill=fill, stroke_width=1, stroke_fill=(58, 38, 11))
        y += spacing
    return y


def _paste_with_feather(canvas: Image.Image, source: Image.Image, box: tuple[int, int, int, int]) -> None:
    width, height = box[2] - box[0], box[3] - box[1]
    fitted = ImageOps.fit(source.convert("RGB"), (width, height), Image.Resampling.LANCZOS, centering=(0.5, 0.32))
    mask = Image.new("L", (width, height), 255)
    edge = 45
    inner = Image.new("L", (width - 2 * edge, height - 2 * edge), 255)
    mask.paste(0, (0, 0, width, height))
    mask.paste(inner, (edge, edge))
    mask = mask.filter(ImageFilter.GaussianBlur(32))
    canvas.paste(fitted, (box[0], box[1]), mask)


def render_cover_slide(content: CarouselContent) -> bytes:
    if not content.portrait_bytes:
        raise BrandAssetError("retrato aprovado do autor é obrigatório")

    canvas = _open_fit(_COVER_REFERENCE)
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Remove exclusivamente as áreas variáveis do exemplo (retrato e título),
    # preservando literalmente logo, bordas, fundo e arquitetura fornecidos.
    draw.rounded_rectangle((36, 76, 975, 1630), radius=34, fill=_NAVY)
    portrait = Image.open(BytesIO(content.portrait_bytes)).convert("RGB")
    _paste_with_feather(canvas, portrait, (54, 95, 955, 1610))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rectangle((70, 1450, 1785, 2195), fill=_NAVY)

    part_font = _serif(62)
    title_font = _serif(126)
    part = content.part_label.upper()
    part_width = draw.textlength(part, font=part_font)
    draw.line((390, 1568, (CANVAS_SIZE[0] - part_width) / 2 - 34, 1568), fill=(*_GOLD, 255), width=3)
    draw.line(((CANVAS_SIZE[0] + part_width) / 2 + 34, 1568, 1466, 1568), fill=(*_GOLD, 255), width=3)
    draw.text(((CANVAS_SIZE[0] - part_width) / 2, 1525), part, font=part_font, fill=_GOLD)

    lines = _wrap_by_width(draw, content.candidate.author.upper(), title_font, 1580)
    if len(lines) > 3:
        title_font = _serif(104)
        lines = _wrap_by_width(draw, content.candidate.author.upper(), title_font, 1580)
    total = len(lines) * 145
    _center_lines(draw, lines, title_font, 1665 + max(0, (390 - total) // 2), fill=_GOLD, spacing=145)

    buf = BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _keyword_spans(text: str, terms: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for term in terms:
        pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I)
        spans.extend((match.start(), match.end()) for match in pattern.finditer(text))
    return spans


def _tokenize(text: str, terms: list[str]) -> list[tuple[str, bool]]:
    spans = _keyword_spans(text, terms)
    tokens: list[tuple[str, bool]] = []
    for match in re.finditer(r"\S+", text):
        highlighted = any(match.start() < end and match.end() > start for start, end in spans)
        tokens.append((match.group(0), highlighted))
    return tokens


def _wrap_tokens(
    draw: ImageDraw.ImageDraw,
    tokens: list[tuple[str, bool]],
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[list[tuple[str, bool, float]]]:
    space = draw.textlength(" ", font=font)
    lines: list[list[tuple[str, bool, float]]] = []
    current: list[tuple[str, bool, float]] = []
    used = 0.0
    for word, highlighted in tokens:
        width = draw.textlength(word, font=font)
        needed = width + (space if current else 0)
        if current and used + needed > max_width:
            lines.append(current)
            current = [(word, highlighted, width)]
            used = width
        else:
            current.append((word, highlighted, width))
            used += needed
    if current:
        lines.append(current)
    return lines


def _draw_justified(
    draw: ImageDraw.ImageDraw,
    lines: list[list[tuple[str, bool, float]]],
    *,
    x: int,
    y: int,
    width: int,
    line_height: int,
    font: ImageFont.FreeTypeFont,
) -> int:
    normal_space = draw.textlength(" ", font=font)
    for index, line in enumerate(lines):
        word_width = sum(item[2] for item in line)
        gaps = len(line) - 1
        # O exemplo fornecido usa alinhamento à esquerda, não espaços
        # artificialmente esticados entre as palavras.
        gap = normal_space
        cursor = float(x)
        for word, highlighted, measured in line:
            draw.text((cursor, y), word, font=font, fill=_HIGHLIGHT if highlighted else _INK)
            cursor += measured + gap
        y += line_height
    return y


def _paste_pdf_extract(canvas: Image.Image, excerpts: list[bytes], *, top: int) -> None:
    if not excerpts:
        raise BrandAssetError("recorte comprobatório da citação é obrigatório")
    target_h = min(520, CANVAS_SIZE[1] - top - 145)
    count = min(2, len(excerpts))
    target_w = 830 if count == 2 else 1760
    for index, payload in enumerate(excerpts[:count]):
        source = Image.open(BytesIO(payload)).convert("RGB")
        panel = Image.new("RGB", (target_w, target_h), "white")
        fitted = ImageOps.contain(source, (target_w, target_h), Image.Resampling.LANCZOS)
        panel.paste(fitted, ((target_w - fitted.width) // 2, (target_h - fitted.height) // 2))
        x = 48 if index == 0 else 914
        canvas.paste(panel, (x, top))


def render_citation_slide(content: CarouselContent) -> bytes:
    if not content.pdf_page_bytes:
        raise BrandAssetError("imagem da página-fonte é obrigatória")

    canvas = _open_fit(_PAGE_TEMPLATE)
    draw = ImageDraw.Draw(canvas)
    header_font = _body_font(56)
    body_font = _body_font(59)
    margin_x = 112
    content_width = CANVAS_SIZE[0] - 2 * margin_x

    header_lines = _wrap_by_width(draw, format_reference(content.candidate), header_font, content_width)
    y = 64
    for line in header_lines[:3]:
        draw.text((margin_x, y), line, font=header_font, fill=_REFERENCE_INK)
        y += 70
    y += 45

    tokens = _tokenize(content.candidate.quote, content.candidate.highlight_terms)
    lines = _wrap_tokens(draw, tokens, body_font, content_width)
    max_lines = 17
    if len(lines) > max_lines:
        raise BrandAssetError(
            f"citação exige {len(lines)} linhas; máximo visual aprovado é {max_lines}. "
            "O seletor deve escolher um trecho menor, sem truncar."
        )
    body_bottom = _draw_justified(
        draw,
        lines,
        x=margin_x,
        y=y,
        width=content_width,
        line_height=75,
        font=body_font,
    )
    scan_top = max(1545, body_bottom + 45)
    if scan_top > 1660:
        raise BrandAssetError("texto encostaria no recorte da fonte; publicação bloqueada")
    _paste_pdf_extract(canvas, content.pdf_excerpt_bytes or [], top=scan_top)

    buf = BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _texture_patch(size: tuple[int, int]) -> Image.Image:
    page = Image.open(_require_file(_PAGE_TEMPLATE, "página-base")).convert("RGB")
    patch = page.crop((360, 520, 1500, 1700))
    return ImageOps.fit(patch, size, Image.Resampling.LANCZOS)


def render_cta_slide(content: CarouselContent) -> bytes:
    if not content.portrait_bytes or not content.pdf_page_bytes:
        raise BrandAssetError("CTA exige retrato aprovado e página-fonte")
    canvas = _open_fit(_CTA_REFERENCE)
    draw = ImageDraw.Draw(canvas)

    # Mantém literalmente a moldura externa e o selo inferior do exemplo;
    # substitui somente os quatro blocos variáveis internos.
    canvas.paste(_texture_patch((1530, 190)), (163, 65))
    canvas.paste(_texture_patch((1510, 470)), (173, 274))
    canvas.paste(_texture_patch((1090, 1025)), (383, 770))
    canvas.paste(_texture_patch((1450, 315)), (203, 1835))
    draw = ImageDraw.Draw(canvas)

    header_font = _serif(48)
    header_lines = _wrap_by_width(draw, format_reference(content.candidate), header_font, 1500)
    y = 78
    for line in header_lines[:3]:
        width = draw.textlength(line, font=header_font)
        draw.text(((CANVAS_SIZE[0] - width) / 2, y), line, font=header_font, fill=(42, 25, 13))
        y += 60

    # O exemplo aprovado mostra a folha de rosto/identificação da edição na
    # arte final. A página da citação continua reservada ao slide central.
    page = Image.open(
        BytesIO(content.pdf_title_page_bytes or content.pdf_page_bytes)
    ).convert("RGB")
    source = Image.open(
        BytesIO((content.pdf_excerpt_bytes or [content.pdf_page_bytes])[0])
    ).convert("RGB")
    for index, image in enumerate((page, source)):
        panel = Image.new("RGB", (710, 420), "white")
        fitted = ImageOps.contain(image, (690, 400), Image.Resampling.LANCZOS)
        panel.paste(fitted, ((710 - fitted.width) // 2, (420 - fitted.height) // 2))
        canvas.paste(panel, (198 + index * 750, 296))
    draw.rectangle((190, 288, 1666, 724), outline=(82, 48, 19), width=7)

    portrait = Image.open(BytesIO(content.portrait_bytes)).convert("RGB")
    portrait = ImageOps.fit(portrait, (1000, 985), Image.Resampling.LANCZOS, centering=(0.5, 0.27))
    canvas.paste(portrait, (428, 790))
    draw.rectangle((418, 780, 1438, 1785), outline=(137, 91, 30), width=9)

    title_font = _serif(70)
    line_font = _serif(50, bold=True)
    lines = [
        ("Quer crescer na fé católica?", title_font),
        ("Siga @Vera.Fidei", line_font),
        ("YouTube: @mattcirineo", line_font),
        ('e entre no canal do WhatsApp “Vera.Fidei”!', _serif(42, bold=True)),
    ]
    y = 1848
    for line, font in lines:
        width = draw.textlength(line, font=font)
        draw.text(((CANVAS_SIZE[0] - width) / 2, y), line, font=font, fill=(40, 20, 10))
        y += 72

    buf = BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_carousel(content: CarouselContent) -> list[bytes]:
    return [
        render_cover_slide(content),
        render_citation_slide(content),
        render_cta_slide(content),
    ]
