from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class LanguageAgent(BaseAgent):
    name = "language_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        # STUB — Fase 1: valida arquitetura e contrato entre agentes.
        # Fase 2: substituir por chamadas reais a utils/language.py
        # para detecção e normalização automática de idioma.

        source = ctx.findings.get("source", {})

        result = {
            "source_reference": source.get("reference"),
            "identified_language": source.get("language", "desconhecido"),
            "text_nature": "texto em língua original",
            "certainty": 0.95,
            "limitations": [],
            "relevant_variants": [],
        }

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=["Idioma identificado."],
        )
