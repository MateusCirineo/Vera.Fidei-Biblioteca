from __future__ import annotations

import io
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib import colors

from models.database import VerificationHistory


_PLAN_ORDER = ["fiel", "catequista", "apologeta", "patristico", "magisterio"]


def generate_laudo_pdf(entry: VerificationHistory, user_plan: str = "catequista") -> bytes:
    has_apologeta = _PLAN_ORDER.index(user_plan) >= _PLAN_ORDER.index("apologeta")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "VFTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#C9A84C"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "VFSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#888888"),
        spaceAfter=12,
    )
    label_style = ParagraphStyle(
        "VFLabel",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#888888"),
        spaceBefore=8,
        spaceAfter=2,
    )
    value_style = ParagraphStyle(
        "VFValue",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#EEEEEE"),
        spaceAfter=4,
    )
    citation_style = ParagraphStyle(
        "VFCitation",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#CCCCCC"),
        leftIndent=12,
        borderPadding=(4, 8, 4, 8),
        spaceAfter=4,
        fontName="Times-Italic",
    )
    verdict_style = ParagraphStyle(
        "VFVerdict",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#C9A84C"),
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    footer_style = ParagraphStyle(
        "VFFooter",
        parent=styles["Normal"],
        fontSize=7,
        textColor=colors.HexColor("#555555"),
        alignment=1,  # center
    )

    now = datetime.datetime.utcnow().strftime("%d/%m/%Y às %H:%M UTC")
    date_str = (
        entry.created_at.strftime("%d/%m/%Y às %H:%M")
        if entry.created_at
        else now
    )

    story = [
        Paragraph("Vera.Fidei — Laudo de Verificação", title_style),
        Paragraph(f"Emitido em {now}", subtitle_style),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#333333")),
        Spacer(1, 0.3 * cm),

        Paragraph("CITAÇÃO ANALISADA", label_style),
        Paragraph(f'"{_safe(entry.citation_text)}"', citation_style),

        Paragraph("ATRIBUÍDA A", label_style),
        Paragraph(_safe(entry.attributed_to), value_style),

        Paragraph("DATA DA VERIFICAÇÃO", label_style),
        Paragraph(date_str, value_style),
    ]

    if entry.author:
        story += [
            Paragraph("AUTOR CANÔNICO LOCALIZADO", label_style),
            Paragraph(_safe(entry.author), value_style),
        ]

    if entry.work:
        story += [
            Paragraph("OBRA", label_style),
            Paragraph(_safe(entry.work), value_style),
        ]

    if entry.matched_excerpt:
        story += [
            Paragraph("TRECHO LOCALIZADO NA FONTE", label_style),
            Paragraph(f'"{_safe(entry.matched_excerpt)}"', citation_style),
        ]

    # Contexto patrístico e tradução — exclusivo Apologeta+
    if has_apologeta and entry.response_json:
        try:
            import json as _json
            resp = _json.loads(entry.response_json)
            ctx_before = resp.get("context_before")
            ctx_after = resp.get("context_after")
            translation = resp.get("matched_translation")
            fidelity = resp.get("translation_fidelity")
            translator = resp.get("translator") or resp.get("translation_edition")

            if ctx_before or ctx_after:
                story += [Paragraph("CONTEXTO PATRÍSTICO", label_style)]
                if ctx_before:
                    story += [Paragraph(f"[...] {_safe(ctx_before)}", citation_style)]
                story += [Paragraph(f'"{_safe(entry.matched_excerpt)}"', verdict_style)]
                if ctx_after:
                    story += [Paragraph(f"{_safe(ctx_after)} [...]", citation_style)]

            if translation:
                story += [
                    Paragraph("TRADUÇÃO DE REFERÊNCIA", label_style),
                    Paragraph(f'"{_safe(translation)}"', citation_style),
                ]
                if fidelity:
                    fidelity_label = "Tradução fiel" if fidelity == "fiel" else "Tradução imprecisa"
                    story += [Paragraph(f"Fidelidade: {fidelity_label}" + (f" — {_safe(translator)}" if translator else ""), value_style)]
        except Exception:
            pass

    story += [
        Spacer(1, 0.3 * cm),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#333333")),
        Spacer(1, 0.2 * cm),
        Paragraph("VEREDITO", label_style),
        Paragraph(_safe(entry.label) or _safe(entry.status_code), verdict_style),
    ]

    if entry.confidence:
        story += [
            Paragraph("NÍVEL DE CONFIANÇA", label_style),
            Paragraph(_safe(entry.confidence), value_style),
        ]

    if entry.explanation:
        story += [
            Paragraph("ANÁLISE", label_style),
            Paragraph(_safe(entry.explanation), value_style),
        ]

    story += [
        Spacer(1, 0.5 * cm),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#222222")),
        Spacer(1, 0.2 * cm),
        Paragraph(
            "Vera.Fidei Biblioteca · verafidei.app · Desenvolvido por Mateus Cirineo · "
            "Este laudo é gerado automaticamente e não substitui pesquisa acadêmica especializada.",
            footer_style,
        ),
    ]

    doc.build(story)
    return buffer.getvalue()


def _safe(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
