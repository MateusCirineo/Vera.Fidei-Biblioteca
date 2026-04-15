from __future__ import annotations

from app.agents.base import PipelineContext
from app.services.agent_registry import get_agent_registry


class PipelineDispatcher:
    def __init__(self) -> None:
        self.registry = get_agent_registry()

    def run(self, task: str) -> PipelineContext:
        ctx = PipelineContext(user_task=task)

        # O orchestrator define a missão e a ordem de execução
        orchestrator = self.registry["orchestrator"]
        result = orchestrator.run(ctx)
        ctx.add_result(result)

        # Itera sobre uma cópia para evitar skip se algum agente mutar a lista durante execução
        for agent_name in list(ctx.mission.get("execution_order", [])):
            agent = self.registry.get(agent_name)
            if agent is None:
                continue
            result = agent.run(ctx)
            ctx.add_result(result)

        return ctx
