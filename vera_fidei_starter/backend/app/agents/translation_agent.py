from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class TranslationAgent(BaseAgent):
    """Fail closed until translations have their own source ledger.

    Legacy translation rows predate page-level provenance. They can remain in
    the private search index to locate possible sources, but an agent must not
    quote, rate, or label them as faithful writing without an independently
    verified edition and page.
    """

    name = "translation_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        source = ctx.findings.get("source", {})
        original_text = source.get("located_excerpt", "")

        if source.get("status") == "not_found" or not source.get("chunk_id"):
            verdict = "análise não aplicável: fonte não localizada"
            note = "Fonte não localizada; análise de tradução não aplicável."
        else:
            verdict = "tradução omitida: edição e página ainda não verificadas"
            note = "Tradução legada omitida até conferência independente de edição e página."

        result = {
            "translation_found": False,
            "original_text": original_text[:350] if original_text else None,
            "translation_text": None,
            "translation_language": None,
            "translator": None,
            "edition_label": None,
            "fidelity_verdict": verdict,
            "detected_problems": (
                []
                if source.get("status") == "not_found"
                else ["A tradução legada não possui comprovação independente de redação literal."]
            ),
        }
        ctx.findings["translation"] = result
        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=[note],
        )
