from __future__ import annotations

from app.agents.base import AgentResult, BaseAgent, PipelineContext
from app.social.ledger import SocialLedger
from app.social.package import create_launch_preview_package, create_preview_package
from core.config import settings


class SocialArtAgent(BaseAgent):
    name = "social_art_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        validation = ctx.findings.get("social_validation")
        if validation is None or not validation.ok:
            return AgentResult(self.name, "blocked", warnings=["consistência não aprovada"])
        options = ctx.findings.get("social_options") or {}
        if options.get("campaign_kind") == "launch":
            campaign = ctx.findings["social_launch_campaign"]
            package = create_launch_preview_package(
                campaign=campaign,
                caption=ctx.findings["social_caption"],
                execution_id=ctx.execution_id,
            )
            ctx.findings["social_package"] = package
            SocialLedger(settings.social_ledger_path).append(
                {
                    "event": "launch_preview_generated",
                    "source_fingerprint": campaign.fingerprint,
                    "campaign_id": campaign.campaign_id,
                    "package": str(package.resolve()),
                }
            )
            ctx.handoff(self.name, "social_approval_agent", {"campaign_kind": "launch", "package": str(package)})
            return AgentResult(
                self.name,
                "ok",
                data={
                    "campaign_kind": "launch",
                    "package": str(package.resolve()),
                    "slides": [str((package / f"slide_{i}.png").resolve()) for i in range(1, 4)],
                },
                notes=["três artes de lançamento geradas; nenhuma chamada externa realizada"],
            )
        package = create_preview_package(
            candidate=ctx.findings["social_candidate"],
            portrait_bytes=ctx.findings["social_portrait_bytes"],
            pdf_page_bytes=ctx.findings["social_pdf_page_bytes"],
            pdf_title_page_bytes=ctx.findings["social_pdf_title_page_bytes"],
            pdf_excerpt_bytes=ctx.findings["social_pdf_excerpt_bytes"],
            caption=ctx.findings["social_caption"],
            execution_id=ctx.execution_id,
        )
        ctx.findings["social_package"] = package
        SocialLedger(settings.social_ledger_path).append(
            {
                "event": "preview_generated",
                "source_fingerprint": ctx.findings["social_candidate"].source_fingerprint,
                "chunk_id": ctx.findings["social_candidate"].chunk_id,
                "package": str(package.resolve()),
            }
        )
        ctx.handoff(self.name, "social_approval_agent", {"package": str(package)})
        return AgentResult(
            self.name,
            "ok",
            data={
                "package": str(package.resolve()),
                "slides": [str((package / f"slide_{i}.png").resolve()) for i in range(1, 4)],
            },
            notes=["três artes geradas; nada enviado ao Instagram"],
        )
