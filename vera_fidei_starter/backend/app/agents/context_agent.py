from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class ContextAgent(BaseAgent):
    name = "context_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        # STUB — Fase 1: valida arquitetura e contrato entre agentes.
        # Fase 2: substituir por recuperação real dos trechos adjacentes
        # via busca no corpus (chunks anteriores e posteriores ao localizado).

        result = {
            "central_excerpt": (
                "Habere iam non potest Deum patrem qui ecclesiam non habet matrem."
            ),
            "previous_context": (
                "O autor discute a unidade da Igreja e a impossibilidade de "
                "salvação fora da comunhão eclesial."
            ),
            "next_context": (
                "O argumento continua reforçando a indivisibilidade da Igreja de Cristo."
            ),
            "local_theme": "unidade da Igreja",
            "is_usage_contextually_correct": True,
            "out_of_context_risk": "baixo",
            "observations": [
                "A frase é frequentemente usada de forma isolada, mas o sentido "
                "geral condiz com a temática do trecho.",
            ],
        }

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=["Contexto recuperado e analisado."],
        )
