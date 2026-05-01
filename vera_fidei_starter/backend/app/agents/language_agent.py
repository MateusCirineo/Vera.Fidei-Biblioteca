from __future__ import annotations

from app.agents.base import BaseAgent, AgentResult, PipelineContext

_LANG_LABELS: dict[str, str] = {
    "la": "Latim",
    "grc": "Grego Antigo",
    "el": "Grego Moderno",
    "pt": "Português",
    "es": "Espanhol",
    "en": "Inglês",
    "fr": "Francês",
    "it": "Italiano",
    "de": "Alemão",
    "he": "Hebraico",
    "syc": "Siríaco",
    "cop": "Copta",
    "ar": "Árabe",
    "hy": "Armênio",
    "ka": "Georgiano",
    "gez": "Ge'ez",
}

_LANGDETECT_TO_ISO: dict[str, str] = {
    "la": "la",
    "el": "grc",
    "pt": "pt",
    "es": "es",
    "en": "en",
    "fr": "fr",
    "it": "it",
    "de": "de",
    "he": "he",
    "ar": "ar",
}


def _detect_language(text: str) -> tuple[str, float, list[str]]:
    """
    Returns (iso_code, certainty, limitations).
    Priority: script heuristic (non-Latin scripts) > Latin heuristic > langdetect.
    """
    from utils.language import detect_script_heuristic, detect_latin_heuristic

    limitations: list[str] = []

    # 1. Script detection for non-Latin scripts (Greek, Syriac, Coptic, etc.)
    script = detect_script_heuristic(text)
    if script:
        return script, 0.90, limitations

    # 2. Latin heuristic for classical Latin
    if detect_latin_heuristic(text):
        return "la", 0.85, limitations

    # 3. langdetect as fallback
    try:
        from langdetect import detect, detect_langs
        probs = detect_langs(text)
        top = probs[0]
        iso = _LANGDETECT_TO_ISO.get(top.lang, top.lang)
        certainty = round(float(top.prob), 2)
        if certainty < 0.75:
            limitations.append(f"langdetect com baixa certeza ({certainty:.0%}) — texto curto ou ambíguo.")
        return iso, certainty, limitations
    except Exception as exc:
        limitations.append(f"langdetect indisponível: {exc}")
        return "desconhecido", 0.0, limitations


class LanguageAgent(BaseAgent):
    name = "language_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        source = ctx.findings.get("source", {})
        located_text = source.get("located_excerpt", "")
        stored_language = source.get("language", "")

        # Also detect query language for cross-language context
        user_quote = ctx.findings.get("quote") or ctx.user_task
        warnings: list[str] = []

        # Detect source language
        if located_text:
            detected_iso, certainty, limitations = _detect_language(located_text[:600])
        else:
            detected_iso, certainty, limitations = "desconhecido", 0.0, ["Nenhum trecho localizado."]

        # Cross-check with stored language field
        stored_iso = ""
        try:
            from utils.language import normalize_lang
            stored_iso = normalize_lang(stored_language) if stored_language else ""
        except ImportError:
            pass

        if stored_iso and detected_iso not in ("desconhecido", stored_iso):
            # If stored and detected differ, trust stored for known codes; warn otherwise
            if stored_iso in ("la", "grc", "syc", "cop", "he"):
                detected_iso = stored_iso
                limitations.append(
                    f"Detecção automática retornou '{detected_iso}' mas campo armazenado é '{stored_iso}'. "
                    "Usando valor armazenado para idioma clássico."
                )
            else:
                warnings.append(
                    f"Divergência: idioma armazenado='{stored_iso}', detectado='{detected_iso}'."
                )

        # Detect query language
        query_iso, query_certainty, _ = _detect_language(user_quote[:400]) if user_quote else ("desconhecido", 0.0, [])

        text_nature = "texto em língua original" if detected_iso in ("la", "grc", "syc", "cop", "he", "ar", "gez") else "texto em vernáculo"

        result = {
            "source_reference": source.get("reference"),
            "identified_language": detected_iso,
            "language_label": _LANG_LABELS.get(detected_iso, detected_iso),
            "stored_language": stored_language or None,
            "text_nature": text_nature,
            "certainty": certainty,
            "query_language": query_iso,
            "query_language_label": _LANG_LABELS.get(query_iso, query_iso),
            "cross_language_query": detected_iso != query_iso and query_iso != "desconhecido",
            "limitations": limitations,
            "relevant_variants": [],
        }

        ctx.findings["language"] = result

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=[
                f"Idioma da fonte: {result['language_label']} (certeza: {certainty:.0%}).",
                f"Idioma da query: {result['query_language_label']}.",
                "Busca multilíngue relevante." if result["cross_language_query"] else "Busca no mesmo idioma.",
            ],
            warnings=warnings,
        )
