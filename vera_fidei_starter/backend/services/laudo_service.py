from __future__ import annotations

import datetime
import io
import json
import os
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.plans import has_min_plan
from models.database import VerificationHistory

BR_TZ = ZoneInfo("America/Sao_Paulo")
LOGO_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "Imagens para frontend", "Logo-VF.png")
)
MAX_QUOTE_CHARS = 950
MAX_EXCERPT_CHARS = 1100
MAX_CONTEXT_CHARS = 620
MAX_TRANSLATION_CHARS = 950


def generate_laudo_pdf(entry: VerificationHistory, user_plan: str = "catequista") -> bytes:
    has_apologeta = has_min_plan(user_plan, "apologeta")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.2 * cm,
    )

    styles = getSampleStyleSheet()
    brand_style = ParagraphStyle(
        "VFBrand",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#1A1A1A"),
    )
    brand_subtitle_style = ParagraphStyle(
        "VFBrandSubtitle",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#8B6F1F"),
    )
    title_style = ParagraphStyle(
        "VFTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1A1A1A"),
        spaceBefore=10,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "VFSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#6B7280"),
        spaceAfter=12,
    )
    label_style = ParagraphStyle(
        "VFLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#8B6F1F"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    value_style = ParagraphStyle(
        "VFValue",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=4,
    )
    citation_style = ParagraphStyle(
        "VFCitation",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=13,
        textColor=colors.HexColor("#111827"),
        spaceBefore=0,
        spaceAfter=0,
    )
    citation_italic_style = ParagraphStyle(
        "VFCitationItalic",
        parent=citation_style,
        fontName="Times-Italic",
        fontSize=10,
        leading=14,
    )
    verdict_style = ParagraphStyle(
        "VFVerdict",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#8B6F1F"),
        spaceAfter=4,
    )
    muted_style = ParagraphStyle(
        "VFMuted",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#6B7280"),
        spaceAfter=5,
    )
    footer_style = ParagraphStyle(
        "VFFooter",
        parent=styles["Normal"],
        fontSize=7,
        leading=10,
        textColor=colors.HexColor("#6B7280"),
        alignment=1,
    )

    emitted_at = _format_br_datetime(_now_br())
    verified_at = _format_br_datetime(_to_br_datetime(entry.created_at)) if entry.created_at else emitted_at
    reference_html = _reference_html(entry.reference_json)

    story = [
        _header_table(brand_style, brand_subtitle_style),
        Paragraph("Laudo de Verifica&ccedil;&atilde;o", title_style),
        Paragraph(f"Emitido em {emitted_at}", subtitle_style),
        HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#D9C46A")),
        Spacer(1, 0.2 * cm),
        Paragraph("CITA&Ccedil;&Atilde;O ANALISADA", label_style),
        _quote_box(f'"{_safe(_trim_middle(entry.citation_text, MAX_QUOTE_CHARS))}"', citation_italic_style),
        Paragraph("ATRIBU&Iacute;DA A", label_style),
        Paragraph(_safe(entry.attributed_to), value_style),
        Paragraph("DATA DA VERIFICA&Ccedil;&Atilde;O", label_style),
        Paragraph(verified_at, value_style),
    ]

    if entry.author:
        story += [
            Paragraph("AUTOR CAN&Ocirc;NICO LOCALIZADO", label_style),
            Paragraph(_safe(entry.author), value_style),
        ]

    if entry.work:
        story += [
            Paragraph("OBRA", label_style),
            Paragraph(_safe(entry.work), value_style),
        ]

    if reference_html:
        story += [
            Paragraph("REFER&Ecirc;NCIA DA FONTE", label_style),
            Paragraph(reference_html, value_style),
        ]

    if entry.matched_excerpt:
        story += [
            Paragraph("TRECHO LOCALIZADO NA FONTE", label_style),
            _quote_box(f'"{_safe(_trim_middle(entry.matched_excerpt, MAX_EXCERPT_CHARS))}"', citation_style),
        ]

    if has_apologeta and entry.response_json:
        try:
            resp = json.loads(entry.response_json)
            ctx_before = resp.get("context_before")
            ctx_after = resp.get("context_after")
            translation = resp.get("matched_translation")
            fidelity = resp.get("translation_fidelity")
            translator = resp.get("translator") or resp.get("translation_edition")
            variant_analysis = resp.get("variant_analysis")

            if ctx_before or ctx_after:
                story += [Paragraph("CONTEXTO PATR&Iacute;STICO", label_style)]
                if ctx_before:
                    story += [
                        Paragraph("Antes do trecho localizado", muted_style),
                        _quote_box(f"[...] {_safe(_tail(ctx_before, MAX_CONTEXT_CHARS))}", citation_style),
                    ]
                if entry.matched_excerpt:
                    story += [
                        Paragraph("Trecho central", muted_style),
                        _quote_box(f'"{_safe(_trim_middle(entry.matched_excerpt, MAX_EXCERPT_CHARS))}"', citation_style),
                    ]
                if ctx_after:
                    story += [
                        Paragraph("Depois do trecho localizado", muted_style),
                        _quote_box(f"{_safe(_head(ctx_after, MAX_CONTEXT_CHARS))} [...]", citation_style),
                    ]

            if translation:
                story += [
                    Paragraph("TRADU&Ccedil;&Atilde;O DE REFER&Ecirc;NCIA", label_style),
                    _quote_box(f'"{_safe(_trim_middle(translation, MAX_TRANSLATION_CHARS))}"', citation_style),
                ]
                if fidelity:
                    fidelity_label = (
                        "Tradu&ccedil;&atilde;o fiel"
                        if fidelity == "fiel"
                        else "Tradu&ccedil;&atilde;o imprecisa"
                    )
                    suffix = f" - {_safe(translator)}" if translator else ""
                    story += [Paragraph(f"Fidelidade: {fidelity_label}{suffix}", value_style)]

            if variant_analysis:
                story += [
                    Paragraph("AN&Aacute;LISE DE VARIA&Ccedil;&Atilde;O TEXTUAL", label_style),
                    Paragraph(_safe(variant_analysis), value_style),
                ]
        except Exception:
            pass

    story += [
        Spacer(1, 0.2 * cm),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D1D5DB")),
        Spacer(1, 0.2 * cm),
        Paragraph("VEREDITO", label_style),
        _verdict_box(_safe(entry.label) or _safe(entry.status_code), verdict_style),
    ]

    if entry.confidence:
        story += [
            Paragraph("N&Iacute;VEL DE CONFIAN&Ccedil;A", label_style),
            Paragraph(_safe(entry.confidence), value_style),
        ]

    if entry.explanation:
        story += [
            Paragraph("AN&Aacute;LISE", label_style),
            Paragraph(_safe(entry.explanation), value_style),
        ]

    story += [
        Spacer(1, 0.5 * cm),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")),
        Spacer(1, 0.2 * cm),
        Paragraph(
            "Vera.Fidei Biblioteca - verafidei.app - Desenvolvido por Mateus Cirineo - "
            "Este laudo &eacute; gerado automaticamente e n&atilde;o substitui pesquisa academica especializada.",
            footer_style,
        ),
    ]

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buffer.getvalue()


def _header_table(brand_style: ParagraphStyle, subtitle_style: ParagraphStyle) -> Table:
    brand = [
        Paragraph("Vera.Fidei", brand_style),
        Paragraph("Biblioteca Cat&oacute;lica Digital", subtitle_style),
    ]
    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=1.35 * cm, height=1.35 * cm, kind="proportional")
        data = [[logo, brand]]
        col_widths = [1.55 * cm, 14.2 * cm]
    else:
        data = [[brand]]
        col_widths = [15.75 * cm]

    table = Table(data, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _quote_box(text: str, style: ParagraphStyle) -> Table:
    table = Table([[Paragraph(text, style)]], colWidths=[15.75 * cm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBF7EA")),
        ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#D9C46A")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _verdict_box(text: str, style: ParagraphStyle) -> Table:
    table = Table([[Paragraph(text, style)]], colWidths=[15.75 * cm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6E7B0")),
        ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#B9952E")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _safe(value: str | None) -> str:
    if not value:
        return "-"
    return _compact(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _compact(value: str) -> str:
    return " ".join(str(value).split())


def _trim_middle(value: str | None, limit: int) -> str:
    text = _compact(value or "")
    if len(text) <= limit:
        return text
    side = max(80, (limit - 7) // 2)
    return f"{text[:side].rstrip()} [...] {text[-side:].lstrip()}"


def _head(value: str | None, limit: int) -> str:
    text = _compact(value or "")
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _tail(value: str | None, limit: int) -> str:
    text = _compact(value or "")
    if len(text) <= limit:
        return text
    return f"...{text[-limit:].lstrip()}"


def _now_br() -> datetime.datetime:
    return datetime.datetime.now(BR_TZ)


def _to_br_datetime(value: datetime.datetime | None) -> datetime.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(BR_TZ)


def _format_br_datetime(value: datetime.datetime) -> str:
    return value.strftime("%d/%m/%Y &agrave;s %H:%M") + " (hor&aacute;rio de Bras&iacute;lia)"


def _reference_html(reference_json: str | None) -> str:
    if not reference_json:
        return ""
    try:
        ref = json.loads(reference_json)
    except Exception:
        return ""

    parts: list[str] = []
    edition = ref.get("edition_label")
    source = ref.get("source_label")
    page = ref.get("pdf_page")
    section = ref.get("chapter_or_section")
    editor = ref.get("editor")
    translator = ref.get("translator")

    if edition:
        parts.append(f"Edi&ccedil;&atilde;o: {_safe(edition)}")
    if source:
        parts.append(f"Fonte: {_safe(source)}")
    if page:
        parts.append(f"P&aacute;gina do PDF: {_safe(str(page))}")
    if section:
        parts.append(f"Se&ccedil;&atilde;o: {_safe(section)}")
    if editor:
        parts.append(f"Editor: {_safe(editor)}")
    if translator:
        parts.append(f"Tradutor: {_safe(translator)}")

    return "<br/>".join(parts)


def _draw_footer(canvas: Canvas, doc: SimpleDocTemplate) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
    canvas.setLineWidth(0.4)
    canvas.line(doc.leftMargin, 1.55 * cm, A4[0] - doc.rightMargin, 1.55 * cm)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(doc.leftMargin, 1.2 * cm, "Vera.Fidei Biblioteca")
    canvas.drawRightString(A4[0] - doc.rightMargin, 1.2 * cm, f"Pagina {doc.page}")
    canvas.restoreState()
