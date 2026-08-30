"""Prévia oficial do lançamento da PWA Vera.Fidei.

Esta campanha é promocional e não finge ser uma publicação patrística: não há
autor, citação, página ou ``chunk_id``. Mesmo assim, ela passa pela mesma cadeia
de agentes, usa os três assets visuais homologados e permanece bloqueada para
publicação até uma aprovação específica do proprietário.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.social.carousel import CANVAS_SIZE
from app.social.post_model import ValidationReport
from core.config import settings


_SOCIAL_DIR = Path(__file__).resolve().parent
_REPOSITORY_ROOT = _SOCIAL_DIR.parents[3]
_ASSETS = _SOCIAL_DIR / "assets"
_CAMPAIGN_MANIFEST = _ASSETS / "campaigns" / "pwa_launch_v1.3.2.json"
_LOGO_PATH = _ASSETS / "Logo-VF.png"
_PAGE_TEMPLATE = _ASSETS / "templates" / "page_with_logo.png"
_COVER_REFERENCE = _ASSETS / "references" / "cover_saint_ambrose.png"
_CTA_REFERENCE = _ASSETS / "references" / "cta_saint_ambrose.jpg"
_SCREENSHOTS_DIR = _ASSETS / "screenshots"
_PRESENTATION_ASSET_NAMES = (
    "presentation-primary-sources.webp",
    "presentation-tradition.webp",
    "presentation-verification.webp",
)
_PROOF_SCREENSHOT_PATH = _SCREENSHOTS_DIR / "citation-confirmed.png"

_NAVY = (2, 31, 49)
_GOLD = (202, 151, 58)
_LIGHT_GOLD = (239, 213, 148)
_INK = (35, 22, 13)
_MUTED_INK = (91, 66, 42)
_CREAM = (248, 238, 211)
_WHITE = (251, 248, 240)
KEYWORD_RGB = (102, 29, 20)


class LaunchCampaignError(RuntimeError):
    """Bloqueia a campanha quando texto, evidência ou asset diverge."""


@dataclass(frozen=True, slots=True)
class LaunchCampaign:
    payload: dict[str, Any]

    @property
    def campaign_id(self) -> str:
        return str(self.payload["campaign_id"])

    @property
    def release(self) -> str:
        return str(self.payload["release"])

    @property
    def domain(self) -> str:
        return str(self.payload["domain"])

    @property
    def fingerprint(self) -> str:
        serialized = json.dumps(self.payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return "launch:" + hashlib.sha256(serialized).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_evidence_path(relative: str) -> Path:
    return _REPOSITORY_ROOT / Path(relative)


def load_launch_campaign() -> LaunchCampaign:
    if not _CAMPAIGN_MANIFEST.is_file():
        raise LaunchCampaignError(f"manifesto de campanha ausente: {_CAMPAIGN_MANIFEST}")
    payload = json.loads(_CAMPAIGN_MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LaunchCampaignError("manifesto de campanha inválido")
    return LaunchCampaign(payload=payload)


def launch_style_files() -> tuple[Path, ...]:
    """Arquivos cujo conteúdo define esta composição promocional."""
    campaign = load_launch_campaign()
    screenshot_paths = tuple(
        _SCREENSHOTS_DIR / str(item["file"])
        for item in campaign.payload.get("screenshots") or []
    )
    feature_paths = tuple(
        _resolve_evidence_path(str(item["asset"]))
        for item in (campaign.payload.get("copy") or {}).get("features") or []
    )
    proof_item = campaign.payload.get("proof_screenshot") or {}
    proof_path = _SCREENSHOTS_DIR / str(proof_item.get("file") or "")
    return (
        _PAGE_TEMPLATE,
        _COVER_REFERENCE,
        _CTA_REFERENCE,
        _LOGO_PATH,
        Path(settings.social_body_font_path),
        Path(__file__),
        _CAMPAIGN_MANIFEST,
        *screenshot_paths,
        *feature_paths,
        proof_path,
    )


def _campaign_text(campaign: LaunchCampaign) -> str:
    copy = campaign.payload.get("copy") or {}
    caption = str(campaign.payload.get("caption") or "")
    return json.dumps(copy, ensure_ascii=False) + "\n" + caption


def validate_launch_campaign(campaign: LaunchCampaign) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    payload = campaign.payload

    if payload.get("schema_version") != 1 or payload.get("campaign_kind") != "launch":
        errors.append("manifesto não identifica uma campanha de lançamento suportada")
    if campaign.campaign_id != "pwa-launch-v1.3.2" or campaign.release != "1.3.2":
        errors.append("campanha não corresponde à release PWA 1.3.2")
    if campaign.domain != "verafidei.com.br":
        errors.append("domínio da campanha diverge do domínio canônico")

    text = _campaign_text(campaign).casefold()
    forbidden = [str(value).casefold() for value in payload.get("forbidden_claims") or []]
    forbidden.extend(("em breve", "ainda não é o lançamento", "estou preparando", "play store"))
    for claim in forbidden:
        if claim and claim in text:
            errors.append(f"alegação proibida na campanha: {claim}")

    evidence = payload.get("evidence") or []
    if not evidence:
        errors.append("campanha não registra evidências documentais")
    for item in evidence:
        path = _resolve_evidence_path(str(item.get("path") or ""))
        expected = str(item.get("contains") or "")
        if not path.is_file():
            errors.append(f"evidência ausente: {path}")
            continue
        if not expected or expected not in path.read_text(encoding="utf-8"):
            errors.append(f"evidência não confirmada em {path.name}: {expected}")

    screenshots = payload.get("screenshots") or []
    if len(screenshots) != 2:
        errors.append("campanha deve usar exatamente duas capturas reais e saneadas")
    for item in screenshots:
        path = _SCREENSHOTS_DIR / str(item.get("file") or "")
        expected_hash = str(item.get("sha256") or "")
        crop = item.get("public_crop") or []
        if not path.is_file():
            errors.append(f"captura ausente: {path}")
            continue
        if _sha256_file(path) != expected_hash:
            errors.append(f"captura alterada sem nova aprovação: {path.name}")
        try:
            with Image.open(path) as image:
                left, top, right, bottom = (int(value) for value in crop)
                if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
                    raise ValueError
                # A conta usada na captura fica no extremo direito. O corte é
                # obrigatório para que nome/avatar não entrem na arte pública.
                if right > 810:
                    errors.append(f"corte público não remove a área da conta: {path.name}")
        except (OSError, TypeError, ValueError):
            errors.append(f"corte público inválido: {path.name}")

    features = (payload.get("copy") or {}).get("features") or []
    if len(features) != 3:
        errors.append("a arte central deve apresentar exatamente três pilares")
    for index, item in enumerate(features):
        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or "").strip()
        path = _resolve_evidence_path(str(item.get("asset") or ""))
        expected_hash = str(item.get("sha256") or "").casefold()
        expected_name = (
            _PRESENTATION_ASSET_NAMES[index]
            if index < len(_PRESENTATION_ASSET_NAMES)
            else ""
        )
        if not title or not body:
            errors.append(f"pilar {index + 1} está sem título ou descrição")
        if path.name != expected_name:
            errors.append(f"asset visual divergente no pilar {index + 1}: {path.name}")
        if not path.is_file():
            errors.append(f"asset visual ausente: {path}")
        elif _sha256_file(path).casefold() != expected_hash:
            errors.append(f"asset visual alterado sem nova aprovação: {path.name}")

    proof_item = payload.get("proof_screenshot") or {}
    proof_path = _SCREENSHOTS_DIR / str(proof_item.get("file") or "")
    proof_crop = proof_item.get("public_crop") or []
    if proof_path != _PROOF_SCREENSHOT_PATH:
        errors.append("captura comprobatória diverge do artefato homologado")
    if not proof_path.is_file():
        errors.append(f"captura comprobatória ausente: {proof_path}")
    elif _sha256_file(proof_path).casefold() != str(proof_item.get("sha256") or "").casefold():
        errors.append("captura comprobatória foi alterada sem nova aprovação")
    else:
        try:
            with Image.open(proof_path) as image:
                left, top, right, bottom = (int(value) for value in proof_crop)
                if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
                    raise ValueError
                # O corte termina antes do rodapé do ambiente de teste, que
                # contém a identificação pessoal do proprietário.
                if bottom > 1300:
                    errors.append("corte comprobatório inclui área não pública")
        except (OSError, TypeError, ValueError):
            errors.append("corte da captura comprobatória é inválido")

    for required in (_COVER_REFERENCE, _PAGE_TEMPLATE, _CTA_REFERENCE, _LOGO_PATH):
        if not required.is_file():
            errors.append(f"asset homologado ausente: {required}")
    font = Path(settings.social_body_font_path)
    if font.name.upper() != "ARLRDBD.TTF" or not font.is_file():
        errors.append("fonte obrigatória Arial Rounded MT Bold não está disponível")

    return ValidationReport(ok=not errors, errors=errors, warnings=warnings)


def _require_file(path: Path, description: str) -> Path:
    if not path.is_file():
        raise LaunchCampaignError(f"{description} ausente: {path}")
    return path


def _open_fit(path: Path) -> Image.Image:
    return ImageOps.fit(
        Image.open(_require_file(path, "asset homologado")).convert("RGB"),
        CANVAS_SIZE,
        Image.Resampling.LANCZOS,
    )


def _serif(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/georgiab.ttf" if bold else "C:/Windows/Fonts/georgia.ttf"),
        Path("C:/Windows/Fonts/timesbd.ttf" if bold else "C:/Windows/Fonts/times.ttf"),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
        ),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    raise LaunchCampaignError("fonte serif homologada não encontrada")


def _body_font(size: int) -> ImageFont.FreeTypeFont:
    path = Path(settings.social_body_font_path)
    if path.name.upper() != "ARLRDBD.TTF":
        raise LaunchCampaignError("a fonte do corpo deve ser ARLRDBD.TTF")
    return ImageFont.truetype(str(_require_file(path, "fonte Arial Rounded MT Bold")), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and draw.textlength(trial, font=font) > width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def _centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    y: int,
    *,
    fill: tuple[int, int, int],
    width: int = 1600,
    spacing: int | None = None,
) -> int:
    lines = _wrap(draw, text, font, width)
    step = spacing or int(font.size * 1.2)
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        x = (CANVAS_SIZE[0] - (box[2] - box[0])) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += step
    return y


def _sanitized_screenshot(campaign: LaunchCampaign, index: int) -> Image.Image:
    item = (campaign.payload.get("screenshots") or [])[index]
    path = _SCREENSHOTS_DIR / str(item["file"])
    image = Image.open(_require_file(path, "captura da produção")).convert("RGB")
    crop = tuple(int(value) for value in item["public_crop"])
    return image.crop(crop)


def _rounded_paste(
    canvas: Image.Image,
    source: Image.Image,
    box: tuple[int, int, int, int],
    *,
    contain: bool,
    radius: int = 34,
) -> None:
    width, height = box[2] - box[0], box[3] - box[1]
    panel = Image.new("RGB", (width, height), (10, 14, 17))
    if contain:
        fitted = ImageOps.contain(source, (width - 24, height - 24), Image.Resampling.LANCZOS)
        panel.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
    else:
        fitted = ImageOps.fit(source, (width, height), Image.Resampling.LANCZOS, centering=(0.5, 0.45))
        panel.paste(fitted, (0, 0))
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
    canvas.paste(panel, (box[0], box[1]), mask)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, radius=radius, outline=_GOLD, width=7)


def _paste_logo(canvas: Image.Image, box: tuple[int, int, int, int]) -> None:
    logo = Image.open(_require_file(_LOGO_PATH, "logo oficial")).convert("RGBA")
    fitted = ImageOps.contain(logo, (box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
    canvas.paste(
        fitted,
        (box[0] + (box[2] - box[0] - fitted.width) // 2, box[1] + (box[3] - box[1] - fitted.height) // 2),
        fitted,
    )


def _proof_screenshot(campaign: LaunchCampaign) -> Image.Image:
    item = campaign.payload.get("proof_screenshot") or {}
    image = Image.open(
        _require_file(_SCREENSHOTS_DIR / str(item["file"]), "captura comprobatória")
    ).convert("RGB")
    crop = tuple(int(value) for value in item["public_crop"])
    return image.crop(crop)


def _presentation_asset(campaign: LaunchCampaign, index: int) -> Image.Image:
    feature = (campaign.payload.get("copy") or {}).get("features") or []
    if index >= len(feature):
        raise LaunchCampaignError(f"asset visual {index + 1} ausente na campanha")
    return _feature_asset(feature[index])


def _cinematic_frame(
    frame_path: Path,
    photograph: Image.Image,
    *,
    focus: tuple[float, float],
    inset: int = 34,
    navy_opacity: int = 104,
) -> Image.Image:
    """Preenche a moldura homologada com uma fotografia editorial escura."""
    canvas = _open_fit(frame_path)
    width, height = CANVAS_SIZE[0] - inset * 2, CANVAS_SIZE[1] - inset * 2
    fitted = ImageOps.fit(
        photograph,
        (width, height),
        Image.Resampling.LANCZOS,
        centering=focus,
    )
    canvas.paste(fitted, (inset, inset))

    overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(
        (inset, inset, CANVAS_SIZE[0] - inset, CANVAS_SIZE[1] - inset),
        fill=(*_NAVY, navy_opacity),
    )
    # A vinheta preserva a fotografia, mas mantém texto e mockups legíveis
    # mesmo quando a arte é vista na largura de um telefone.
    for y in range(inset, CANVAS_SIZE[1] - inset):
        normalized = (y - inset) / max(1, height)
        alpha = int(38 + 128 * max(0.0, (normalized - 0.44) / 0.56))
        draw.line(
            (inset, y, CANVAS_SIZE[0] - inset, y),
            fill=(0, 7, 12, alpha),
            width=1,
        )
    for x in range(inset, CANVAS_SIZE[0] - inset):
        normalized = (x - inset) / max(1, width)
        alpha = int(118 * max(0.0, (0.62 - normalized) / 0.62))
        draw.line(
            (x, inset, x, CANVAS_SIZE[1] - inset),
            fill=(0, 4, 8, alpha),
            width=1,
        )
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rectangle(
        (inset + 5, inset + 5, CANVAS_SIZE[0] - inset - 6, CANVAS_SIZE[1] - inset - 6),
        outline=(*_GOLD, 218),
        width=3,
    )
    return canvas


def _sequence_header(
    canvas: Image.Image,
    index: int,
    *,
    dark: bool,
    include_logo: bool = True,
) -> None:
    """Marca os três cards como capítulos de uma única sequência."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    text_color = _CREAM if dark else _INK
    line_color = (*_GOLD, 220) if dark else (130, 86, 35, 210)
    if include_logo:
        _paste_logo(canvas, (112, 48, 184, 120))
        draw = ImageDraw.Draw(canvas, "RGBA")
        draw.text((204, 62), "VERA.FIDEI", font=_serif(31, bold=True), fill=text_color)
    counter = f"0{index} / 03"
    counter_font = _body_font(29)
    counter_width = draw.textlength(counter, font=counter_font)
    draw.text((1740 - counter_width, 66), counter, font=counter_font, fill=text_color)
    draw.line((112, 143, 1744, 143), fill=line_color, width=2)


