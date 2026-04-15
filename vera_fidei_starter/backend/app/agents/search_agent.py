from __future__ import annotations

import re
import unicodedata

from app.agents.base import BaseAgent, AgentResult, PipelineContext


def _normalize(text: str) -> str:
    """Minúsculo, sem acentos, sem pontuação excessiva."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_quote(task: str) -> str:
    """Extrai o texto entre aspas, se houver. Caso contrário, retorna a tarefa inteira."""
    match = re.search(r'[\u201c\u201d\u00ab\u00bb"](.*?)[\u201c\u201d\u00ab\u00bb"]', task, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Tenta após dois-pontos
    match = re.search(r':\s*(.+)$', task, re.DOTALL)
    if match:
        return match.group(1).strip()
    return task.strip()


def _extract_attributed_to(task: str) -> str:
    """Extrai o autor atribuído a partir de padrões como 'atribuída a X' ou 'de X:'."""
    patterns = [
        r'atribu[íi]d[ao]\s+a\s+([^:,\n"]+)',
        r'\bde\s+((?:São|Santo|Santa|Beato|Papa|Padre|San)\s+\w+(?:\s+\w+)?)',
        r'\bsegundo\s+((?:São|Santo|Santa|Beato|Papa|Padre|San)\s+\w+(?:\s+\w+)?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, task, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


class SearchAgent(BaseAgent):
    name = "search_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        warnings: list[str] = []

        quote = _extract_quote(ctx.user_task)
        attributed_to = _extract_attributed_to(ctx.user_task)

        # Salva no contexto para uso pelos agentes seguintes
        ctx.findings["quote"] = quote
        ctx.findings["attributed_to"] = attributed_to

        # ── Busca textual (Elasticsearch) ──────────────────────────────
        text_hits: dict[int, dict] = {}
        try:
            from search.text_search import TextSearchClient
            ts = TextSearchClient()
            for hit in ts.search(quote, attributed_to=attributed_to, limit=10):
                text_hits[hit.chunk_id] = {
                    "chunk_id": hit.chunk_id,
                    "text_score": hit.score,
                    "semantic_score": 0.0,
                    "excerpt": hit.excerpt,
                }
        except Exception as exc:
            warnings.append(f"Elasticsearch indisponível: {exc}")

        # ── Busca semântica (ChromaDB) ─────────────────────────────────
        try:
            from search.semantic_search import SemanticSearchClient
            sc = SemanticSearchClient()
            for hit in sc.search(quote, limit=10):
                if hit.chunk_id in text_hits:
                    text_hits[hit.chunk_id]["semantic_score"] = hit.score
                else:
                    text_hits[hit.chunk_id] = {
                        "chunk_id": hit.chunk_id,
                        "text_score": 0.0,
                        "semantic_score": hit.score,
                        "excerpt": "",
                    }
        except Exception as exc:
            warnings.append(f"ChromaDB indisponível: {exc}")

        if not text_hits:
            warnings.append("Nenhum candidato localizado — corpus pode estar vazio ou serviços offline.")
            ctx.findings["search_candidates"] = []
            return AgentResult(
                agent_name=self.name,
                status="ok",
                data={"candidates": [], "quote_extracted": quote, "attributed_to": attributed_to},
                notes=["Busca concluída sem candidatos."],
                warnings=warnings,
            )

        # ── Ranking combinado ──────────────────────────────────────────
        candidates = []
        for cand in text_hits.values():
            ts_score = cand["text_score"]
            sem_score = cand["semantic_score"]
            combined = ts_score * 0.65 + sem_score * 0.35

            # Determina estratégia de match para rastreabilidade
            if ts_score >= 0.3:
                match_strategy = "user_query"
            elif ts_score >= 0.1:
                match_strategy = "fallback_quote"
            else:
                match_strategy = "semantic"

            candidates.append({**cand, "combined_score": combined, "match_strategy": match_strategy})

        candidates.sort(key=lambda c: c["combined_score"], reverse=True)
        top5 = candidates[:5]

        ctx.findings["search_candidates"] = top5

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data={
                "candidates_found": len(top5),
                "top_combined_score": top5[0]["combined_score"] if top5 else 0.0,
                "quote_extracted": quote,
                "attributed_to": attributed_to,
                "match_strategy": top5[0]["match_strategy"] if top5 else None,
            },
            notes=[f"Encontrados {len(top5)} candidatos. Melhor score: {top5[0]['combined_score']:.2f}" if top5 else "Sem candidatos."],
            warnings=warnings,
        )
