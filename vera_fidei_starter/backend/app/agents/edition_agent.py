from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext

_COLLECTION_FULL_NAME: dict[str, str] = {
    "PL": "Patrologia Latina (Migne)",
    "PG": "Patrologia Graeca (Migne)",
    "PO": "Patrologia Orientalis",
    "PT": "Coleção Patrística (Paulus)",
    "CONC": "Documentos Conciliares",
    "MAG": "Magistério",
    "NA": "New Advent",
}


class EditionAgent(BaseAgent):
    name = "edition_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        source = ctx.findings.get("source", {})
        chunk_id = source.get("chunk_id")
        collection = source.get("collection", "")

        if not chunk_id or source.get("status") == "not_found":
            return AgentResult(
                agent_name=self.name,
                status="ok",
                data={
                    "work": source.get("candidate_work"),
                    "collection": collection or None,
                    "available_files": [],
                    "considered_editions": [],
                    "adopted_edition": "não identificada",
                    "choice_reason": "Fonte não localizada.",
                    "risks": ["Edição desconhecida — qualquer validação textual é provisória."],
                },
                notes=["Fonte não localizada; análise de edição não aplicável."],
            )

        try:
            from models.database import SessionLocal, Chunk, BookFile
        except ImportError as exc:
            return AgentResult(
                agent_name=self.name,
                status="error",
                data={},
                notes=[],
                warnings=[f"Módulo DB indisponível: {exc}"],
            )

        try:
            with SessionLocal() as db:
                chunk = db.get(Chunk, chunk_id)
                if chunk is None:
                    raise ValueError(f"Chunk {chunk_id} não encontrado.")

                book = chunk.book
                files = (
                    db.query(BookFile)
                    .filter(BookFile.book_id == book.id)
                    .order_by(BookFile.volume_number)
                    .all()
                )

                available_files = [
                    {
                        "filename": f.original_filename,
                        "volume": f.volume_number,
                        "editor": f.editor,
                        "translator": f.translator,
                    }
                    for f in files
                ]

        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                status="error",
                data={},
                notes=[],
                warnings=[f"Falha ao consultar DB: {exc}"],
            )

        collection_name = _COLLECTION_FULL_NAME.get(collection.upper(), collection or "desconhecida")
        adopted_edition = book.edition_label or collection_name

        # Build list of editions represented in the corpus for this work
        considered_editions: list[str] = []
        if collection_name:
            considered_editions.append(collection_name)
        for f in available_files:
            if f["editor"]:
                label = f"Ed. {f['editor']}"
                if label not in considered_editions:
                    considered_editions.append(label)
            if f["translator"]:
                label = f"Trad. {f['translator']}"
                if label not in considered_editions:
                    considered_editions.append(label)

        risks: list[str] = []
        if not available_files:
            risks.append("Nenhum arquivo de edição vinculado ao livro no DB.")
        if collection in ("PG", "PL"):
            risks.append(
                "Edições Migne (PG/PL) são reproduções do séc. XIX — cruzar com edição crítica moderna recomendado."
            )
        if not book.edition_label:
            risks.append("Campo edition_label não preenchido — edição não confirmada formalmente.")

        result = {
            "work": book.canonical_title or book.title,
            "collection": collection,
            "collection_name": collection_name,
            "available_files": available_files,
            "considered_editions": considered_editions or ["desconhecida"],
            "adopted_edition": adopted_edition,
            "choice_reason": f"Edição presente no corpus para '{book.title}'.",
            "risks": risks or ["Edição provisória — aguarda cruzamento crítico."],
        }

        ctx.findings["edition"] = result

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=[
                f"Edição adotada: {adopted_edition}.",
                f"Arquivos vinculados no DB: {len(available_files)}.",
            ],
        )
