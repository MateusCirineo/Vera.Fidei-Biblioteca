from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class OrchestratorAgent(BaseAgent):
    name = "orchestrator"

    def run(self, ctx: PipelineContext) -> AgentResult:
        task = ctx.user_task.lower()

        if any(kw in task for kw in ("citação", "citar", "atribuída", "atribuido", "disse", "escreveu")):
            mission = {
                "task": ctx.user_task,
                "objective": "Verificar autenticidade, fonte, idioma, edição, tradução e contexto da citação.",
                "scope": [
                    "localizar fonte",
                    "identificar autor e obra",
                    "identificar idioma e edição",
                    "comparar texto",
                    "avaliar tradução",
                    "avaliar contexto",
                    "emitir veredito prudencial",
                ],
                "out_of_scope": [
                    "afirmação dogmática sem fonte",
                    "validação com evidência fraca",
                ],
                "agents": [
                    "planner",
                    "source_finder",
                    "language_agent",
                    "edition_agent",
                    "citation_verifier",
                    "translation_agent",
                    "context_agent",
                    "consistency_agent",
                    "safety_agent",
                ],
                "execution_order": [
                    "planner",
                    "search_agent",
                    "source_finder",
                    "language_agent",
                    "edition_agent",
                    "citation_verifier",
                    "translation_agent",
                    "context_agent",
                    "consistency_agent",
                    "safety_agent",
                ],
                "dependencies": {
                    "search_agent": ["planner"],
                    "source_finder": ["search_agent"],
                    "language_agent": ["source_finder"],
                    "edition_agent": ["source_finder"],
                    "citation_verifier": ["source_finder", "language_agent", "edition_agent"],
                    "translation_agent": ["citation_verifier", "language_agent"],
                    "context_agent": ["citation_verifier"],
                    "consistency_agent": [
                        "source_finder",
                        "language_agent",
                        "edition_agent",
                        "citation_verifier",
                        "translation_agent",
                        "context_agent",
                    ],
                    "safety_agent": ["consistency_agent"],
                },
                "risks": [
                    "paráfrase tratada como citação literal",
                    "mistura entre edições",
                    "tradução distorcida",
                    "uso fora de contexto",
                ],
                "done_definition": [
                    "fonte localizada ou ausência justificada",
                    "idioma identificado com grau de certeza",
                    "edição indicada",
                    "classificação da citação emitida",
                    "contexto analisado",
                    "veredito final prudencial",
                ],
                "execution_id": ctx.execution_id,
            }
        else:
            mission = {
                "task": ctx.user_task,
                "objective": "Executar tarefa geral do Vera.Fidei.",
                "scope": ["analisar tarefa", "planejar", "executar agentes técnicos"],
                "agents": ["planner"],
                "execution_order": ["planner"],
                "dependencies": {},
                "risks": ["escopo ambíguo"],
                "done_definition": ["planejamento concluído"],
                "execution_id": ctx.execution_id,
            }

        ctx.mission = mission
        ctx.progress = {
            "completed": ["orchestrator"],
            "in_progress": [],
            "pending": list(mission["execution_order"]),  # cópia — não o mesmo objeto
            "blockers": [],
            "next_steps": mission["execution_order"][:2],
        }

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=mission,
            notes=["Missão criada com sucesso.", f"execution_id: {ctx.execution_id}"],
        )