def _sequence_footer(canvas: Image.Image, *, dark: bool, final: bool = False) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    text_color = _GOLD if dark else KEYWORD_RGB
    line_color = (*_GOLD, 185) if dark else (130, 86, 35, 185)
    draw.line((112, 2192, 1432, 2192), fill=line_color, width=2)
    prompt = "VERAFIDEI.COM.BR" if final else "DESLIZE  >"
    font = _body_font(27)
    width = draw.textlength(prompt, font=font)
    draw.text((1744 - width, 2174), prompt, font=font, fill=text_color)


def _floating_screen(
    canvas: Image.Image,
    source: Image.Image,
    *,
    size: tuple[int, int],
    center: tuple[int, int],
    angle: float,
    focus: tuple[float, float] = (0.5, 0.5),
) -> None:
    """Insere uma tela real como cartão editorial, sem chrome de navegador."""
    width, height = size
    panel = Image.new("RGBA", size, (0, 0, 0, 0))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (8, 8, width - 9, height - 9),
        radius=44,
        fill=255,
    )
    fitted = ImageOps.fit(
        source,
        (width - 30, height - 30),
        Image.Resampling.LANCZOS,
        centering=focus,
    )
    interior = Image.new("RGBA", size, (5, 9, 12, 255))
    interior.paste(fitted, (15, 15))
    panel.paste(interior, (0, 0), mask)
    pdraw = ImageDraw.Draw(panel, "RGBA")
    pdraw.rounded_rectangle(
        (8, 8, width - 9, height - 9),
        radius=44,
        outline=(*_GOLD, 255),
        width=6,
    )
    rotated = panel.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)

    shadow = Image.new("RGBA", rotated.size, (0, 0, 0, 0))
    shadow.putalpha(rotated.getchannel("A").filter(ImageFilter.GaussianBlur(24)))
    shadow_color = Image.new("RGBA", rotated.size, (0, 0, 0, 170))
    shadow_color.putalpha(shadow.getchannel("A"))

    x = center[0] - rotated.width // 2
    y = center[1] - rotated.height // 2
    canvas.alpha_composite(shadow_color, (x + 24, y + 34))
    canvas.alpha_composite(rotated, (x, y))


