from __future__ import annotations

from schemas.citation import VerifyCitationRequest
from confidence.classifier import ClassificationResult


def _hardcoded_explanation(
    result: ClassificationResult,
    work: str | None,
    author: str | None,
    intrusion_score: float,
    ocr_similarity: float,
) -> str:
    if result.code == "CONFIRMADA_EXATA":
        return (
            f"A citação foi localizada de forma exata em fonte primária, associada a "
            f"{author or 'autor não identificado'} na obra {work or 'não informada'}."
        )
    if result.code == "ATRIBUICAO_DUVIDOSA":
        found_ref = ""
        if author and work:
            found_ref = f" na obra '{work}' ({author})"
        elif author:
            found_ref = f" em obra de {author}"
        return (
            f"O texto foi localizado{found_ref}, mas o autor atribuído não é o mesmo da fonte encontrada. "
            f"É possível que essa frase esteja sendo citada nesse documento, e não seja o texto original do autor indicado. "
            f"Verifique se o autor atribuído é realmente a fonte primária dessa expressão."
        )
    if result.code == "CORRESPONDENCIA_FORTE":
        if ocr_similarity >= 0.80:
            return (
                "A citação coincide textualmente com o trecho localizado na tradução da fonte utilizada. "
                "Pequenas diferenças de formatação (numeração de linha, pontuação) foram ignoradas na comparação."
            )
        if ocr_similarity >= 0.60:
            return (
                "A formulação apresentada é muito próxima ao texto localizado na fonte primária. "
                "A correspondência é forte, com variações mínimas de formatação ou pontuação."
            )
        return "A formulação encontrada corresponde ao conteúdo da fonte primária, mas apresenta diferenças textuais em relação à versão apresentada."
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
    return (
        "Nenhuma correspondência textual confiável foi localizada. "
        "O texto pode tratar de tema patrístico genuíno, mas a formulação não corresponde "
        "ao conteúdo real de nenhum trecho indexado — possivelmente paráfrase interpretativa, "
        "comentário secundário ou citação fabricada."
    )


def _build_prompt(
    payload: VerifyCitationRequest,
    result: ClassificationResult,
    work: str | None,
    author: str | None,
    intrusion_score: float,
    ocr_similarity: float,
) -> str:
    return f"""Você é o componente explicador do sistema Vera.Fidei, um verificador de citações patrísticas e documentos da Igreja.

Seu papel é EXCLUSIVAMENTE verbalizar em português simples e claro o resultado de uma verificação já concluída por regras determinísticas. Você NÃO pode alterar o veredito, o score nem a classificação. Você apenas explica o que o sistema encontrou.

## Dados da verificação

- **Citação analisada:** {payload.quote}
- **Autor atribuído:** {payload.attributed_to or "não informado"}
- **Classificação:** {result.label}
- **Nível de confiança:** {result.confidence}
- **Obra localizada:** {work or "não identificada"}
- **Autor da obra encontrada:** {author or "não identificado"}
- **Intrusão de linguagem moderna:** {"detectada" if intrusion_score > 0 else "não detectada"}
- **Correspondência textual:** {"alta" if ocr_similarity >= 0.80 else "média" if ocr_similarity >= 0.50 else "baixa"}

## Instruções

1. Escreva 2 a 4 frases em português claro, sem jargão técnico.
2. Explique POR QUÊ o sistema chegou a essa classificação, com base nos dados acima.
3. Se a citação foi localizada, mencione obra e autor encontrados.
4. Se não foi localizada ou é paráfrase, explique sem dramatizar.
5. NÃO invente dados. NÃO mencione fontes, obras ou autores ausentes dos dados acima.
6. NÃO repita códigos internos nem scores numéricos.
7. Seja conciso. O usuário é leigo em patrística.

Escreva apenas a explicação, sem títulos nem listas."""


def _call_anthropic(prompt: str, model: str, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _call_groq(prompt: str, model: str, api_key: str) -> str:
    from groq import Groq
    client = Groq(api_key=api_key)
    chat = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.3,
    )
    return chat.choices[0].message.content.strip()


def _call_google(prompt: str, model: str, api_key: str) -> str:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=300, temperature=0.3),
    )
    return response.text.strip()


_PROVIDERS = {
    "anthropic": (_call_anthropic, "anthropic_api_key"),
    "groq":      (_call_groq,      "groq_api_key"),
    "google":    (_call_google,    "google_api_key"),
}


def _llm_explanation(
    payload: VerifyCitationRequest,
    result: ClassificationResult,
    work: str | None,
    author: str | None,
    intrusion_score: float,
    ocr_similarity: float,
) -> str:
    """
    Verbalizes the already-decided classification via LLM.
    The LLM does NOT influence score or verdict — explanatory-only.
    Falls back to hardcoded text on any error.
    """
    try:
        from core.config import settings

        provider = settings.llm_provider
        if provider not in _PROVIDERS:
            return _hardcoded_explanation(result, work, author, intrusion_score, ocr_similarity)

        caller, key_attr = _PROVIDERS[provider]
        api_key = getattr(settings, key_attr, "")
        if not api_key:
            return _hardcoded_explanation(result, work, author, intrusion_score, ocr_similarity)

        prompt = _build_prompt(payload, result, work, author, intrusion_score, ocr_similarity)
        text = caller(prompt, settings.llm_model, api_key)
        return text if text else _hardcoded_explanation(result, work, author, intrusion_score, ocr_similarity)

    except Exception:
        return _hardcoded_explanation(result, work, author, intrusion_score, ocr_similarity)


class ResultExplainer:
    def explain(
        self,
        payload: VerifyCitationRequest,
        result: ClassificationResult,
        work: str | None,
        author: str | None,
        intrusion_score: float = 0.0,
        ocr_similarity: float = 0.0,
    ) -> str:
        try:
            from core.config import settings
            use_llm = settings.llm_enabled and settings.llm_provider in _PROVIDERS
        except Exception:
            use_llm = False

        if use_llm:
            return _llm_explanation(payload, result, work, author, intrusion_score, ocr_similarity)
        return _hardcoded_explanation(result, work, author, intrusion_score, ocr_similarity)
