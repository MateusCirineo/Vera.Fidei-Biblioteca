from __future__ import annotations

import re
from pathlib import Path

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class IngestionValidationAgent(BaseAgent):
    name = "ingestion_validation_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        backend_dir = Path(__file__).resolve().parents[2]
        pdf_dir = backend_dir / "pdfs"
        expected = sorted(
            path.stem.upper()
            for path in pdf_dir.glob("*.pdf")
            if re.fullmatch(r"(PG|PL|PO)\d{3}", path.stem.upper())
        )

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
                collection_label = {
                    "PG": "Graeca",
                    "PL": "Latina",
                    "PO": "Orientalis",
                }[key[:2]]
                title = f"Patrologia {collection_label} {key}"
                book = db.query(Book).filter(Book.title == title).first()
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
            warnings=[] if expected else ["Nenhum PDF PG/PL/PO encontrado para validar."],
        )
