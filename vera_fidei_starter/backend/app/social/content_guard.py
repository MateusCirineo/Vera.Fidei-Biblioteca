from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable

from app.social.post_model import SocialPostCandidate, ValidationReport


_SPACE_RE = re.compile(r"\s+")
_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")
_EDITORIAL_PATTERNS = (
    re.compile(r"\b(?:índice|sumário|table of contents|contents)\b", re.I),
    re.compile(r"\b(?:apresentação|introdução|bibliografia|notas complementares)\b", re.I),
    re.compile(r"(?:\.{4,}|_{4,}|-{6,})"),
)
_TOC_DENSITY_RE = re.compile(
    r"(?:\b(?:livro|cap[ií]tulo|salmo|serm[aã]o)\b[^.!?]{0,45}\b\d{1,4}\b){4,}",
    re.I,
)
_FOOTNOTE_RUN_RE = re.compile(r"(?:^|\s)(?:\d{1,3}\s+){6,}")

# Conteúdo que o usuário informou já ter publicado manualmente. A checagem é
# feita por fragmentos normalizados, portanto continua funcionando mesmo que o
# OCR altere pontuação ou quebras de linha.
_MANUAL_BLOCKED_FRAGMENTS = (
    "tens os apostolos por proximos tens os martires por proximos",
    "e preciso suplicar em nosso favor aos anjos",
    "podem rogar por nossos pecados aqueles que com o proprio sangue",
)

_THEOLOGICAL_TERMS = (
    "comunhão dos santos",
    "ressurreição da carne",
    "livre-arbítrio",
    "vida eterna",
    "misericórdia",
    "intercessão",
    "ressurreição",
    "encarnação",
    "eucaristia",
    "sacerdócio",
    "apóstolos",
    "mártires",
    "caridade",
    "salvação",
    "redenção",
    "trindade",
    "batismo",
    "humildade",
    "santidade",
    "sabedoria",
    "justiça",
    "oração",
    "pecados",
    "pecado",
    "virtude",
    "esperança",
    "graça",
    "igreja",
    "anjos",
    "alma",
    "Cristo",
    "Deus",
    "fé",
)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("‐", "-").replace("‑", "-").replace("—", "-")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return _SPACE_RE.sub(" ", value).strip()


