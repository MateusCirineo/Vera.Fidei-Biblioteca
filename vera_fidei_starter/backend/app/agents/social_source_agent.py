from __future__ import annotations

from app.agents.base import AgentResult, BaseAgent, PipelineContext
from app.social.daily_card import pick_daily_card
from app.social.ledger import SocialLedger
from core.config import settings


class SocialSourceAgent(BaseAgent):
    name = "social_source_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        options = ctx.findings.get("social_options") or {}
        ledger = SocialLedger(settings.social_ledger_path)
        candidate = options.get("candidate") or pick_daily_card(
            day=options.get("day"),
            author=options.get("author"),
            ledger=ledger,
        )
        if candidate is None:
            return AgentResult(
                agent_name=self.name,
                status="error",
                warnings=["nenhuma fonte portuguesa, íntegra e ainda não publicada foi localizada"],
            )
        ctx.findings["social_candidate"] = candidate
        ctx.handoff(self.name, "social_consistency_agent", {"chunk_id": candidate.chunk_id})
        return AgentResult(
            agent_name=self.name,
            status="ok",
            data={
                "chunk_id": candidate.chunk_id,
                "book_id": candidate.book_id,
                "author": candidate.author,
                "work_title": candidate.work_title,
                "source_fingerprint": candidate.source_fingerprint,
            },
            notes=["autor, obra, citação e página reconstruídos do mesmo chunk"],
        )