def _proof_source_image(campaign: LaunchCampaign) -> Image.Image:
    item = campaign.payload.get("proof_screenshot") or {}
    return Image.open(
        _require_file(_SCREENSHOTS_DIR / str(item["file"]), "captura comprobatória")
    ).convert("RGB")


def _proof_crop(campaign: LaunchCampaign, box: tuple[int, int, int, int]) -> Image.Image:
    # As duas provas ficam estritamente dentro do recorte público homologado
    # [310, 800, 970, 1005], que termina antes da navegação inferior.
    safe = (310, 800, 970, 1005)
    if not (
        safe[0] <= box[0] < box[2] <= safe[2]
        and safe[1] <= box[1] < box[3] <= safe[3]
    ):
        raise LaunchCampaignError("recorte da prova ultrapassa a área pública segura")
    return _proof_source_image(campaign).crop(box)


def _apply_bottom_fade(canvas: Image.Image, *, start: int, opacity: int = 248) -> Image.Image:
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    fade_length = 280
    for y in range(start, CANVAS_SIZE[1] - 24):
        progress = min(1.0, max(0.0, (y - start) / fade_length))
        alpha = int(opacity * progress)
        draw.line((27, y, CANVAS_SIZE[0] - 28, y), fill=(*_NAVY, alpha), width=1)
    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


