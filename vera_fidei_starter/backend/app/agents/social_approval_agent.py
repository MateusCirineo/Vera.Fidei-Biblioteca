from __future__ import annotations

from app.agents.base import AgentResult, BaseAgent, PipelineContext
from app.social.package import style_is_approved


class SocialApprovalAgent(BaseAgent):
    name = "social_approval_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        package = ctx.findings.get("social_package")
        if package is None:
            return AgentResult(self.name, "blocked", warnings=["nenhuma prévia foi gerada"])
        approved = style_is_approved()
        ctx.findings["social_style_approved"] = approved
        if not approved:
            return AgentResult(
                self.name,
                "awaiting_approval",
                data={"package": str(package), "approved": False},
                notes=["aguardando o proprietário conferir capa, citação e CTA"],
            )
        ctx.handoff(self.name, "social_publish_agent", {"approved": True})
        return AgentResult(self.name, "ok", data={"approved": True})
