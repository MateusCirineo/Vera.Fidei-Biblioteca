from __future__ import annotations

from app.agents.base import AgentResult, BaseAgent, PipelineContext
from app.social.daily_card import build_caption, format_reference
from app.social.promo_post import build_promo_caption


class SocialCopyAgent(BaseAgent):
    """Redige somente a partir dos metadados já validados no acervo."""

    name = "social_copy_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        validation = ctx.findings.get("social_validation")
        options = ctx.findings.get("social_options") or {}
        if options.get("campaign_kind") == "launch":
            campaign = ctx.findings.get("social_launch_campaign")
            if validation is None or not validation.ok or campaign is None:
                return AgentResult(self.name, "blocked", warnings=["campanha de lançamento ainda não validada"])
            caption = build_promo_caption(campaign)
            ctx.findings["social_caption"] = caption
            ctx.handoff(self.name, "social_art_agent", {"campaign_kind": "launch"})
            return AgentResult(
                self.name,
                "ok",
                data={"campaign_id": campaign.campaign_id, "caption_characters": len(caption)},
                notes=["legenda construída somente com a copy factual aprovada no manifesto"],
            )
        candidate = ctx.findings.get("social_candidate")
        if validation is None or not validation.ok or candidate is None:
            return AgentResult(self.name, "blocked", warnings=["fonte ainda não validada"])
        caption = build_caption(candidate)
        ctx.findings["social_caption"] = caption
        ctx.handoff(self.name, "social_art_agent", {"reference": format_reference(candidate)})
        return AgentResult(
            self.name,
            "ok",
            data={"reference": format_reference(candidate), "caption_characters": len(caption)},
            notes=["legenda criada sem inventar contexto, tradução ou referência"],
        )
