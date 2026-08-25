"""Carrossel de divulgação do app Vera.Fidei (funcionalidades + telas reais).

Separado de propósito do pipeline de citações patrísticas (carousel.py): usa
seus próprios templates simples, sem tocar nos assets/regras aprovados pro
conteúdo de citações.

Todo o texto de marca vem literalmente de
docs/vera-fidei/09-lancamento-e-comunicacao.md — nada é inventado aqui. O
projeto ainda não lançou publicamente, então o CTA é de pré-lançamento
("acompanhe", "em breve"), nunca "baixe agora". Troque PROMO_CTA_LINES
quando o app for lançado.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

CANVAS_SIZE = (1080, 1350)

_ASSETS = Path(__file__).resolve().parent / "assets"
_LOGO_PATH = _ASSETS / "Logo-VF.png"
_SCREENSHOTS_DIR = _ASSETS / "screenshots"

_BG_COLOR = (13, 13, 20)
_TEXT_COLOR = (240, 235, 220)
_ACCENT_COLOR = (198, 161, 91)
_SUBTLE_COLOR = (150, 148, 145)

_FONT_SERIF = ["C:/Windows/Fonts/georgia.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
_FONT_SERIF_BOLD = ["C:/Windows/Fonts/georgiab.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"]
_FONT_SANS = ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]

# Texto de marca — copiado literalmente de docs/vera-fidei/09-lancamento-e-comunicacao.md
BRAND_TAGLINE = "Fontes, PDFs, orações e verificação de citações."
PRE_LAUNCH_BODY = (
    "Estou preparando o Vera.Fidei, uma biblioteca católica digital com obras, "
    "documentos, PDFs, favoritos e verificação de citações.\n\n"
    "A proposta é ajudar fiéis, catequistas, apologetas, pesquisadores e "
    "criadores de conteúdo a estudar a fé com mais fidelidade às fontes.\n\n"
    "Ainda não é o lançamento oficial, mas em breve quero abrir para os "
    "primeiros usuários."
)
PROMO_CTA_LINES = [
    "Acompanhe o lançamento do Vera.Fidei",
    "Biblioteca Católica Digital",
    "Fontes. Estudo. Rastreabilidade.",
]

# Frases proibidas pela política de comunicação do próprio projeto — nunca
# usar isso em texto gerado (ver docs/vera-fidei/09-lancamento-e-comunicacao.md).
FORBIDDEN_CLAIMS = (
    "a maior biblioteca católica do mundo",
    "verificação infalível",
    "nunca erra",
    "substitui pesquisa teológica",
)


@dataclass
class ScreenshotSlide:
    filename: str  # em app/social/assets/screenshots/
    headline: str
    caption: str


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _paste_logo(canvas: Image.Image, *, max_width: int = 170, margin: int = 45) -> None:
    logo = Image.open(_LOGO_PATH).convert("RGBA")
    ratio = max_width / logo.width
    logo = logo.resize((max_width, int(logo.height * ratio)), Image.LANCZOS)
    x = (canvas.width - logo.width) // 2
    canvas.paste(logo, (x, margin), logo)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, width=max(10, max_width // (font.size // 2))))
    return lines


def _draw_centered(draw: ImageDraw.ImageDraw, lines: list[str], font: ImageFont.FreeTypeFont, y: float, *, fill, line_height: float) -> float:
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((CANVAS_SIZE[0] - w) / 2, y), line, font=font, fill=fill)
        y += line_height
    return y


def render_cover_slide() -> bytes:
    """Slide 1: identidade da marca, sem alegação de funcionalidade específica."""
    canvas = Image.new("RGB", CANVAS_SIZE, _BG_COLOR)
    draw = ImageDraw.Draw(canvas)
    _paste_logo(canvas, max_width=220, margin=int(CANVAS_SIZE[1] * 0.18))

    name_font = _load_font(_FONT_SERIF_BOLD, 78)
    tagline_font = _load_font(_FONT_SANS, 32)

    y = CANVAS_SIZE[1] * 0.46
    w = draw.textlength("Vera.Fidei", font=name_font)
    draw.text(((CANVAS_SIZE[0] - w) / 2, y), "Vera.Fidei", font=name_font, fill=_TEXT_COLOR)
    y += 100

    tagline_lines = textwrap.wrap(BRAND_TAGLINE, width=34)
    _draw_centered(draw, tagline_lines, tagline_font, y, fill=_ACCENT_COLOR, line_height=44)

    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def render_screenshot_slide(slide: ScreenshotSlide) -> bytes:
    """Slide com uma tela real do app dentro de uma moldura, com título e legenda curta."""
    path = _SCREENSHOTS_DIR / slide.filename
    if not path.is_file():
        raise FileNotFoundError(f"screenshot não encontrado: {path}")

    canvas = Image.new("RGB", CANVAS_SIZE, _BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    headline_font = _load_font(_FONT_SERIF_BOLD, 46)
    caption_font = _load_font(_FONT_SANS, 28)

    y = 70.0
    headline_lines = textwrap.wrap(slide.headline, width=26)
    y = _draw_centered(draw, headline_lines, headline_font, y, fill=_TEXT_COLOR, line_height=56)
    y += 20

    # Moldura da captura de tela real, com borda e sombra sutil.
    screenshot = Image.open(path).convert("RGB")
    frame_w = CANVAS_SIZE[0] - 140
    frame_h = int(frame_w * screenshot.height / screenshot.width)
    max_frame_h = CANVAS_SIZE[1] - int(y) - 220
    if frame_h > max_frame_h:
        frame_h = max_frame_h
        frame_w = int(frame_h * screenshot.width / screenshot.height)
    fitted = screenshot.resize((frame_w, frame_h), Image.LANCZOS)
    fx = (CANVAS_SIZE[0] - frame_w) // 2
    fy = int(y) + 10
    draw.rectangle([fx - 6, fy - 6, fx + frame_w + 6, fy + frame_h + 6], outline=_ACCENT_COLOR, width=3)
    canvas.paste(fitted, (fx, fy))

    caption_y = fy + frame_h + 40
    caption_lines = textwrap.wrap(slide.caption, width=42)
    _draw_centered(draw, caption_lines, caption_font, caption_y, fill=_SUBTLE_COLOR, line_height=38)

    _paste_logo(canvas, max_width=90, margin=30)

    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def render_promo_cta_slide() -> bytes:
    """Slide final: CTA de pré-lançamento (texto aprovado, nunca 'baixe agora')."""
    canvas = Image.new("RGB", CANVAS_SIZE, _BG_COLOR)
    draw = ImageDraw.Draw(canvas)
    _paste_logo(canvas, max_width=170, margin=int(CANVAS_SIZE[1] * 0.22))

    title_font = _load_font(_FONT_SERIF_BOLD, 52)
    line_font = _load_font(_FONT_SANS, 32)

    y = CANVAS_SIZE[1] * 0.46
    title_lines = textwrap.wrap(PROMO_CTA_LINES[0], width=22)
    y = _draw_centered(draw, title_lines, title_font, y, fill=_TEXT_COLOR, line_height=62)
    y += 20
    for line in PROMO_CTA_LINES[1:]:
        w = draw.textlength(line, font=line_font)
        draw.text(((CANVAS_SIZE[0] - w) / 2, y), line, font=line_font, fill=_ACCENT_COLOR)
        y += 44

    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def build_promo_caption() -> str:
    """Legenda do post — texto de pré-lançamento aprovado, sem alterações."""
    lines = [
        PRE_LAUNCH_BODY,
        "",
        "#VeraFidei #BibliotecaCatolica #Patristica #FeCatolica #Apologetica",
    ]
    return "\n".join(lines)


DEFAULT_SCREENSHOT_SLIDES = [
    ScreenshotSlide(
        filename="biblioteca.png",
        headline="Uma biblioteca católica organizada",
        caption="Obras, documentos e edições catalogados para consulta — não apenas uma lista de arquivos.",
    ),
    ScreenshotSlide(
        filename="verificador.png",
        headline="Verifique citações patrísticas",
        caption="Confronte uma citação atribuída com o acervo indexado: fonte, edição, idioma e trecho próximo.",
    ),
    ScreenshotSlide(
        filename="santos.png",
        headline="Santo do dia",
        caption="Acompanhe o santoral católico com fontes hagiográficas consultadas.",
    ),
]


def render_promo_carousel(slides: list[ScreenshotSlide] | None = None) -> list[bytes]:
    slides = slides if slides is not None else DEFAULT_SCREENSHOT_SLIDES
    images = [render_cover_slide()]
    images.extend(render_screenshot_slide(slide) for slide in slides)
    images.append(render_promo_cta_slide())
    return images
