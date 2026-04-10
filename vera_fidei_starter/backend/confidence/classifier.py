from dataclasses import dataclass


@dataclass
class ClassificationResult:
    code: str
    label: str
    confidence: str


class DeterministicClassifier:
    def classify(self, combined_score: float, exact_match: bool, author_match: bool) -> ClassificationResult:
        if exact_match and author_match and combined_score >= 1.2:
            return ClassificationResult("CONFIRMADA_EXATA", "✅ Confirmada (exata)", "Alta")
        if exact_match and not author_match and combined_score >= 1.0:
            return ClassificationResult("ATRIBUICAO_DUVIDOSA", "🔴 Atribuição duvidosa", "Baixa")
        if combined_score >= 0.9:
            return ClassificationResult("CONFIRMADA_TRADUCAO", "🟡 Confirmada (tradução diferente)", "Alta")
        if combined_score >= 0.6:
            return ClassificationResult("PARAFRASE_PLAUSIVEL", "🟠 Paráfrase plausível", "Média")
        return ClassificationResult("NAO_ENCONTRADA", "❌ Não encontrada", "Nenhuma")
