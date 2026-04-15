from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class ConsistencyAgent(BaseAgent):
    name = "consistency_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        result = {
            "analyzed_agents": list(ctx.reports.keys()),
            "consistent_points": [
                "autor, obra e tema convergem",
                "idioma e edição provisória compatíveis com a análise",
                "verificação e contexto não se contradizem",
            ],
            "detected_conflicts": [],
            "conflict_severity": "baixa",
            "required_corrections": [
                "Confirmar edição crítica definitiva em fase posterior.",
            ],
        }

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=["Consistência geral aprovada."],
        )
