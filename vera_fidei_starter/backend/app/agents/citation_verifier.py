from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from app.agents.base import BaseAgent, AgentResult, PipelineContext

# Classificações oficiais (7 códigos internos do DeterministicClassifier)
STATUS_CONFIRMADA_EXATA = "CONFIRMADA_EXATA"
STATUS_ATRIBUICAO_DUVIDOSA = "ATRIBUICAO_DUVIDOSA"
STATUS_TRADUCAO_FIEL = "TRADUCAO_FIEL"
STATUS_TRADUCAO_IMPRECISA = "TRADUCAO_IMPRECISA"
STATUS_CORRESPONDENCIA_FORTE = "CORRESPONDENCIA_FORTE"
STATUS_PARAFRASE_PLAUSIVEL = "PARAFRASE_PLAUSIVEL"
STATUS_NAO_ENCONTRADA = "NAO_ENCONTRADA"


def _normalize(text: str) -> str:
    """Remove acentos, minúsculo, sem pontuação — para comparação textual."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _compute_lexical_anchor(query: str, text: str) -> float:
    """Fração de palavras significativas do query presentes no texto localizado."""
    query_words = set(re.findall(r'\b\w{4,}\b', _normalize(query)))
    text_words = set(re.findall(r'\b\w{4,}\b', _normalize(text)))
    if not query_words:
        return 0.0
    return len(query_words & text_words) / len(query_words)


class CitationVerifierAgent(BaseAgent):
    name = "citation_verifier"

    def run(self, ctx: PipelineContext) -> AgentResult:
        source = ctx.findings.get("source", {})

        # ── Caso: fonte não localizada ────────────────────────────────
        if source.get("status") == "not_found" or not source.get("located_excerpt"):
            result = {
                "quoted_text": ctx.user_task,
                "compared_text": "",
                "similarity": 0.0,
                "lexical_anchor": 0.0,
                "intrusion_score": 0.0,
                "exact_match": False,
                "author_match": False,
                "match_type": "none",
                "status": STATUS_NAO_ENCONTRADA,
                "status_label": "Não encontrada",
                "confidence": "baixa",
                "combined_score": 0.0,
                "justification": "Nenhum trecho correspondente foi localizado no corpus.",
                "match_strategy": None,
                "differences": [],
                "attention_points": [],
            }
            return AgentResult(
                agent_name=self.name,
                status="ok",
                data=result,
                notes=["Citação não localizada — retornando NAO_ENCONTRADA sem classificar."],
            )

        quote = ctx.findings.get("quote") or ctx.user_task
        located = source["located_excerpt"]
        text_score = source.get("confidence", 0.0)

        # Scores das buscas (vindos do search_agent via source)
        # O source_finder preserva combined_score como confidence
        # Precisamos text_score e semantic_score separados — tentamos recuperar
        search_candidates = ctx.findings.get("search_candidates", [])
        best_candidate = search_candidates[0] if search_candidates else {}
        raw_text_score = best_candidate.get("text_score", text_score)
        raw_semantic_score = best_candidate.get("semantic_score", 0.0)

        # ── Similaridade textual normalizada ─────────────────────────
        norm_quote = _normalize(quote)
        norm_located = _normalize(located)
        similarity = SequenceMatcher(None, norm_quote, norm_located).ratio()

        # ── Lexical anchor ────────────────────────────────────────────
        lexical_anchor = _compute_lexical_anchor(quote, located)

        # ── Intrusion score (jargão acadêmico moderno) ────────────────
        intrusion_score = 0.0
        try:
            from services.verification_service import _intrusion_score
            intrusion_score = _intrusion_score(quote)
        except Exception:
            pass  # Não crítico — continua sem

        # ── Correspondência exata (normalizada) ──────────────────────
        exact_match = similarity >= 0.85

        # ── Author match ──────────────────────────────────────────────
        author_match = source.get("author_match", False)

        # ── Score combinado via CombinedScorer ───────────────────────
        combined_score = 0.0
        try:
            from confidence.scorer import CombinedScorer
            combined_score = CombinedScorer().combine(raw_text_score, raw_semantic_score, author_match)
        except Exception:
            # Fallback manual se scorer indisponível
            combined_score = raw_text_score * 0.65 + raw_semantic_score * 0.35
            if author_match:
                combined_score = min(1.0, combined_score + 0.2)

        # ── Classificação determinística ──────────────────────────────
        status_code = STATUS_NAO_ENCONTRADA
        status_label = "Não encontrada"
        confidence_level = "baixa"
        try:
            from confidence.classifier import DeterministicClassifier
            clf_result = DeterministicClassifier().classify(
                combined_score=combined_score,
                exact_match=exact_match,
                author_match=author_match,
                translation_fidelity=None,  # translation_agent preencherá em fase posterior
                lexical_anchor=lexical_anchor,
                intrusion_score=intrusion_score,
            )
            status_code = clf_result.code
            status_label = clf_result.label
            confidence_level = clf_result.confidence
        except Exception as exc:
            # Fallback heurístico se classifier indisponível
            if combined_score >= 0.9 and author_match:
                status_code = STATUS_CONFIRMADA_EXATA
            elif combined_score >= 0.55 and lexical_anchor >= 0.18:
                status_code = STATUS_CORRESPONDENCIA_FORTE
            elif combined_score >= 0.35:
                status_code = STATUS_PARAFRASE_PLAUSIVEL
            else:
                status_code = STATUS_NAO_ENCONTRADA

        # ── match_strategy final ──────────────────────────────────────
        match_strategy = source.get("match_strategy") or best_candidate.get("match_strategy") or "semantic"

        # ── Diferenças observadas ─────────────────────────────────────
        differences = []
        if source.get("language") and source["language"] not in ("pt", "por", "português"):
            differences.append(
                f"A citação foi fornecida em português; a fonte localizada está em {source['language']}."
            )
        if not exact_match and similarity > 0.4:
            differences.append(f"Correspondência textual parcial (similaridade normalizada: {similarity:.0%}).")

        result = {
            "quoted_text": quote,
            "compared_text": located[:350] + ("…" if len(located) > 350 else ""),
            "similarity": round(similarity, 3),
            "lexical_anchor": round(lexical_anchor, 3),
            "intrusion_score": round(intrusion_score, 3),
            "exact_match": exact_match,
            "author_match": author_match,
            "combined_score": round(combined_score, 3),
            "status": status_code,
            "status_label": status_label,
            "confidence": confidence_level,
            "match_strategy": match_strategy,
            "justification": (
                f"Classificado como '{status_label}' com score combinado {combined_score:.2f}. "
                f"Similaridade textual: {similarity:.0%}. "
                f"Âncora lexical: {lexical_anchor:.0%}."
            ),
            "differences": differences,
            "attention_points": [
                "Edição definitiva ainda deve ser confirmada." if source.get("candidate_edition") else "Edição não identificada.",
            ],
        }

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=[f"Status: {status_code} | Score: {combined_score:.2f} | Similaridade: {similarity:.0%}"],
        )