def _device_mockup(
    canvas: Image.Image,
    source: Image.Image,
    box: tuple[int, int, int, int],
    *,
    label: str,
) -> None:
    left, top, right, bottom = box
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle(
        (left + 18, top + 24, right + 18, bottom + 24),
        radius=48,
        fill=(0, 0, 0, 120),
    )
    draw.rounded_rectangle(
        box,
        radius=48,
        fill=(5, 9, 12, 255),
        outline=(*_GOLD, 255),
        width=7,
    )
    draw.line((left + 26, top + 82, right - 26, top + 82), fill=(*_GOLD, 150), width=2)
    for offset, color in enumerate(((143, 42, 34), (202, 151, 58), (64, 112, 78))):
        x = left + 42 + offset * 30
        draw.ellipse((x, top + 31, x + 15, top + 46), fill=(*color, 255))
    label_font = _body_font(30)
    label_width = draw.textlength(label, font=label_font)
    draw.text((right - label_width - 42, top + 23), label, font=label_font, fill=_LIGHT_GOLD)
    _rounded_paste(
        canvas,
        source,
        (left + 26, top + 105, right - 26, bottom - 34),
        contain=True,
        radius=24,
    )


def _feature_asset(feature: dict[str, Any]) -> Image.Image:
    path = _resolve_evidence_path(str(feature["asset"]))
    return Image.open(_require_file(path, "asset visual da apresentação")).convert("RGB")


