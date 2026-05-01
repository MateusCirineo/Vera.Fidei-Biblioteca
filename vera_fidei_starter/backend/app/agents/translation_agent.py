from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from app.agents.base import BaseAgent, AgentResult, PipelineContext


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _key_words(text: str, min_len: int = 5) -> set[str]:
    return set(re.findall(rf"\b\w{{{min_len},}}\b", _normalize(text)))


def _evaluate_translation(
    original_latin: str,
    db_translation: str,
    user_quote: str,
) -> dict:
    """
    Tripartite evaluation:
      1. Content correspondence — key concepts of the original reflected in the DB translation
      2. Semantic preservation — the DB translation matches the user quote in meaning
      3. Absence of relevant additions — neither DB translation nor user quote adds concepts absent from original
    """
    orig_words = _key_words(original_latin)
    db_words = _key_words(db_translation)
    user_words = _key_words(user_quote)

    # 1. Content correspondence (DB translation vs. original)
    #    Latin/Portuguese share few root words; we use sequence similarity instead of word overlap
    content_sim = SequenceMatcher(None, _normalize(original_latin[:500]), _normalize(db_translation[:500])).ratio()
    # Boost: even a 0.15 ratio is meaningful for Latin→Portuguese
    content_ok = content_sim >= 0.12

    # 2. Semantic preservation (user quote vs. DB translation)
    semantic_sim = SequenceMatcher(None, _normalize(user_quote), _normalize(db_translation)).ratio()
    semantic_ok = semantic_sim >= 0.55

    # 3. Absence of relevant additions
    #    Extra long words in user quote not in DB translation may indicate additions
    extra_in_user = user_words - db_words
    added_concepts = [w for w in extra_in_user if len(w) >= 7]
    no_additions = len(added_concepts) <= 2

    problems: list[str] = []
    if not content_ok:
        problems.append("Baixa correspondência entre o original e a tradução no corpus.")
    if not semantic_ok:
        problems.append(
            f"A citação fornecida difere significativamente da tradução no corpus "
            f"(similaridade: {semantic_sim:.0%})."
        )
    if not no_additions:
        sample = ", ".join(sorted(added_concepts)[:4])
        problems.append(f"Possíveis acréscimos na citação fornecida não presentes na tradução do corpus: {sample}.")

    if not problems:
        fidelity_verdict = "tradução fiel — correspondência de conteúdo, semântica preservada, sem acréscimos relevantes"
        correspondence = "alta"
    elif len(problems) == 1 and not no_additions:
        fidelity_verdict = "tradução aceitável com possíveis adaptações"
        correspondence = "média"
    elif semantic_ok and not content_ok:
        fidelity_verdict = "paráfrase — sentido preservado mas distante do texto original"
        correspondence = "média"
    else:
        fidelity_verdict = "tradução imprecisa ou paráfrase livre — não confirma a citação fornecida"
        correspondence = "baixa"

    return {
        "content_similarity": round(content_sim, 3),
        "semantic_similarity": round(semantic_sim, 3),
        "added_concepts": added_concepts[:6],
        "correspondence_level": correspondence,
        "detected_problems": problems,
        "fidelity_verdict": fidelity_verdict,
    }


class TranslationAgent(BaseAgent):
    name = "translation_agent"

    def run(self, ctx: PipelineContext) -> AgentResult:
        source = ctx.findings.get("source", {})
        chunk_id = source.get("chunk_id")
        user_quote = ctx.findings.get("quote") or ctx.user_task
        original_text = source.get("located_excerpt", "")

        if not chunk_id or source.get("status") == "not_found":
            return AgentResult(
                agent_name=self.name,
                status="ok",
                data={
                    "translation_found": False,
                    "original_text": original_text[:350] if original_text else None,
                    "translation_text": None,
                    "fidelity_verdict": "análise não aplicável — fonte não localizada",
                    "detected_problems": [],
                },
                notes=["Fonte não localizada; análise de tradução não aplicável."],
            )

        try:
            from models.database import SessionLocal, Translation
        except ImportError as exc:
            return AgentResult(
                agent_name=self.name,
                status="error",
                data={},
                notes=[],
                warnings=[f"Módulo DB indisponível: {exc}"],
            )

        try:
            with SessionLocal() as db:
                translations = (
                    db.query(Translation)
                    .filter(Translation.chunk_id == chunk_id)
                    .all()
                )
        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                status="error",
                data={},
                notes=[],
                warnings=[f"Falha ao consultar traduções: {exc}"],
            )

        if not translations:
            return AgentResult(
                agent_name=self.name,
                status="ok",
                data={
                    "translation_found": False,
                    "original_text": original_text[:350],
                    "translation_text": None,
                    "fidelity_verdict": "sem tradução registrada no corpus para este trecho",
                    "detected_problems": [],
                    "note": "A citação não pôde ser comparada com tradução de referência.",
                },
                notes=["Nenhuma tradução no DB para o chunk encontrado."],
            )

        # Prefer Portuguese; fall back to first available
        pt_translation = next(
            (t for t in translations if t.language in ("pt", "por", "português")),
            translations[0],
        )

        evaluation = _evaluate_translation(original_text, pt_translation.text, user_quote)

        result = {
            "translation_found": True,
            "original_text": original_text[:350],
            "translation_text": pt_translation.text[:350],
            "translation_language": pt_translation.language,
            "translator": pt_translation.translator,
            "edition_label": pt_translation.edition_label,
            **evaluation,
        }

        ctx.findings["translation"] = result

        return AgentResult(
            agent_name=self.name,
            status="ok",
            data=result,
            notes=[
                f"Tradução encontrada no corpus (chunk {chunk_id}).",
                f"Veredito: {evaluation['fidelity_verdict']}",
            ],
        )
