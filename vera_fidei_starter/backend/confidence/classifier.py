from dataclasses import dataclass


@dataclass
class ClassificationResult:
    code: str
    label: str
    confidence: str


# Ancoras minimas para resultados de maior confianca.
# Evitam que similaridade tematica seja confundida com correspondencia textual.
_ANCHOR_STRONG = 0.30
_ANCHOR_MODERATE = 0.18


class DeterministicClassifier:
    def classify(
        self,
        combined_score: float,
        exact_match: bool,
        author_match: bool,
        translation_fidelity: str | None = None,
        lexical_anchor: float = 0.0,
        intrusion_score: float = 0.0,
        ocr_similarity: float = 0.0,
    ) -> ClassificationResult:
        # Modern academic language in patristic quotes is treated as fabrication
        # unless the phrase was literally found in the corpus.
        if intrusion_score > 0.0 and not exact_match:
            return ClassificationResult("NAO_ENCONTRADA", "Não encontrada", "Nenhuma")

        # Exact textual confirmation.
        if exact_match and author_match:
            return ClassificationResult("CONFIRMADA_EXATA", "Confirmada (exata)", "Alta")

        # The text exists, but not under the attributed author.
        if exact_match and not author_match:
            return ClassificationResult("ATRIBUICAO_DUVIDOSA", "Atribuição duvidosa", "Baixa")

        # Translation fidelity.
        if (
            translation_fidelity == "fiel"
            and author_match
            and combined_score >= 0.55
            and lexical_anchor >= _ANCHOR_MODERATE
        ):
            return ClassificationResult("TRADUCAO_FIEL", "Tradução fiel confirmada", "Alta")

        if (
            translation_fidelity == "fiel"
            and not author_match
            and combined_score >= 0.55
            and lexical_anchor >= _ANCHOR_MODERATE
        ):
            return ClassificationResult("ATRIBUICAO_DUVIDOSA", "Atribuição duvidosa", "Baixa")

        if (
            translation_fidelity == "imprecisa"
            and combined_score >= 0.55
            and lexical_anchor >= _ANCHOR_MODERATE
        ):
            return ClassificationResult("TRADUCAO_IMPRECISA", "Tradução imprecisa", "Média")

        # Non-exact same-author wording: useful for study, but not a confirmed
        # quotation. Tight thresholds avoid thematic false positives like
        # a Lutheran catechism phrase attributed to Augustine.
        if (
            author_match
            and combined_score >= 0.78
            and lexical_anchor >= 0.75
            and ocr_similarity >= 0.50
        ):
            return ClassificationResult("PARAFRASE_PLAUSIVEL", "Paráfrase/variante localizada", "Média")

        return ClassificationResult("NAO_ENCONTRADA", "Não encontrada", "Nenhuma")
