from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class OrchestratorAgent(BaseAgent):
    name = "orchestrator"

    def run(self, ctx: PipelineContext) -> AgentResult:
        task = ctx.user_task.lower()

        if any(kw in task for kw in ("pdf", "upload", "upar", "ingest", "ingerir", "importar", "patrologia", "pg", "pl")):
            mission = self._pdf_ingestion_mission(ctx)
        elif any(
            kw in task
            for kw in (
                "cita",
                "atribu",
                "disse",
                "escreveu",
            )
        ):
            mission = self._citation_mission(ctx)
        else:
            mission = {
                "task": ctx.user_task,
                "objective": "Executar tarefa geral do Vera.Fidei.",
                "scope": ["analisar tarefa", "planejar", "executar agentes tecnicos"],
                "agents": ["planner"],
                "execution_order": ["planner"],
                "dependencies": {},
                "risks": ["escopo ambiguo"],
                "done_definition": ["planejamento concluido"],
                "execution_id": ctx.execution_id,
            }

        ctx.mission = mission
        ctx.progress = {
            "completed": ["orchestrator"],
            "in_progress": [],
            "pending": list(mission["execution_order"]),
            "blockers": [],
            "next_steps": mission["execution_order"][:2],
        }

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=mission,
            notes=["Missao criada com sucesso.", f"execution_id: {ctx.execution_id}"],
        )

    def _pdf_ingestion_mission(self, ctx: PipelineContext) -> dict:
        return {
            "task": ctx.user_task,
            "objective": "Importar PDFs patristicos para a biblioteca, validar extracao, indexar busca textual e busca semantica.",
            "scope": [
                "inventariar PDFs de entrada",
                "classificar colecao e tradicao",
                "extrair texto ou executar OCR quando necessario",
                "criar registros de livro, arquivo e chunks",
                "indexar Elasticsearch",
                "indexar embeddings no Chroma delta",
                "validar contagens e status final",
            ],
            "out_of_scope": [
                "sobrescrever registros ja concluidos sem verificacao",
                "gravar na colecao Chroma legada instavel",
                "rodar OCR paralelo agressivo sem controle de carga",
            ],
            "agents": [
                "planner",
                "pdf_ingestion_agent",
                "ingestion_validation_agent",
            ],
            "execution_order": [
                "planner",
                "pdf_ingestion_agent",
                "ingestion_validation_agent",
            ],
            "dependencies": {
                "pdf_ingestion_agent": ["planner"],
                "ingestion_validation_agent": ["pdf_ingestion_agent"],
            },
            "risks": [
                "PDF escaneado exigir OCR demorado",
                "PDF com texto digital parcial precisar fallback",
                "metadados de volume Migne ficarem genericos ate curadoria fina",
                "interrupcao durante embeddings ou OCR",
            ],
            "done_definition": [
                "todos os PDFs-alvo com arquivo nao zerado",
                "livros e BookFiles criados ou reutilizados",
                "chunks no banco maiores que zero",
                "Elasticsearch e Chroma delta com contagens compativeis",
                "status done ou erro acionavel por volume",
            ],
            "execution_id": ctx.execution_id,
        }

    def _citation_mission(self, ctx: PipelineContext) -> dict:
        return {
            "task": ctx.user_task,
            "objective": "Verificar autenticidade, fonte, idioma, edicao, traducao e contexto da citacao.",
            "scope": [
                "localizar fonte",
                "identificar autor e obra",
                "identificar idioma e edicao",
                "comparar texto",
                "avaliar traducao",
                "avaliar contexto",
                "emitir veredito prudencial",
            ],
            "out_of_scope": [
                "afirmacao dogmatica sem fonte",
                "validacao com evidencia fraca",
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
                "parafrase tratada como citacao literal",
                "mistura entre edicoes",
                "traducao distorcida",
                "uso fora de contexto",
            ],
            "done_definition": [
                "fonte localizada ou ausencia justificada",
                "idioma identificado com grau de certeza",
                "edicao indicada",
                "classificacao da citacao emitida",
                "contexto analisado",
                "veredito final prudencial",
            ],
            "execution_id": ctx.execution_id,
        }
