from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext

_NOT_FOUND: dict = {
    "status": "not_found",
    "confidence": 0.0,
    "candidate_author": None,
    "canonical_author": None,
    "candidate_work": None,
    "candidate_edition": None,
    "language": None,
    "located_excerpt": "",
    "reference": None,
    "collection": None,
    "volume": None,
    "column_start": None,
    "pdf_page": None,
    "author_match": False,
    "match_strategy": None,
    "observations": [],
}


class SourceFinderAgent(BaseAgent):
    name = "source_finder"

    def run(self, ctx: PipelineContext) -> AgentResult:
        warnings: list[str] = []
        candidates: list[dict] = ctx.findings.get("search_candidates", [])
        attributed_to: str = ctx.findings.get("attributed_to", "")

        if not candidates:
            ctx.findings["source"] = _NOT_FOUND.copy()
            return AgentResult(
                agent_name=self.name,
                status="ok",
                data=_NOT_FOUND.copy(),
                notes=["Nenhum candidato recebido do search_agent."],
                warnings=["Fonte não localizada — corpus pode estar vazio ou serviços offline."],
            )

        # ── Consulta DB para enriquecer cada candidato ─────────────────
        try:
            from models.database import SessionLocal, Chunk, Book
            from utils.author_detection import detect_author
            from services.verification_service import _author_matches
        except ImportError as exc:
            ctx.findings["source"] = _NOT_FOUND.copy()
            return AgentResult(
                agent_name=self.name,
                status="ok",
                data=_NOT_FOUND.copy(),
                notes=["Erro de importação de módulo."],
                warnings=[f"DB ou utils indisponível: {exc}"],
            )

        enriched: list[dict] = []
        try:
            with SessionLocal() as db:
                for cand in candidates:
                    chunk = db.get(Chunk, cand["chunk_id"])
                    if chunk is None:
                        continue
                    book = chunk.book

                    # Normaliza autor canônico
                    detected_author, score = detect_author(
                        book.canonical_title or book.title,
                        chunk.text[:500],
                    )
                    canonical = detected_author or book.canonical_author or book.author

                    # Verifica correspondência com autor atribuído
                    author_match = _author_matches(attributed_to, book, chunk=chunk) if attributed_to else False

                    enriched.append({
                        "chunk_id": cand["chunk_id"],
                        "combined_score": cand["combined_score"],
                        "text_score": cand["text_score"],
                        "semantic_score": cand["semantic_score"],
                        "match_strategy": cand["match_strategy"],
                        "excerpt": cand.get("excerpt") or chunk.text[:350],
                        "full_text": chunk.text,
                        "candidate_author": book.author,
                        "canonical_author": canonical,
                        "candidate_work": book.canonical_title or book.title,
                        "candidate_edition": book.edition_label or None,
                        "language": book.language,
                        "collection": book.collection,
                        "volume": chunk.volume,
                        "column_start": chunk.column_start,
                        "pdf_page": chunk.pdf_page,
                        "author_match": author_match,
                        "author_match_score": score,
                    })
        except Exception as exc:
            ctx.findings["source"] = _NOT_FOUND.copy()
            return AgentResult(
                agent_name=self.name,
                status="ok",
                data=_NOT_FOUND.copy(),
                notes=["Falha na consulta ao banco de dados."],
                warnings=[f"DB indisponível: {exc}"],
            )

        if not enriched:
            ctx.findings["source"] = _NOT_FOUND.copy()
            return AgentResult(
                agent_name=self.name,
                status="ok",
                data=_NOT_FOUND.copy(),
                notes=["Chunks não encontrados no banco para os candidatos retornados pela busca."],
                warnings=["Chunks podem ter sido removidos ou IDs estão dessincronizados."],
            )

        # ── Seleciona melhor candidato ─────────────────────────────────
        # Prioritiza: author_match > combined_score
        enriched.sort(key=lambda c: (c["author_match"], c["combined_score"]), reverse=True)
        best = enriched[0]

        reference_parts = []
        if best["candidate_work"]:
            reference_parts.append(best["candidate_work"])
        if best["volume"]:
            reference_parts.append(f"vol. {best['volume']}")
        if best["column_start"]:
            reference_parts.append(f"col. {best['column_start']}")
        elif best["pdf_page"]:
            reference_parts.append(f"p. {best['pdf_page']}")

        result = {
            "status": "found",
            "confidence": best["combined_score"],
            "candidate_author": best["candidate_author"],
            "canonical_author": best["canonical_author"],
            "candidate_work": best["candidate_work"],
            "candidate_edition": best["candidate_edition"],
            "language": best["language"],
            "located_excerpt": best["full_text"],
            "reference": ", ".join(reference_parts) if reference_parts else None,
            "collection": best["collection"],
            "volume": best["volume"],
            "column_start": best["column_start"],
            "pdf_page": best["pdf_page"],
            "author_match": best["author_match"],
            "match_strategy": best["match_strategy"],
            "observations": [
                f"Candidato selecionado com score combinado {best['combined_score']:.2f}.",
                f"Correspondência de autor: {'sim' if best['author_match'] else 'não confirmada'}.",
            ],
        }

        ctx.findings["source"] = result
        ctx.handoff("source_finder", "citation_verifier", result)
        ctx.handoff("source_finder", "language_agent", result)
        ctx.handoff("source_finder", "edition_agent", result)

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=[f"Fonte localizada: {best['candidate_work']} ({best['canonical_author']})."],
            warnings=warnings,
        )
