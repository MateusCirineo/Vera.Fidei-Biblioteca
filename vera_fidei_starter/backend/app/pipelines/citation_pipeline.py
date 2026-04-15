from __future__ import annotations

from app.services.dispatcher import PipelineDispatcher


def run_citation_pipeline(task: str) -> dict:
    """
    Executa o pipeline completo de verificação de citação.

    Entrada única: a tarefa ou citação do usuário.
    Saída: relatório consolidado com todos os agentes executados.
    """
    dispatcher = PipelineDispatcher()
    ctx = dispatcher.run(task)

    final_report = {
        "execution_id": ctx.execution_id,
        "task": ctx.user_task,
        "mission": ctx.mission,
        "reports": ctx.reports,
        "handoffs": ctx.handoffs,
        "history": [
            {
                "agent": item.agent_name,
                "status": item.status,
                "notes": item.notes,
                "warnings": item.warnings,
            }
            for item in ctx.history
        ],
        "final_verdict": ctx.reports.get("safety_agent", {}).get("final_verdict", "não disponível"),
        "safety_level": ctx.reports.get("safety_agent", {}).get("safety_level", "não disponível"),
    }

    return final_report