def _feature_card(
    canvas: Image.Image,
    feature: dict[str, Any],
    *,
    index: int,
    top: int,
) -> None:
    left, right, height = 118, 1738, 505
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle(
        (left + 12, top + 16, right + 12, top + height + 16),
        radius=34,
        fill=(68, 40, 17, 44),
    )
    draw.rounded_rectangle(
        (left, top, right, top + height),
        radius=34,
        fill=(246, 231, 194, 238),
        outline=(137, 91, 36, 225),
        width=4,
    )
    _rounded_paste(
        canvas,
        _feature_asset(feature),
        (145, top + 25, 670, top + height - 25),
        contain=False,
        radius=25,
    )

    draw = ImageDraw.Draw(canvas, "RGBA")
    badge = f"0{index}"
    badge_font = _body_font(36)
    draw.ellipse((738, top + 62, 814, top + 138), fill=(*KEYWORD_RGB, 255))
    badge_width = draw.textlength(badge, font=badge_font)
    draw.text((776 - badge_width / 2, top + 77), badge, font=badge_font, fill=(250, 235, 196))

    title_font = _serif(58, bold=True)
    draw.text((846, top + 58), str(feature["title"]), font=title_font, fill=_INK)
    draw.line((846, top + 145, 1620, top + 145), fill=(150, 105, 50, 150), width=3)
    body_font = _body_font(43)
    y = top + 181
    for line in _wrap(draw, str(feature["body"]), body_font, 780):
        draw.text((846, y), line, font=body_font, fill=_MUTED_INK)
        y += 59


