from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class PlannerAgent(BaseAgent):
    name = "planner"

    def run(self, ctx: PipelineContext) -> AgentResult:
        plan = {
            "central_objective": ctx.mission.get("objective"),
            "subtasks": ctx.mission.get("scope", []),
            "execution_order": ctx.mission.get("execution_order", []),
            "dependencies": ctx.mission.get("dependencies", {}),
            "risks": ctx.mission.get("risks", []),
            "done_definition": ctx.mission.get("done_definition", []),
        }

        ctx.progress["completed"].append("planner")
        if "planner" in ctx.progress["pending"]:
            ctx.progress["pending"].remove("planner")
        ctx.progress["next_steps"] = ctx.mission.get("execution_order", [])[1:3]

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=plan,
            notes=["Plano operacional gerado."],
        )
