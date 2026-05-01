from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class IngestionValidationAgent(BaseAgent):
    name = "ingestion_validation_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        expected = ["PG002", "PG003", "PG004", "PG005", "PL001", "PL002", "PL003", "PL004", "PL005"]

        try:
            from models.database import Book, BookFile, Chunk, SessionLocal
        except ImportError as exc:
            return AgentResult(
                agent_name=self.name,
                status="error",
                data={},
                warnings=[f"DB indisponivel: {exc}"],
            )

        rows = []
        with SessionLocal() as db:
            for key in expected:
                book = db.query(Book).filter(Book.title == f"Patrologia {'Graeca' if key.startswith('PG') else 'Latina'} {key}").first()
                if book is None:
                    rows.append({"target": key, "status": "not_imported", "files": 0, "chunks": 0})
                    continue
                files = db.query(BookFile).filter(BookFile.book_id == book.id).count()
                chunks = db.query(Chunk).filter(Chunk.book_id == book.id).count()
                rows.append({
                    "target": key,
                    "book_id": book.id,
                    "status": book.ingest_status,
                    "files": files,
                    "chunks": chunks,
                })

        done = [row for row in rows if row.get("status") == "done" and row.get("chunks", 0) > 0]
        result = {
            "expected": expected,
            "rows": rows,
            "done": len(done),
            "remaining": len(expected) - len(done),
        }
        ctx.findings["ingestion_validation"] = result
        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=[f"Volumes concluidos: {len(done)}/{len(expected)}."],
        )