def render_cover_slide(campaign: LaunchCampaign) -> bytes:
    copy = campaign.payload["copy"]
    canvas = _cinematic_frame(
        _COVER_REFERENCE,
        _presentation_asset(campaign, 1),
        focus=(0.69, 0.49),
        navy_opacity=112,
    ).convert("RGBA")
    _sequence_header(canvas, 1, dark=True)
    draw = ImageDraw.Draw(canvas, "RGBA")

    eyebrow = f"{copy['cover_badge']}  —  {str(copy['cover_status']).upper()}"
    draw.text((126, 250), eyebrow, font=_body_font(34), fill=_GOLD)
    draw.line((126, 310, 650, 310), fill=(*_GOLD, 225), width=3)
    draw.text((120, 348), "VERA.FIDEI", font=_serif(142, bold=True), fill=_WHITE)
    draw.text(
        (128, 525),
        str(copy["cover_subtitle"]),
        font=_body_font(50),
        fill=_CREAM,
    )
    draw.text(
        (128, 596),
        (
            f"{copy['features'][0]['title']} e "
            f"{str(copy['features'][2]['title']).lower()}."
        ),
        font=_body_font(35),
        fill=(226, 213, 183),
    )

    # Duas telas reais, sobrepostas como páginas de um carrossel editorial.
    # Elas funcionam como prova secundária do produto e não disputam com o
    # título principal.
    _floating_screen(
        canvas,
        _sanitized_screenshot(campaign, 0),
        size=(1010, 930),
        center=(660, 1450),
        angle=-2.7,
        focus=(0.48, 0.48),
    )
    _floating_screen(
        canvas,
        _sanitized_screenshot(campaign, 1),
        size=(850, 790),
        center=(1270, 1570),
        angle=3.0,
        focus=(0.49, 0.50),
    )
    _sequence_footer(canvas, dark=True)

    buffer = BytesIO()
    canvas.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_feature_slide(campaign: LaunchCampaign) -> bytes:
    copy = campaign.payload["copy"]
    canvas = _open_fit(_PAGE_TEMPLATE)
    draw = ImageDraw.Draw(canvas)

    y = _centered_text(
        draw,
        str(copy["feature_heading"]),
        _serif(82, bold=True),
        78,
        fill=_INK,
        width=1580,
        spacing=98,
    )
    y = _centered_text(
        draw,
        str(copy["feature_lead"]),
        _body_font(46),
        y + 10,
        fill=KEYWORD_RGB,
        width=1480,
        spacing=60,
    )
    draw.line((220, y + 24, 1636, y + 24), fill=(134, 91, 41), width=4)

    for index, feature in enumerate(copy["features"], 1):
        _feature_card(canvas, feature, index=index, top=350 + (index - 1) * 548)
    # Os três cartões permanecem literais; só estes marcadores discretos
    # conectam visualmente o card central aos demais capítulos.
    draw = ImageDraw.Draw(canvas, "RGBA")
    counter = "02 / 03"
    counter_font = _body_font(24)
    counter_width = draw.textlength(counter, font=counter_font)
    draw.text((1740 - counter_width, 30), counter, font=counter_font, fill=KEYWORD_RGB)
    _sequence_footer(canvas, dark=False)
    buffer = BytesIO()
    canvas.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _texture_patch(size: tuple[int, int]) -> Image.Image:
    page = Image.open(_require_file(_PAGE_TEMPLATE, "página-base")).convert("RGB")
    patch = page.crop((125, 80, 1731, 2180))
    return ImageOps.fit(patch, size, Image.Resampling.LANCZOS)


