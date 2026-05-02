from dataclasses import dataclass


@dataclass
class ClassificationResult:
    code: str
    label: str
    confidence: str


# Âncoras mínimas para resultados de alta confiança.
# Evitam que similaridade temática seja confundida com correspondência textual.
_ANCHOR_STRONG = 0.30   # exige que 30 % dos tokens significativos da query estejam na fonte
_ANCHOR_MODERATE = 0.18 # exige 18 % — para resultados intermediários


class DeterministicClassifier:
    def classify(
        self,
        combined_score: float,
        exact_match: bool,
        author_match: bool,
        translation_fidelity: str | None = None,
        lexical_anchor: float = 0.0,
        intrusion_score: float = 0.0,
    ) -> ClassificationResult:
        # ── Portão de intrusão conceitual ─────────────────────────────────────
        # Qualquer presença de linguagem acadêmica moderna anacrônica (ex:
        # "reinterpretação", "construção viva", "intérpretes posteriores") em
        # citações patrísticas é sinal forte de fabricação ou pseudoparáfrase.
        # O portão só cede para correspondência exata — o único caso onde a
        # frase foi literalmente encontrada no corpus independente do estilo.
        if intrusion_score > 0.0 and not exact_match:
            return ClassificationResult("NAO_ENCONTRADA", "❌ Não encontrada", "Nenhuma")

        # ── Correspondência exata ─────────────────────────────────────────────
        # Limiares calibrados para text_score normalizado [0,1] (ES BM25 é capado em 1.0):
        # max combined (text=1, semantic=1, author=True)  = 0.65+0.35+0.2 = 1.2
        # max combined sem semantic (texto exato no DB)    = 0.65+0.00+0.2 = 0.85
        # → threshold de 0.80 garante CONFIRMADA mesmo sem retorno ChromaDB
        if exact_match and author_match and combined_score >= 0.80:
            return ClassificationResult("CONFIRMADA_EXATA", "✅ Confirmada (exata)", "Alta")
        # Após penalidade 0.6 (exact+wrong author): max sem semântico = 0.65*0.6 = 0.39
        # → threshold 0.35 cobre o caso onde chunk não está no ChromaDB (semantic=0)
        #   mas o texto foi encontrado literalmente — evidência forte de atribuição errada.
        if exact_match and not author_match and combined_score >= 0.35:
            return ClassificationResult("ATRIBUICAO_DUVIDOSA", "🔴 Atribuição duvidosa", "Baixa")

        # ── Fidelidade de tradução ────────────────────────────────────────────
        # Exige ancoragem lexical: garante que a query usa vocabulário real do trecho,
        # não apenas jargão temático plausível.
        if translation_fidelity == "fiel" and author_match and combined_score >= 0.55 and lexical_anchor >= _ANCHOR_MODERATE:
            return ClassificationResult("TRADUCAO_FIEL", "✅ Tradução fiel confirmada", "Alta")
        if translation_fidelity == "fiel" and not author_match and combined_score >= 0.55 and lexical_anchor >= _ANCHOR_MODERATE:
            return ClassificationResult("ATRIBUICAO_DUVIDOSA", "🔴 Atribuição duvidosa", "Baixa")
        if translation_fidelity == "imprecisa" and combined_score >= 0.55 and lexical_anchor >= _ANCHOR_MODERATE:
            return ClassificationResult("TRADUCAO_IMPRECISA", "🟠 Tradução imprecisa", "Média")

        # ── Correspondência forte (query em idioma original, sem tradução no banco) ──
        # Exige âncora forte: impede que semântica alta sozinha confirme frases falsas.
        if combined_score >= 0.80 and lexical_anchor >= _ANCHOR_STRONG:
            return ClassificationResult("CORRESPONDENCIA_FORTE", "🟡 Forte correspondência", "Alta")

        # ── Paráfrase plausível ───────────────────────────────────────────────
        # Aceita âncora moderada: a query usa vocabulário do tema mas não corresponde
        # com precisão ao trecho localizado.
        if combined_score >= 0.55 and lexical_anchor >= _ANCHOR_MODERATE:
            return ClassificationResult("PARAFRASE_PLAUSIVEL", "🟠 Paráfrase plausível", "Média")

        # ── Não encontrada ────────────────────────────────────────────────────
        # Cobre dois casos distintos:
        # (a) score baixo — nenhuma correspondência relevante
        # (b) score alto mas âncora baixa — similaridade temática sem base textual
        #     (frase inventada sobre o tema correto)
        return ClassificationResult("NAO_ENCONTRADA", "❌ Não encontrada", "Nenhuma")
