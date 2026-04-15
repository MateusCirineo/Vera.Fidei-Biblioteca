from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class EditionAgent(BaseAgent):
    name = "edition_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        # STUB — Fase 1: valida arquitetura e contrato entre agentes.
        # Fase 2: substituir por consulta real às tabelas de edições
        # (PG, PL, Sources Chrétiennes, Corpus Christianorum, etc.).

        source = ctx.findings.get("source", {})

        result = {
            "work": source.get("candidate_work"),
            "considered_editions": [
                "Patrologia Latina",
                "edição crítica moderna",
            ],
            "adopted_edition": "Patrologia Latina (provisória)",
            "relevant_differences": [
                "Possíveis variações mínimas de pontuação.",
            ],
            "choice_reason": "Maior disponibilidade inicial para validação textual.",
            "risks": [
                "Necessidade de cruzar com edição crítica posterior.",
            ],
        }

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=["Edição base definida provisoriamente."],
        )
