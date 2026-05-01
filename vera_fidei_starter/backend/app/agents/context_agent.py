from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


def _context_risk(prev_text: str | None, next_text: str | None, chunk_text: str) -> str:
    """Rough estimate of out-of-context risk based on surrounding text."""
    if prev_text is None and next_text is None:
        return "indeterminado — sem trechos adjacentes disponíveis"

    surrounding = " ".join(filter(None, [prev_text, next_text])).lower()
    negative_markers = ("não", "nunca", "falso", "heresia", "errado", "erroneamente")
    if any(m in surrounding for m in negative_markers):
        return "alto — contexto adjacente contém negações ou contraposições"

    return "baixo"


class ContextAgent(BaseAgent):
    name = "context_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        source = ctx.findings.get("source", {})
        chunk_id = source.get("chunk_id")

        if not chunk_id or source.get("status") == "not_found":
            return AgentResult(
                agent_name=self.name,
                status="ok",
                data={
                    "central_excerpt": None,
                    "previous_context": None,
                    "next_context": None,
                    "sequence_index": None,
                    "out_of_context_risk": "indeterminado — fonte não localizada",
                    "observations": ["Fonte não localizada; análise de contexto não aplicável."],
                },
                notes=["Fonte ausente — contexto não analisado."],
            )

        try:
            from models.database import SessionLocal, Chunk
        except ImportError as exc:
            return AgentResult(
                agent_name=self.name,
                status="error",
                data={},
                notes=[],
                warnings=[f"Módulo DB indisponível: {exc}"],
            )

        observations: list[str] = []
        prev_text: str | None = None
        next_text: str | None = None
        seq_index: int | None = None

        try:
            with SessionLocal() as db:
                chunk = db.get(Chunk, chunk_id)
                if chunk is None:
                    return AgentResult(
                        agent_name=self.name,
                        status="ok",
                        data={
                            "central_excerpt": None,
                            "previous_context": None,
                            "next_context": None,
                            "sequence_index": None,
                            "out_of_context_risk": "indeterminado — chunk não encontrado no DB",
                            "observations": [f"Chunk {chunk_id} não encontrado."],
                        },
                        notes=["Chunk ausente no DB."],
                    )

                seq_index = chunk.sequence_index
                central_text = chunk.text

                if seq_index is not None:
                    prev_chunk = (
                        db.query(Chunk)
                        .filter(
                            Chunk.book_id == chunk.book_id,
                            Chunk.sequence_index == seq_index - 1,
                        )
                        .first()
                    )
                    next_chunk = (
                        db.query(Chunk)
                        .filter(
                            Chunk.book_id == chunk.book_id,
                            Chunk.sequence_index == seq_index + 1,
                        )
                        .first()
                    )
                    prev_text = prev_chunk.text[:400] if prev_chunk else None
                    next_text = next_chunk.text[:400] if next_chunk else None

                    if prev_text is None:
                        observations.append("Trecho anterior não disponível (primeiro chunk do livro ou sequência interrompida).")
                    if next_text is None:
                        observations.append("Trecho posterior não disponível (último chunk do livro ou sequência interrompida).")
                else:
                    observations.append("sequence_index não definido para este chunk — adjacentes não recuperados.")

        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                status="error",
                data={},
                notes=[],
                warnings=[f"Falha ao consultar DB: {exc}"],
            )

        risk = _context_risk(prev_text, next_text, central_text)

        result = {
            "central_excerpt": central_text[:500],
            "previous_context": prev_text,
            "next_context": next_text,
            "sequence_index": seq_index,
            "out_of_context_risk": risk,
            "observations": observations,
        }

        ctx.findings["context"] = result

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=[
                f"Contexto recuperado para chunk {chunk_id} (seq={seq_index}).",
                f"Risco de uso fora de contexto: {risk}.",
            ],
        )
