from schemas.citation import VerifyCitationRequest
from confidence.classifier import ClassificationResult


class ResultExplainer:
    def explain(
        self,
        payload: VerifyCitationRequest,
        result: ClassificationResult,
        work: str | None,
        author: str | None,
        intrusion_score: float = 0.0,
    ) -> str:
        if result.code == "CONFIRMADA_EXATA":
            return f"A citação foi localizada de forma exata em fonte primária, associada a {author or 'autor não identificado'} na obra {work or 'não informada'}."
        if result.code == "ATRIBUICAO_DUVIDOSA":
            return "O texto foi localizado, mas a autoria enviada não coincide com a melhor correspondência encontrada."
        if result.code == "CORRESPONDENCIA_FORTE":
            return "A formulação encontrada corresponde ao conteúdo da fonte primária, mas não coincide textualmente com a versão apresentada."
        if result.code == "PARAFRASE_PLAUSIVEL":
            return "O conteúdo temático é próximo ao de um trecho localizado na fonte, mas a formulação não coincide com o texto real — pode ser paráfrase livre ou resumo interpretativo."
        if result.code == "TRADUCAO_FIEL":
            return (
                f"A citação apresentada é uma tradução fiel do texto original de "
                f"{author or 'autor não identificado'} na obra {work or 'não informada'}."
            )
        if result.code == "TRADUCAO_IMPRECISA":
            return (
                f"A citação corresponde ao conteúdo de {author or 'autor não identificado'}, "
                f"mas a tradução diverge em alguns pontos do texto original."
            )
        if intrusion_score > 0.0:
            return (
                "A formulação contém linguagem acadêmica moderna anacrônica — "
                "expressões como paráfrase interpretativa, vocabulário de teoria crítica "
                "ou metalinguagem hermenêutica que não aparecem em textos patrísticos autênticos. "
                "Isso indica um comentário secundário, pseudoparáfrase ou citação fabricada, "
                "não um texto de Padre ou Doutor da Igreja."
            )
        return "Nenhuma correspondência textual confiável foi localizada. O texto pode tratar de tema patrístico genuíno, mas a formulação não corresponde ao conteúdo real de nenhum trecho indexado — possivelmente paráfrase interpretativa, comentário secundário ou citação fabricada."
