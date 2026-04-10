from dataclasses import dataclass


@dataclass
class ClassificationResult:
    code: str
    label: str
    confidence: str


class DeterministicClassifier:
    def classify(
        self,
        combined_score: float,
        exact_match: bool,
        author_match: bool,
        translation_fidelity: str | None = None,
    ) -> ClassificationResult:
        if exact_match and author_match and combined_score >= 1.2:
            return ClassificationResult("CONFIRMADA_EXATA", "✅ Confirmada (exata)", "Alta")
        if exact_match and not author_match and combined_score >= 1.0:
            return ClassificationResult("ATRIBUICAO_DUVIDOSA", "🔴 Atribuição duvidosa", "Baixa")
        if translation_fidelity == "fiel" and combined_score >= 0.85:
            return ClassificationResult("TRADUCAO_FIEL", "✅ Tradução fiel confirmada", "Alta")
        if translation_fidelity == "imprecisa" and combined_score >= 0.6:
            return ClassificationResult("TRADUCAO_IMPRECISA", "🟠 Tradução imprecisa", "Média")
        if combined_score >= 0.9:
            return ClassificationResult("CONFIRMADA_TRADUCAO", "🟡 Confirmada (tradução)", "Alta")
        if combined_score >= 0.6:
            return ClassificationResult("PARAFRASE_PLAUSIVEL", "🟠 Paráfrase plausível", "Média")
        return ClassificationResult("NAO_ENCONTRADA", "❌ Não encontrada", "Nenhuma")
