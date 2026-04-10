from schemas.citation import VerifyCitationRequest
from confidence.classifier import ClassificationResult


class ResultExplainer:
    def explain(self, payload: VerifyCitationRequest, result: ClassificationResult, work: str | None, author: str | None) -> str:
        if result.code == "CONFIRMADA_EXATA":
            return f"A citação foi localizada de forma exata em fonte primária, associada a {author or 'autor não identificado'} na obra {work or 'não informada'}."
        if result.code == "ATRIBUICAO_DUVIDOSA":
            return "O texto foi localizado, mas a autoria enviada não coincide com a melhor correspondência encontrada."
        if result.code == "CONFIRMADA_TRADUCAO":
            return "A ideia foi confirmada em fonte primária, mas a formulação apresentada varia em relação ao texto localizado."
        if result.code == "PARAFRASE_PLAUSIVEL":
            return "Há indícios de que a citação seja uma paráfrase plausível do conteúdo encontrado."
        return "Nenhuma correspondência confiável foi localizada nas fontes indexadas atualmente."
