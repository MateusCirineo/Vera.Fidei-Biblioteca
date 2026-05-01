from __future__ import annotations

from pathlib import Path

from app.agents.base import BaseAgent, AgentResult, PipelineContext


class PdfIngestionAgent(BaseAgent):
    name = "pdf_ingestion_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        backend_dir = Path(__file__).resolve().parents[2]
        pdf_dir = backend_dir / "pdfs"
        targets = [
            *(pdf_dir / f"PG{i:03d}.pdf" for i in range(2, 6)),
            *(pdf_dir / f"PL{i:03d}.pdf" for i in range(1, 6)),
        ]

        inventory = []
        missing = []
        zero = []
        for path in targets:
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            if not exists:
                missing.append(path.name)
            elif size == 0:
                zero.append(path.name)
            inventory.append({
                "filename": path.name,
                "path": str(path),
                "exists": exists,
                "bytes": size,
                "collection": path.stem[:2],
                "volume": int(path.stem[2:]),
            })

        result = {
            "pdf_dir": str(pdf_dir),
            "targets": inventory,
            "missing": missing,
            "zero_byte_files": zero,
            "recommended_command": (
                ".\\.venv\\Scripts\\python.exe scripts\\import_migne_volumes.py "
                "--batch-size 4 --cooldown-seconds 1.0 --device cuda"
            ),
            "uses_chroma_delta": True,
            "ocr_note": "OCR usa Tesseract/CPU; embeddings usam CUDA quando disponivel.",
        }

        ctx.findings["pdf_ingestion"] = result
        return AgentResult(
            agent_name=self.name,
            status="ok" if not missing and not zero else "needs_attention",
            data=result,
            notes=[
                f"PDFs-alvo encontrados: {len(targets) - len(missing)}/{len(targets)}.",
                f"Arquivos zerados: {len(zero)}.",
                "Fluxo de ingestao preparado para PG002-PG005 e PL001-PL005.",
            ],
            warnings=[*(f"Arquivo ausente: {name}" for name in missing), *(f"Arquivo zerado: {name}" for name in zero)],
        )
