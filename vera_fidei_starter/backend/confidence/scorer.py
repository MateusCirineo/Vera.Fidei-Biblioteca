class CombinedScorer:
    def combine(self, text_score: float, semantic_score: float, author_match: bool) -> float:
        if text_score == 0.0:
            # Sem match textual direto: elevar peso semântico para buscas cross-lingual
            score = semantic_score * 0.9
        else:
            score = (text_score * 0.7) + (semantic_score * 0.3)
        if author_match:
            score += 0.5
        return score
