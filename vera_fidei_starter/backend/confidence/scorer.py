class CombinedScorer:
    def combine(self, text_score: float, semantic_score: float, author_match: bool) -> float:
        # ES BM25 retorna floats ilimitados (ex: 30+); normaliza para [0, 1]
        # para que as penalidades e limiares do classificador funcionem corretamente.
        text_score = min(text_score, 1.0)
        semantic_score = min(semantic_score, 1.0)

        if text_score == 0.0:
            # Sem match textual direto: elevar peso semântico para buscas cross-lingual
            score = semantic_score * 0.9
        else:
            score = (text_score * 0.65) + (semantic_score * 0.35)
        if author_match:
            # Bônus reduzido: autor correto é indício, não confirmação.
            score += 0.2
        return score
