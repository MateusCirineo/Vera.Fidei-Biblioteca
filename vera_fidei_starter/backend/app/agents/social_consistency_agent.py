from __future__ import annotations

from app.agents.base import AgentResult, BaseAgent, PipelineContext
from app.social.content_guard import validate_candidate
from app.social.ledger import SocialLedger
from app.social.pdf_page_image import (
    render_pdf_page,
    render_pdf_quote_excerpts,
    render_pdf_title_page,
)
from app.social.saint_portrait import fetch_saint_portrait, portrait_is_approved
from app.social.promo_post import validate_launch_campaign
from core.config import settings


class SocialConsistencyAgent(BaseAgent):
    name = "social_consistency_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        options = ctx.findings.get("social_options") or {}
        if options.get("campaign_kind") == "launch":
            campaign = ctx.findings.get("social_launch_campaign")
            if campaign is None:
                return AgentResult(self.name, "blocked", warnings=["manifesto de lançamento ausente"])
            report = validate_launch_campaign(campaign)
            ctx.findings["social_validation"] = report
            if report.ok:
                ctx.handoff(self.name, "social_copy_agent", {"campaign_kind": "launch", "validated": True})
            return AgentResult(
                self.name,
                "ok" if report.ok else "blocked",
                data=report.to_dict(),
                warnings=report.errors + report.warnings,
                notes=["release, domínio, alegações, assets, hashes e cortes públicos conferidos"],
            )
        candidate = ctx.findings.get("social_candidate")
        if candidate is None:
            return AgentResult(self.name, "blocked", warnings=["agente de fonte não entregou candidato"])

        ledger = SocialLedger(settings.social_ledger_path)
        report = validate_candidate(
            candidate,
            expected_author=candidate.author,
            published_fingerprints=ledger.published_fingerprints(),
        )
        publishing = bool(options.get("publish_requested"))
        portrait = fetch_saint_portrait(
            candidate.author,
            allow_pending_local=not publishing,
        )
        if portrait is None:
            report.errors.append(
                f"não existe retrato aprovado para {candidate.author}; pesquisa pode continuar, publicação não"
            )
        elif not portrait_is_approved(candidate.author):
            report.warnings.append(
                f"retrato de {candidate.author} está visível apenas para revisão; publicação continua bloqueada"
            )
        source_page = None
        title_page = None
        excerpts: list[bytes] = []
        if candidate.book_file_id and candidate.pdf_page:
            source_page = render_pdf_page(candidate.book_file_id, candidate.pdf_page)
            title_page = render_pdf_title_page(
                candidate.book_file_id,
                author=candidate.author,
                work_title=candidate.work_title,
            )
            excerpts = render_pdf_quote_excerpts(
                candidate.book_file_id,
                candidate.pdf_page,
                candidate.quote,
            )
        if source_page is None:
            report.errors.append("não foi possível renderizar a página exata da fonte")
        if title_page is None:
            report.errors.append("não foi possível renderizar a folha de rosto da obra")
        if not excerpts:
            report.errors.append("não foi possível localizar a citação dentro da página-fonte")
        report.ok = not report.errors
        ctx.findings["social_validation"] = report
        if report.ok:
            ctx.findings["social_portrait_bytes"] = portrait
            ctx.findings["social_pdf_page_bytes"] = source_page
            ctx.findings["social_pdf_title_page_bytes"] = title_page
            ctx.findings["social_pdf_excerpt_bytes"] = excerpts
            ctx.handoff(self.name, "social_art_agent", {"validated": True})
        return AgentResult(
            self.name,
            "ok" if report.ok else "blocked",
            data=report.to_dict(),
            warnings=report.errors + report.warnings,
            notes=["nenhuma arte é gerada quando autor, retrato ou página-fonte divergem"],
        )