def render_promo_cta_slide(campaign: LaunchCampaign) -> bytes:
    copy = campaign.payload["copy"]
    canvas = _cinematic_frame(
        _CTA_REFERENCE,
        _presentation_asset(campaign, 2),
        focus=(0.72, 0.48),
        navy_opacity=122,
    ).convert("RGBA")
    _sequence_header(canvas, 3, dark=True)
    draw = ImageDraw.Draw(canvas, "RGBA")

    verifier = copy["features"][2]
    draw.text(
        (126, 250),
        str(verifier["title"]).upper(),
        font=_body_font(34),
        fill=_GOLD,
    )
    draw.line((126, 310, 650, 310), fill=(*_GOLD, 225), width=3)
    headline = str(copy["cta_message"])
    headline = headline.replace(" com ", "\ncom ", 1).replace(" às fontes.", "\nàs fontes.")
    draw.multiline_text(
        (120, 352),
        headline,
        font=_serif(102, bold=True),
        fill=_WHITE,
        spacing=18,
    )
    body_font = _body_font(36)
    body_y = 760
    for line in _wrap(draw, str(verifier["body"]), body_font, 900):
        draw.text((128, body_y), line, font=body_font, fill=_CREAM)
        body_y += 51

    draw.text((128, 1040), "RESULTADO REAL", font=_body_font(30), fill=_GOLD)
    # O chip e a base da decisão são dois recortes independentes da mesma
    # captura real. Ambos terminam antes da barra de navegação do aplicativo.
    _floating_screen(
        canvas,
        _proof_crop(campaign, (310, 800, 700, 872)),
        size=(850, 166),
        center=(590, 1212),
        angle=-1.2,
    )
    _floating_screen(
        canvas,
        _proof_crop(campaign, (310, 845, 970, 980)),
        size=(1390, 310),
        center=(1010, 1445),
        angle=1.0,
    )

    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.text((128, 1812), str(copy["cta_button"]), font=_body_font(34), fill=_GOLD)
    draw.text((120, 1870), campaign.domain, font=_serif(82, bold=True), fill=_WHITE)
    draw.line((126, 1990, 970, 1990), fill=(*_GOLD, 225), width=3)
    _sequence_footer(canvas, dark=True, final=True)

    buffer = BytesIO()
    canvas.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_promo_carousel(campaign: LaunchCampaign | None = None) -> list[bytes]:
    campaign = campaign or load_launch_campaign()
    report = validate_launch_campaign(campaign)
    if not report.ok:
        raise LaunchCampaignError("; ".join(report.errors))
    slides = [
        render_cover_slide(campaign),
        render_feature_slide(campaign),
        render_promo_cta_slide(campaign),
    ]
    if len(slides) != 3:
        raise LaunchCampaignError("o contrato exige exatamente três artes")
    for index, payload in enumerate(slides, 1):
        with Image.open(BytesIO(payload)) as image:
            if image.size != CANVAS_SIZE:
                raise LaunchCampaignError(f"slide {index} não mede 1856 x 2304")
    return slides


def build_promo_caption(campaign: LaunchCampaign | None = None) -> str:
    campaign = campaign or load_launch_campaign()
    report = validate_launch_campaign(campaign)
    if not report.ok:
        raise LaunchCampaignError("; ".join(report.errors))
    return str(campaign.payload["caption"]).strip() + "\n"