def same_author(left: str, right: str) -> bool:
    a, b = normalize_text(left), normalize_text(right)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def quote_fingerprint(
    *, chunk_id: int, author: str, work_title: str, quote: str
) -> str:
    payload = "|".join(
        (str(chunk_id), normalize_text(author), normalize_text(work_title), normalize_text(quote))
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_manually_blocked(text: str) -> bool:
    normalized = normalize_text(text)
    return any(fragment in normalized for fragment in _MANUAL_BLOCKED_FRAGMENTS)


def looks_like_editorial_noise(text: str) -> bool:
    clean = _SPACE_RE.sub(" ", text or "").strip()
    if len(clean) < 160:
        return True
    prefix = clean[:900]
    if any(pattern.search(prefix) for pattern in _EDITORIAL_PATTERNS):
        return True
    if _TOC_DENSITY_RE.search(prefix) or _FOOTNOTE_RUN_RE.search(prefix):
        return True
    alpha = sum(ch.isalpha() for ch in clean)
    if alpha / max(1, len(clean)) < 0.62:
        return True
    sentence_marks = sum(clean.count(mark) for mark in ".!?")
    return sentence_marks < 2


def clean_ocr_text(text: str) -> str:
    value = (text or "").replace("\u00ad", "")
    # Hífens introduzidos na quebra de linha/página: "dife- rença".
    value = re.sub(r"(?<=[A-Za-zÀ-ÿ])[-‐‑]\s+(?=[a-zà-ÿ])", "", value)
    value = _SPACE_RE.sub(" ", value).strip()
    # Número de nota colado ao fim da frase: "teu.56".
    value = re.sub(r"(?<=[.!?])\d{1,3}(?=\s|$)", "", value)
    return value


def extract_coherent_passage(text: str, *, min_chars: int = 360, max_chars: int = 980) -> str:
    """Extrai frases completas sem fabricar ou misturar conteúdo.

    O trecho começa e termina em limite de sentença. Cabeçalhos de índice,
    bibliografia e blocos de notas são recusados.
    """

    clean = clean_ocr_text(text)
    if looks_like_editorial_noise(clean):
        return ""

    # Um chunk pode começar na continuação da página anterior. Não transforma
    # esse fragmento em citação: começa na primeira frase completa seguinte.
    if clean and clean[0].islower():
        boundary = re.search(r"[.!?…]\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", clean)
        if boundary:
            clean = clean[boundary.end():].strip()

    protected = re.sub(r"\b(Ag|Ev)\.", r"\1§", clean)
    sentences = [s.replace("§", ".").strip() for s in _SENTENCE_RE.split(protected) if s.strip()]
    best = ""
    best_score = float("-inf")
    for start in range(len(sentences)):
        parts: list[str] = []
        for sentence in sentences[start:]:
            candidate = " ".join(parts + [sentence]).strip()
            if len(candidate) > max_chars:
                break
            parts.append(sentence)
            if len(candidate) >= min_chars and not looks_like_editorial_noise(candidate):
                if re.search(r"\b(?:Ag|Ev)\.", candidate):
                    continue
                # Prefere um bloco teologicamente substantivo e de tamanho
                # próximo ao exemplo. O início numerado de uma seção recebe um
                # pequeno bônus por formar uma unidade editorial completa.
                score = len(pick_highlight_terms(candidate)) * 80
                score -= abs(len(candidate) - 700)
                if re.match(r"^\d{1,3}\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]", candidate):
                    score += 35
                if score > best_score:
                    best = candidate
                    best_score = score
    return best


def pick_highlight_terms(text: str, max_terms: int = 6) -> list[str]:
    normalized = normalize_text(text)
    positions: list[tuple[int, str]] = []
    for term in _THEOLOGICAL_TERMS:
        pos = normalized.find(normalize_text(term))
        if pos >= 0:
            positions.append((pos, term))
    positions.sort(key=lambda item: (item[0], -len(item[1])))
    selected: list[str] = []
    for _, term in positions:
        term_norm = normalize_text(term)
        if any(term_norm in normalize_text(existing) or normalize_text(existing) in term_norm for existing in selected):
            continue
        selected.append(term)
        if len(selected) >= max_terms:
            break
    return selected


def validate_candidate(
    candidate: SocialPostCandidate,
    *,
    expected_author: str | None = None,
    published_fingerprints: Iterable[str] = (),
) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    if candidate.chunk_id <= 0 or candidate.book_id <= 0:
        errors.append("fonte sem chunk_id/book_id válido")
    if not candidate.author.strip():
        errors.append("autor ausente")
    if expected_author and not same_author(expected_author, candidate.author):
        errors.append("autor solicitado não corresponde ao autor da fonte")
    if not candidate.work_title.strip():
        errors.append("obra ausente")
    if not candidate.quote.strip():
        errors.append("citação ausente")
    elif looks_like_editorial_noise(candidate.quote):
        errors.append("trecho parece índice, introdução, notas ou OCR inadequado")
    if is_manually_blocked(candidate.quote):
        errors.append("trecho já publicado manualmente e bloqueado pela política")
    if not candidate.source_fingerprint:
        errors.append("impressão digital da fonte ausente")
    elif candidate.source_fingerprint in set(published_fingerprints):
        errors.append("trecho já publicado")
    if candidate.book_file_id is None or candidate.pdf_page is None:
        errors.append("arquivo/página da fonte ausente")
    if not candidate.edition_label and not candidate.collection:
        errors.append("edição/coleção ausente")
    if not candidate.chapter_or_section:
        warnings.append("capítulo/seção indisponível; a referência usará a página")
    if not candidate.original_text.strip():
        warnings.append("texto original indisponível; somente a edição em português será exibida")

    return ValidationReport(ok=not errors, errors=errors, warnings=warnings)
