from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext

# Mapeamento: 7 códigos internos → 4 saídas públicas
_CODE_TO_PUBLIC: dict[str, tuple[str, str]] = {
    "CONFIRMADA_EXATA":      ("confirmado",      "alto"),
    "TRADUCAO_FIEL":         ("confirmado",      "médio-alto"),
    "CORRESPONDENCIA_FORTE": ("provável",         "médio"),
    "ATRIBUICAO_DUVIDOSA":   ("inconclusivo",    "baixo"),
    "TRADUCAO_IMPRECISA":    ("inconclusivo",    "baixo"),
    "PARAFRASE_PLAUSIVEL":   ("inconclusivo",    "baixo"),
    "NAO_ENCONTRADA":        ("não sustentado",  "crítico"),
}

# Ordem de degradação conservadora (regra: em caso de dúvida, vai para baixo)
_DEGRADATION: dict[str, str] = {
    "confirmado":     "provável",
    "provável":       "inconclusivo",
    "inconclusivo":   "não sustentado",
    "não sustentado": "não sustentado",
}
_DEGRADATION_LEVEL: dict[str, str] = {
    "confirmado":     "médio",
    "provável":       "baixo",
    "inconclusivo":   "crítico",
    "não sustentado": "crítico",
}

# Recomendações por veredito
_RECOMMENDATION: dict[str, str] = {
    "confirmado": (
        "Pode ser exibida como citação autêntica. "
        "Informar edição adotada caso provisória."
    ),
    "provável": (
        "Pode ser exibida com ressalva: 'provavelmente atribuída a este autor'. "
        "Não afirmar autenticidade sem verificação adicional."
    ),
    "inconclusivo": (
        "Exibir como inconclusiva. Indicar que o sistema não encontrou "
        "correspondência suficiente para confirmar ou negar."
    ),
    "não sustentado": (
        "Não exibir como autêntica. "
        "O sistema não localizou base documental suficiente para esta citação."
    ),
}


class SafetyAgent(BaseAgent):
    name = "safety_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        verification = ctx.reports.get("citation_verifier", {})
        consistency = ctx.reports.get("consistency_agent", {})

        internal_code: str = verification.get("status", "NAO_ENCONTRADA")
        intrusion_score: float = verification.get("intrusion_score", 0.0)
        conflicts: list = consistency.get("detected_conflicts", [])
        combined_score: float = verification.get("combined_score", 0.0)

        # ── Traduz para veredito público ──────────────────────────────
        public_verdict, safety_level = _CODE_TO_PUBLIC.get(
            internal_code, ("não sustentado", "crítico")
        )

        # ── Regra conservadora: degradar se intrusão alta ou conflitos ─
        degradation_reasons: list[str] = []

        if intrusion_score > 0.3:
            degradation_reasons.append(
                f"Intrusão de linguagem moderna detectada (score {intrusion_score:.2f} > 0.3)."
            )
            public_verdict = _DEGRADATION[public_verdict]
            safety_level = _DEGRADATION_LEVEL[public_verdict]

        if conflicts:
            degradation_reasons.append(
                f"{len(conflicts)} conflito(s) detectado(s) entre agentes."
            )
            public_verdict = _DEGRADATION[public_verdict]
            safety_level = _DEGRADATION_LEVEL[public_verdict]

        # ── Monta evidências ──────────────────────────────────────────
        strengths: list[str] = []
        weaknesses: list[str] = []

        if combined_score >= 0.75:
            strengths.append(f"Score combinado alto ({combined_score:.2f}).")
        if verification.get("author_match"):
            strengths.append("Correspondência de autor confirmada.")
        if verification.get("lexical_anchor", 0.0) >= 0.30:
            strengths.append("Âncora lexical forte — palavras-chave presentes no texto localizado.")

        if combined_score < 0.55:
            weaknesses.append(f"Score combinado baixo ({combined_score:.2f}).")
        if not verification.get("author_match"):
            weaknesses.append("Correspondência de autor não confirmada.")
        if intrusion_score > 0.1:
            weaknesses.append(f"Linguagem moderna detectada na citação (score {intrusion_score:.2f}).")
        if internal_code in ("PARAFRASE_PLAUSIVEL", "ATRIBUICAO_DUVIDOSA"):
            weaknesses.append("Classificação interna indica apenas correspondência parcial ou atribuição duvidosa.")

        error_risk_map = {
            "confirmado":    "baixo",
            "provável":      "moderado",
            "inconclusivo":  "alto",
            "não sustentado": "muito alto",
        }

        result = {
            "internal_code": internal_code,
            "final_verdict": public_verdict,
            "safety_level": safety_level,
            "error_risk": error_risk_map[public_verdict],
            "degradation_applied": len(degradation_reasons) > 0,
            "degradation_reasons": degradation_reasons,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendation": _RECOMMENDATION[public_verdict],
            "match_strategy": verification.get("match_strategy"),
        }

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=[
                f"Veredito público: {public_verdict.upper()} (nível de segurança: {safety_level}).",
                *(f"Degradado: {r}" for r in degradation_reasons),
            ],
        )
