from __future__ import annotations

from app.agents.base import AgentResult, BaseAgent, PipelineContext
from app.social.ledger import SocialLedger
from app.social.package import publish_package
from core.config import settings


class SocialPublishAgent(BaseAgent):
    name = "social_publish_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        options = ctx.findings.get("social_options") or {}
        if options.get("campaign_kind") == "launch":
            return AgentResult(
                self.name,
                "skipped",
                notes=["campanha de lançamento gerada somente como prévia; upload e Graph API bloqueados"],
            )
        if not options.get("publish_requested"):
            return AgentResult(
                self.name,
                "skipped",
                notes=["execução em modo prévia; nenhum POST foi feito na API do Instagram"],
            )
        if not ctx.findings.get("social_style_approved"):
            return AgentResult(self.name, "blocked", warnings=["estilo ainda não aprovado"])
        package = ctx.findings.get("social_package")
        if package is None:
            return AgentResult(self.name, "blocked", warnings=["pacote de publicação ausente"])
        try:
            media_id = publish_package(package, SocialLedger(settings.social_ledger_path))
        except Exception as exc:
            return AgentResult(self.name, "blocked", warnings=[str(exc)])
        return AgentResult(
            self.name,
            "ok",
            data={"remote_media_id": media_id},
            notes=["carrossel publicado pela API oficial e registrado no ledger"],
        )
