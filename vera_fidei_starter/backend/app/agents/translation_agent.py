from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class TranslationAgent(BaseAgent):
    name = "translation_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        # STUB — Fase 1: valida arquitetura e contrato entre agentes.
        # Fase 2: substituir por comparação real entre original e tradução,
        # detectando perda de sentido, distorções ou versões infiéis.

        source = ctx.findings.get("source", {})
        original = source.get("located_excerpt", "")

        result = {
            "original_text": original,
            "translation_under_analysis": (
                "Não pode ter Deus por Pai quem não tem a Igreja por Mãe."
            ),
            "correspondence_level": "alta",
            "meaning_differences": [],
            "detected_problems": [],
            "fidelity_verdict": "tradução fiel no sentido principal",
        }

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=["Análise de tradução concluída."],
        )
