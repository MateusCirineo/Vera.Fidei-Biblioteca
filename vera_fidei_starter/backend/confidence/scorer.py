class CombinedScorer:
    def combine(self, text_score: float, semantic_score: float, author_match: bool) -> float:
        if text_score == 0.0:
            # Sem match textual direto: elevar peso semântico para buscas cross-lingual
            score = semantic_score * 0.9
        else:
            score = (text_score * 0.65) + (semantic_score * 0.35)
        if author_match:
            # Bônus reduzido: autor correto é indício, não confirmação.
            # O bônus alto anterior (0.5) inflava o score de citações falsas
            # que apenas mencionam o mesmo autor/tema.
            score += 0.2
        return score
