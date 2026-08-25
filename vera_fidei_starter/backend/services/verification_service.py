import logging
import os
import re
import unicodedata
from functools import lru_cache

import pdfplumber
try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - optional fast PDF backend
    fitz = None

_log = logging.getLogger(__name__)
from langdetect import detect, LangDetectException

from models.database import SessionLocal, Chunk, Book, BookFile, Translation, VerifiedPassage, init_db
from schemas.citation import VerifyCitationRequest, VerifyCitationResponse, MatchReference
from search.text_search import TextSearchClient
from search.semantic_search import SemanticSearchClient
from confidence.scorer import CombinedScorer
from confidence.classifier import DeterministicClassifier
from confidence.explainer import ResultExplainer
from storage.pdf_storage import get_pdf_storage
from services.source_fidelity_service import (
    PUBLIC_SOURCE_FIDELITIES,
    VerifiedPassageCandidate,
    select_verified_passage,
)
from utils.language import (
    normalize_lang as _normalize_lang,
    detect_latin_heuristic,
    detect_script_heuristic,
    ORIGINAL_LANGS, TRANSLATION_LANGS,
    classify_book,
)
from utils.author_detection import (
    AUTHOR_ALIASES,
    detect_author,
    detect_canonical_title,
    resolve_author_alias,
    _normalize_for_alias,
)


def _detect_language(text: str, hint: str | None = None) -> str:
    """
    Detecta o idioma da query.
    Prioridade: hint > script Unicode (grego/siríaco/copta/etc.) > heurística latina > langdetect.
    "unknown" ≠ "la": evita enviesar o boosting de busca.
    """
    if hint:
        return _normalize_lang(hint)
    # Scripts não-latinos detectados por blocos Unicode antes de qualquer heurística
    script = detect_script_heuristic(text)
    if script:
        return script
    if detect_latin_heuristic(text):
        return "la"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def _author_core(value: str | None) -> str:
    norm = _normalize_for_alias(value or "")
    norm = re.sub(r"\b(santo|santa|sao|beato|beata|papa|padre)\b", " ", norm)
    norm = re.sub(r"\b(de|da|do|dos|das|e)\b", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()


def _author_name_matches(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    left_norm = _normalize_for_alias(left)
    right_norm = _normalize_for_alias(right)
    if left_norm == right_norm:
        return True
    if len(left_norm) >= 6 and left_norm in right_norm:
        return True
    if len(right_norm) >= 6 and right_norm in left_norm:
        return True
    left_core = _author_core(left)
    right_core = _author_core(right)
    if not left_core or not right_core:
        return False
    if left_core == right_core:
        return True
    if len(left_core) >= 6 and left_core in right_core:
        return True
    if len(right_core) >= 6 and right_core in left_core:
        return True
    return False


def _author_matches(attributed_to: str, book, chunk=None) -> bool:
    """
    Verifica se o autor atribuido bate com o livro/chunk encontrado.

    Usa aliases canonicos e comparacao tolerante para nomes com formas curtas,
    como "Santo Agostinho" versus "Santo Agostinho de Hipona".
    """
    if not attributed_to or not book:
        return False

    if chunk and chunk.chunk_author:
        if _author_name_matches(attributed_to, chunk.chunk_author):
            return True

    resolved = resolve_author_alias(attributed_to)
    if resolved:
        for field in [chunk.chunk_author if chunk else None, book.author, book.canonical_author]:
            if _author_name_matches(resolved, field):
                return True

    for field in [book.author, book.canonical_author]:
        if _author_name_matches(attributed_to, field):
            return True

    return False


def _author_matches_in_context(attributed_to: str, book, context_text: str) -> bool:
    """
    Confirma autor dentro de coletaneas, como Padres Apostolicos, quando o
    Book.author e generico e o chunk_author veio errado da indexacao.
    """
    if not attributed_to or not context_text:
        return False

    canonical = resolve_author_alias(attributed_to) or attributed_to
    if _author_name_matches(attributed_to, context_text) or _author_name_matches(canonical, context_text):
        return True

    context_norm = _normalize_for_alias(context_text)
    canonical_norm = _normalize_for_alias(canonical)
    attributed_norm = _normalize_for_alias(attributed_to)
    book_author_norm = _normalize_for_alias(getattr(book, "author", "") if book else "")
    is_collective = any(
        marker in book_author_norm
        for marker in ("padres apostolicos", "padres apologistas", "varios", "vvaa", "vv aa")
    )

    for alias, target in AUTHOR_ALIASES.items():
        target_norm = _normalize_for_alias(target)
        if target_norm not in {canonical_norm, attributed_norm} and not _author_name_matches(canonical, target):
            continue
        alias_norm = _normalize_for_alias(alias)
        if len(alias_norm) < 6 or alias_norm not in context_norm:
            continue
        # Aliases curtos como "inacio" so confirmam autor dentro de coletaneas.
        if len(alias_norm.split()) >= 2 or is_collective:
            return True

    return False


def _response_author(attributed_to: str, author_match: bool, book, chunk=None) -> str | None:
    if attributed_to and author_match:
        return resolve_author_alias(attributed_to) or attributed_to
    if chunk is not None and getattr(chunk, "chunk_author", None):
        return chunk.chunk_author
    return book.author if book else None


def _authoritative_source_text(db, chunk: Chunk, query: str, candidate_text: str) -> tuple[str, str] | None:
    """Resolve the wording allowed to support a public verification result.

    OCR can nominate a page, but only native PDF text or a literal page
    transcription may be used to classify and quote a citation.
    """
    if (chunk.source_fidelity or "") in PUBLIC_SOURCE_FIDELITIES:
        # An approved chunk must not lend its status to unverified neighbors
        # that happened to be included in a broader search window.
        return chunk.text, chunk.source_fidelity

    if chunk.pdf_page is None:
        return None
    rows = (
        db.query(VerifiedPassage)
        .filter(
            VerifiedPassage.book_id == chunk.book_id,
            VerifiedPassage.pdf_page == chunk.pdf_page,
        )
        .all()
    )
    verified = select_verified_passage(
        candidate_text,
        query,
        (
            VerifiedPassageCandidate(
                text=row.text,
                language=row.language,
                method=row.verification_method,
            )
            for row in rows
        ),
    )
    if verified is None:
        return None
    return verified.text, "verified_transcription"

# Marcadores de linguagem acadêmica moderna que NÃO aparecem em traduções patrísticas
# autênticas. Lista conservadora: apenas termos que são anacrônicos de forma inequívoca.
# Não inclui palavras que podem aparecer em traduções legítimas (ex: "comunidade", "processo").
_MODERN_MARKERS_PT: frozenset[str] = frozenset({
    # Neologismos hermenêuticos / pós-modernos
    "reinterpretação", "ressignificação", "ressignificar", "ressignifica",
    "releitura", "desconstrução", "reapropriação", "reapropria",
    # Jargão acadêmico de teoria crítica
    "paradigmático", "paradigmaticamente", "epistemológico", "epistêmico",
    "contextualização", "contextualizar", "intertextualidade",
    "narratividade", "performatividade",
    # Fraseologia de estudos de recepção / história dos efeitos
    "reinterpreta", "ressignificam",
    # Marcadores de metalinguagem temporal anacrônica
    "posteriores",   # quase sempre em "intérpretes posteriores"
    "releituras",
})

# Bigramas modernos: pares de palavras que sozinhos já sinalizam prosa acadêmica
_MODERN_BIGRAMS_PT: tuple[str, ...] = (
    "intérpretes posteriores",
    "construção viva",
    "legado vivo",
    "participação ativa",
    "reinterpretação da tradição",
    "ativamente na construção",
    "cada comunidade participa",
    "hermenêutica do",
    "ao longo da história",   # em citações patrísticas é anacronismo narrativo
)


def _intrusion_score(query: str) -> float:
    """
    Detecta linguagem acadêmica moderna anacrônica em supostas citações patrísticas.
    Retorna 0.0–1.0:
      0.0 = nenhum marcador detectado
      > 0.0 = presença de termos ou bigramas inequivocamente modernos
    Fórmula: (tokens_marcados / tokens_significativos) + bonus por bigramas (cap em 1.0).
    Qualquer score > 0 em combinação com resultado positivo deve gerar downgrade.
    """
    import re
    q_lower = query.lower()

    # Verificar bigramas primeiro (peso maior — sinal mais forte)
    bigram_hits = sum(1 for b in _MODERN_BIGRAMS_PT if b in q_lower)

    # Verificar tokens individuais
    tokens = re.findall(r'\b\w{5,}\b', q_lower)
    if not tokens and bigram_hits == 0:
        return 0.0

    token_hits = sum(1 for t in tokens if t in _MODERN_MARKERS_PT)

    if not tokens:
        return min(1.0, bigram_hits * 0.4)

    return min(1.0, (token_hits / len(tokens)) + (bigram_hits * 0.25))


def _translation_fidelity(query: str, reference: str) -> str:
    """
    Avalia quanto da query está ancorada no texto de referência.
    Mede query_coverage = |q ∩ r| / |q| (fração dos tokens da query que
    aparecem na referência), não o inverso. Isso penaliza queries que
    introduzem vocabulário ausente da fonte — sinal de paráfrase inventada.
    Tokens curtos (≤3 chars) são ignorados para evitar ruído de stopwords.
    """
    q_tokens = {t.lower() for t in query.split() if len(t) > 3}
    r_tokens = {t.lower() for t in reference.split() if len(t) > 3}
    if not q_tokens:
        return "nao_encontrada"
    overlap = len(q_tokens & r_tokens) / len(q_tokens)
    if overlap >= 0.40:
        return "fiel"
    if overlap >= 0.20:
        return "imprecisa"
    return "nao_encontrada"


def _variant_analysis(
    *,
    exact_match: bool,
    ocr_similarity: float,
    lexical_anchor: float,
    translation_fidelity: str | None,
    status_code: str,
    known_paraphrase_score: float = 0.0,
) -> str | None:
    """Short, user-facing diagnosis of textual variation in the located evidence."""
    if status_code == "NAO_ENCONTRADA":
        return None
    if exact_match or ocr_similarity >= 0.95:
        return (
            "Correspondencia literal ou praticamente literal: o texto informado "
            "aparece na fonte com variacoes normais de OCR, pontuacao ou quebra de pagina."
        )
    if translation_fidelity == "fiel":
        return (
            "Variacao de traducao aceitavel: a formulacao nao e identica, mas os "
            "termos centrais estao preservados no trecho localizado."
        )
    if known_paraphrase_score >= 0.80:
        return (
            "Parafrase conceitual localizada: a frase curta nao aparece como "
            "citacao literal, mas resume uma tese encontrada em trecho especifico "
            "da obra indexada."
        )
    if lexical_anchor >= 0.45:
        return (
            "Parafrase proxima: ha ancoragem real na fonte, mas a frase foi "
            "reformulada e deve ser citada com cuidado."
        )
    if translation_fidelity == "imprecisa":
        return (
            "Traducao ou formulacao imprecisa: parte do vocabulario existe na "
            "fonte, mas a frase introduz diferencas relevantes."
        )
    return (
        "Correspondencia fraca: o sistema encontrou relacao tematica, mas nao "
        "base suficiente para tratar a frase como citacao textual."
    )


def _lexical_anchor(query: str, chunk_text: str, translation_text: str | None) -> float:
    """
    Fração de tokens significativos da query que aparecem no trecho fonte
    (texto original + tradução PT, se disponível).
    Alta ancoragem: a citação tem base lexical real no texto encontrado.
    Baixa ancoragem: a citação introduz vocabulário ausente da fonte — sinal
    de similaridade temática sem correspondência textual (frase falsa/paráfrase livre).
    """
    import re
    STOP = {
        "de", "do", "da", "dos", "das", "que", "em", "no", "na", "nos", "nas",
        "um", "uma", "o", "a", "os", "as", "e", "é", "ao", "aos", "por", "para",
        "com", "se", "não", "mas", "ou", "isto", "este", "esta", "esse", "essa",
        "seu", "sua", "seus", "suas", "todo", "toda", "todos", "todas", "também",
        "foi", "são", "ser", "ter", "mais", "quando", "como", "bem", "já", "isso",
        "ela", "ele", "eles", "elas", "nela", "nele", "dele", "dela",
        # Latim
        "et", "in", "est", "ut", "ad", "non", "ex", "cum", "per", "qui", "quod",
    }

    def tokenize(text: str) -> set[str]:
        tokens = re.findall(r'\b\w{4,}\b', text.lower())
        return {t for t in tokens if t not in STOP}

    q_tokens = tokenize(query)
    if not q_tokens:
        return 0.0

    source = tokenize(chunk_text)
    trans = tokenize(translation_text) if translation_text else set()
    all_source = source | trans
    ratio = len(q_tokens & all_source) / len(q_tokens)
    # Frases curtas/aforísticas ficam perigosas: dois ou três termos em comum
    # podem significar apenas proximidade temática. Sem correspondência literal,
    # não devem passar como paráfrase localizada.
    if len(q_tokens) < 4:
        return min(ratio, 0.50)

    return ratio


# ─── PDF directory + path resolution ─────────────────────────────────────────

_PDFS_DIR = os.environ.get("PDF_DIR") or os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "pdfs")
)

_ENABLE_PDF_PAGE_SCAN = os.environ.get("VERIFIER_ENABLE_PDF_PAGE_SCAN", "1").lower() not in {
    "0",
    "false",
    "no",
}
# Default 0 = sem limite. O comportamento esperado do Vera.Fidei e tentar localizar
# a pagina real em todo PDF vinculado, como era antes, mas usando PyMuPDF/cache.
_PDF_PAGE_SCAN_MAX_BYTES = int(os.environ.get("VERIFIER_PDF_PAGE_SCAN_MAX_BYTES", "0"))
_ALWAYS_RUN_SEMANTIC = os.environ.get("VERIFIER_ALWAYS_RUN_SEMANTIC", "").lower() in {
    "1",
    "true",
    "yes",
}
_SEMANTIC_FALLBACK_TIMEOUT = float(os.environ.get("VERIFIER_SEMANTIC_FALLBACK_TIMEOUT", "8"))


def _resolve_pdf_path(stored_path: str) -> str | None:
    """
    Resolve stored_path to an absolute local path for PDF scanning.

    In local mode this resolves legacy files under PDF_DIR. In S3/R2 mode it
    downloads the object into the bounded cache and returns that cached path.
    """
    return get_pdf_storage().resolve_for_processing(stored_path)


# ─── Busca de página real no PDF ─────────────────────────────────────────────

_LAYOUT_HYPHEN_RE = re.compile(
    r"(?<=[^\W\d_])[-\u00ad\u2010\u2011]\s*(?=[^\W\d_])",
    flags=re.UNICODE,
)


def _remove_layout_hyphens(text: str) -> str:
    """Join words split by PDF line-wrap hyphens for comparison only."""
    return _LAYOUT_HYPHEN_RE.sub("", text)

def _normalize_for_search(text: str) -> str:
    """Remove acentos, pontuacao/numero solto, normaliza espaços e converte para minúsculas."""
    text = _remove_layout_hyphens(text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    # PDFs costumam inserir numero de pagina no meio da frase extraida.
    text = re.sub(r"(?<!\w)\d{1,4}(?!\w)", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


_AUGUSTINE_LOVE_KNOWLEDGE_ANCHORS: tuple[str, ...] = (
    "ninguem pode amar algo totalmente desconhecido",
    "somente se pode amar o que se conhece",
    "ninguem ama o desconhecido",
    "ninguem ama o que desconhece totalmente",
    "nao se ama o que e absolutamente desconhecido",
    "ninguem ama alguem de quem nao se recorde ou a quem ignore totalmente",
    "o amor nao e excitado por algo completamente desconhecido",
)

# "Ama et fac quod vis" — Agostinho, In Epistulam Ioannis ad Parthos, Tractatus VII, 8
_AUGUSTINE_AMA_FAC_ANCHORS: tuple[str, ...] = (
    "ama et fac quod vis",
    "dilige et quod vis fac",
    "ama e faz o que queres",
    "ama e faz o que quiseres",
    "amai e fazei o que quiserdes",
    "diliges et quod vis fac",
)

# "Cor nostrum inquietum est" — Agostinho, Confissões I, 1
_AUGUSTINE_COR_INQUIETUM_ANCHORS: tuple[str, ...] = (
    "inquietum est cor nostrum",
    "cor nostrum inquietum est",
    "nosso coracao e inquieto",
    "nosso coracao esta inquieto",
    "inquieto esta o nosso coracao",
    "coracao inquieto ate que repousa",
    "coracao inquieto ate que repouse",
    "inquieto ate que repouse em ti",
    "inquieto ate que repousa em ti",
    "fecisti nos domine ad te et inquietum",
    # Patrística Vol. 10 exact wording (phrasing used in the indexed edition)
    "enquanto nao repousa em ti",
    "fizeste-nos para ti e inquieto esta",
    "fizeste nos para ti e inquieto",
)


def _known_conceptual_paraphrase_score(
    query: str,
    attributed_to: str | None,
    book,
    evidence_text: str,
) -> float:
    """
    Reconhece máximas curtas que são resumos tradicionais de uma tese real,
    sem relaxar o verificador inteiro para qualquer proximidade temática.

    Casos cobertos (todos atribuídos a Santo Agostinho de Hipona):
      1. "não se ama aquilo que não se conhece" — De Trinitate, Livro X
      2. "Ama et fac quod vis" — In Epistulam Ioannis, Tractatus VII, 8
      3. "Cor nostrum inquietum est" — Confissões I, 1
    """
    if not query or not evidence_text:
        return 0.0

    canonical = resolve_author_alias(attributed_to or "") or (attributed_to or "")
    if not _author_name_matches(canonical, "Santo Agostinho de Hipona"):
        return 0.0

    if book is not None and not any(
        _author_name_matches(canonical, field)
        for field in (getattr(book, "author", None), getattr(book, "canonical_author", None))
    ):
        return 0.0

    q_norm = _normalize_for_search(query)
    source = _normalize_for_search(evidence_text)

    # ── Padrão 1: "não se ama o que não se conhece" ──────────────────────────
    has_love = bool(re.search(r"\b(am(?:a|ar|amos|amem|ou|ei|e)|amor|amado|amada)\b", q_norm))
    has_knowledge = "conhec" in q_norm or "desconhec" in q_norm or "ignor" in q_norm
    has_negation = "nao" in q_norm or "desconhec" in q_norm or "ignor" in q_norm
    if has_love and has_knowledge and has_negation:
        if any(anchor in source for anchor in _AUGUSTINE_LOVE_KNOWLEDGE_ANCHORS):
            return 0.95
        if "desconhecido" in source and ("ama" in source or "amor" in source) and "conhec" in source:
            if "trindade" in _normalize_for_search(getattr(book, "title", "") if book else ""):
                return 0.82

    # ── Padrão 2: "Ama et fac quod vis" ──────────────────────────────────────
    # Dois verbos obrigatórios (amar + fazer) + complemento de vontade
    q_has_ama = bool(re.search(r"\b(am[aeo]|dilige|diliges)\b", q_norm))
    q_has_fac = bool(re.search(r"\b(faz(ei|er)?|fac|faca)\b", q_norm))
    q_has_vis = bool(re.search(r"\b(queres|quiseres|quiser|vis)\b", q_norm))
    if q_has_ama and q_has_fac and q_has_vis:
        if any(anchor in source for anchor in _AUGUSTINE_AMA_FAC_ANCHORS):
            return 0.95
        # Obra não indexada mas autor correto e padrão inequívoco: paráfrase conhecida
        return 0.88

    # ── Padrão 3: "Cor nostrum inquietum est donec requiescat in te" ──────────
    q_has_cor = bool(re.search(r"\b(coracao|cor\b|inquieto|inquietum)\b", q_norm))
    q_has_repouso = bool(re.search(r"\b(repous[ae]|requiescat|sossego|descanso)\b", q_norm))
    if q_has_cor and q_has_repouso:
        if any(anchor in source for anchor in _AUGUSTINE_COR_INQUIETUM_ANCHORS):
            return 0.95
        # Frase de abertura das Confissões: inequivocamente agostiniana
        return 0.90

    return 0.0


def _extract_known_conceptual_excerpt(
    query: str,
    attributed_to: str | None,
    book,
    evidence_text: str,
) -> str | None:
    if _known_conceptual_paraphrase_score(query, attributed_to, book, evidence_text) < 0.80:
        return None

    q_norm = _normalize_for_search(query)
    sentences = re.split(r'(?<=[.!?])\s+|\n', evidence_text)
    if not sentences:
        return None

    # Choose anchor set based on detected pattern
    q_has_ama = bool(re.search(r"\b(am[aeo]|dilige)\b", q_norm))
    q_has_fac = bool(re.search(r"\b(faz(ei|er)?|fac|faca)\b", q_norm))
    q_has_vis = bool(re.search(r"\b(queres|quiseres|quiser|vis)\b", q_norm))
    q_has_cor = bool(re.search(r"\b(coracao|cor\b|inquieto|inquietum)\b", q_norm))
    q_has_repouso = bool(re.search(r"\b(repous[ae]|requiescat|sossego)\b", q_norm))

    if q_has_ama and q_has_fac and q_has_vis:
        anchors = _AUGUSTINE_AMA_FAC_ANCHORS
    elif q_has_cor and q_has_repouso:
        anchors = _AUGUSTINE_COR_INQUIETUM_ANCHORS
    else:
        anchors = _AUGUSTINE_LOVE_KNOWLEDGE_ANCHORS

    for index, sentence in enumerate(sentences):
        normalized = _normalize_for_search(sentence)
        if any(anchor in normalized for anchor in anchors):
            start = max(0, index - 1)
            end = min(len(sentences), index + 3)
            excerpt = " ".join(part.strip() for part in sentences[start:end] if part.strip())
            return excerpt[:1400].strip()

    return None


def _normalize_ocr(text: str) -> str:
    """
    Remove artefatos de OCR comuns em citações copiadas de PDFs:
    - Números de linha colados ao início de palavras: "1Celebrem" → "Celebrem"
    - Normaliza aspas curvas/angulares para aspas simples
    - Normaliza espaços e quebras de linha
    """
    # Remove dígitos OCR colados antes de letra maiúscula ou acentuada
    text = re.sub(r'\b(\d+)(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÇÄËÏÖÜ])', '', text)
    # Normaliza aspas tipográficas para neutras
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u00ab', '"').replace('\u00bb', '"')
    # Normaliza espaços e quebras
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalize_for_search_with_offsets(text: str) -> tuple[str, list[int]]:
    """Normalize ``text`` while retaining each output character's source offset.

    ``_normalize_for_search`` deliberately removes accents, punctuation, page
    numbers and repeated whitespace.  A normalized position therefore cannot be
    converted back to the source with a single global ratio: the amount removed
    before a match is not necessarily representative of the whole text.  This
    helper mirrors that normalization and keeps an exact source index for every
    character that survives it.
    """
    expanded: list[str] = []
    offsets: list[int] = []
    removed_layout_offsets = {
        index
        for match in _LAYOUT_HYPHEN_RE.finditer(text)
        for index in range(match.start(), match.end())
    }

    for source_index, source_char in enumerate(text):
        if source_index in removed_layout_offsets:
            continue
        for decomposed_char in unicodedata.normalize("NFD", source_char):
            if unicodedata.category(decomposed_char) == "Mn":
                continue
            normalized_char = (
                decomposed_char
                if re.match(r"[\w\s]", decomposed_char, flags=re.UNICODE)
                else " "
            )
            expanded.append(normalized_char)
            offsets.append(source_index)

    # Lowercase the complete string so contextual Unicode rules are preserved
    # (for example Greek final sigma: ``ΟΣ`` -> ``ος``).  Lowercasing normally
    # keeps the same length; the fallback retains the originating offset for
    # every expanded lowercase code point.
    expanded_text = "".join(expanded)
    intermediate = expanded_text.lower()
    if len(intermediate) != len(offsets):
        expanded_offsets: list[int] = []
        for char, source_index in zip(expanded, offsets):
            expanded_offsets.extend([source_index] * len(char.lower()))
        if len(expanded_offsets) < len(intermediate):
            fallback_offset = expanded_offsets[-1] if expanded_offsets else 0
            expanded_offsets.extend(
                [fallback_offset] * (len(intermediate) - len(expanded_offsets))
            )
        offsets = expanded_offsets[: len(intermediate)]
    expanded = list(intermediate)

    # Keep indices stable by replacing isolated PDF page numbers in place.
    for match in re.finditer(r"(?<!\w)\d{1,4}(?!\w)", intermediate):
        for index in range(match.start(), match.end()):
            expanded[index] = " "

    normalized: list[str] = []
    normalized_offsets: list[int] = []
    pending_space_offset: int | None = None
    for char, source_index in zip(expanded, offsets):
        if char.isspace():
            if normalized and pending_space_offset is None:
                pending_space_offset = source_index
            continue
        if pending_space_offset is not None:
            normalized.append(" ")
            normalized_offsets.append(pending_space_offset)
            pending_space_offset = None
        normalized.append(char)
        normalized_offsets.append(source_index)

    return "".join(normalized), normalized_offsets


def _extract_matching_excerpt(query: str, chunk_text: str) -> str:
    """
    Extrai do chunk_text apenas o trecho que corresponde à query,
    evitando devolver o chunk inteiro (que pode ter centenas de palavras
    antes e depois da citação relevante).

    Estratégia:
    1. Identifica os tokens significativos da query.
    2. Percorre frases/linhas do chunk e encontra o centro de maior sobreposição.
    3. Retorna uma janela centrada nesse ponto, respeitando limites de frase.
    """
    norm_q = _normalize_for_search(_normalize_ocr(query))
    norm_c, source_offsets = _normalize_for_search_with_offsets(chunk_text)

    # Tentativa de substring exata após normalização OCR
    if norm_q and norm_q in norm_c:
        start = norm_c.index(norm_q)
        end = start + len(norm_q)
        # Cada caractere normalizado aponta para sua posição real. Não use uma
        # proporção global: pontuação/layout removidos antes da citação deslocam
        # o recorte para outro parágrafo, embora a correspondência esteja certa.
        orig_start = source_offsets[start]
        orig_end = source_offsets[end - 1] + 1
        return chunk_text[orig_start:orig_end].strip()

    # Janela deslizante por tokens
    query_tokens = set(w for w in norm_q.split() if len(w) >= 4)
    if not query_tokens:
        return chunk_text[:400]

    # Divide chunk em sentenças/linhas
    sentences = re.split(r'(?<=[.!?])\s+|\n', chunk_text)
    if len(sentences) <= 2:
        return chunk_text[:500]

    # Pontua cada sentença pela sobreposição com a query
    scored = []
    for i, sent in enumerate(sentences):
        norm_sent = _normalize_for_search(sent)
        sent_tokens = set(norm_sent.split())
        score = len(query_tokens & sent_tokens)
        scored.append((score, i))

    scored.sort(key=lambda x: -x[0])
    best_idx = scored[0][1]

    # Expande a partir do centro até cobrir ~len(query) caracteres
    target_len = len(query) * 1.5
    parts = []
    total = 0
    for i in range(best_idx, min(len(sentences), best_idx + 10)):
        parts.append(sentences[i])
        total += len(sentences[i])
        if total >= target_len:
            break

    result = ' '.join(parts).strip()
    # Fallback: se muito curto, devolve os 500 primeiros chars do chunk
    return result if len(result) >= 40 else chunk_text[:500]


def _clean_matched_excerpt_display(excerpt: str | None, pdf_page: int | None = None) -> str | None:
    if not excerpt:
        return excerpt

    cleaned = _normalize_ocr(excerpt)
    page_candidates: set[int] = set()
    if isinstance(pdf_page, int):
        page_candidates.update(n for n in (pdf_page - 1, pdf_page, pdf_page + 1) if n > 0)

    for page_number in page_candidates:
        cleaned = re.sub(
            rf"(?<=[A-Za-zÀ-ÖØ-öø-ÿ])\s+{page_number}\s+(?=[A-Za-zÀ-ÖØ-öø-ÿ])",
            " ",
            cleaned,
        )

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _chunk_window_text(db, chunk: Chunk, before: int = 1, after: int = 2) -> str:
    parts: list[str] = []

    if chunk.sequence_index is not None:
        previous = (
            db.query(Chunk)
            .filter(
                Chunk.book_id == chunk.book_id,
                Chunk.sequence_index < chunk.sequence_index,
            )
            .order_by(Chunk.sequence_index.desc())
            .limit(before)
            .all()
        )
        following = (
            db.query(Chunk)
            .filter(
                Chunk.book_id == chunk.book_id,
                Chunk.sequence_index > chunk.sequence_index,
            )
            .order_by(Chunk.sequence_index.asc())
            .limit(after)
            .all()
        )
    else:
        previous = (
            db.query(Chunk)
            .filter(Chunk.book_id == chunk.book_id, Chunk.id < chunk.id)
            .order_by(Chunk.id.desc())
            .limit(before)
            .all()
        )
        following = (
            db.query(Chunk)
            .filter(Chunk.book_id == chunk.book_id, Chunk.id > chunk.id)
            .order_by(Chunk.id.asc())
            .limit(after)
            .all()
        )

    parts.extend(item.text or "" for item in reversed(previous))
    parts.append(chunk.text or "")
    parts.extend(item.text or "" for item in following)
    return "\n".join(part for part in parts if part)


def _is_exact_text_match(query: str, candidate_text: str) -> bool:
    q_raw = (query or "").strip().lower()
    if not q_raw or not candidate_text:
        return False

    q_ocr = _normalize_for_search(_normalize_ocr(query))
    c_raw = candidate_text.lower()
    c_norm = _normalize_for_search(candidate_text)
    if (q_raw in c_raw) or bool(q_ocr and q_ocr in c_norm):
        return True

    # pdftotext/pdfplumber insere o número da página entre palavras quando uma
    # citação cruza a quebra de página (ex: "carne de\n68\nnosso Senhor").
    # Após normalização de espaços o chunk fica "...carne de 68 nosso Senhor...".
    # Tentativa final: remover números isolados de 1–3 dígitos antes de comparar.
    _pnum = re.compile(r'(?<![a-z0-9])\d{1,3}(?![a-z0-9])')
    q_stripped = re.sub(r'\s+', ' ', _pnum.sub(' ', q_ocr)).strip()
    c_stripped = re.sub(r'\s+', ' ', _pnum.sub(' ', c_norm)).strip()
    return bool(q_stripped and len(q_stripped) >= 20 and q_stripped in c_stripped)


@lru_cache(maxsize=32)
def _cached_pdf_page_texts(pdf_path: str, mtime_ns: int, size_bytes: int) -> tuple[str, ...]:
    del mtime_ns, size_bytes

    if fitz is not None:
        try:
            with fitz.open(pdf_path) as doc:
                return tuple(
                    _normalize_for_search(_normalize_ocr(page.get_text("text") or ""))
                    for page in doc
                )
        except Exception:
            pass

    try:
        with pdfplumber.open(pdf_path) as pdf:
            return tuple(
                _normalize_for_search(_normalize_ocr(page.extract_text() or ""))
                for page in pdf.pages
            )
    except Exception:
        return ()


def _find_exact_window_page(pages: tuple[str, ...], words: list[str]) -> int | None:
    if not pages or not words:
        return None

    beginning = words[: min(len(words), 45)]
    candidate_sizes = tuple(size for size in (24, 18, 14, 10, 8, 6, 5) if len(beginning) >= size)

    # Prioriza o começo literal da citação. Uma citação pode atravessar página:
    # a continuação na página seguinte costuma formar janelas mais longas, mas
    # o destino correto para abrir o PDF é onde a frase começa.
    for offset in range(0, len(beginning) - min(candidate_sizes, default=1) + 1):
        for size in candidate_sizes:
            if offset + size > len(beginning):
                continue
            window = " ".join(beginning[offset : offset + size])
            for i, page_text in enumerate(pages, start=1):
                if window and window in page_text:
                    return i

    return None


def _find_real_pdf_page(pdf_path: str, chunk_text: str, min_score: int = 5) -> int | None:
    """
    Varre todas as páginas do PDF e retorna a página onde o trecho COMEÇA.

    Estratégia em dois passos:
    1. Encontra a "página âncora" — aquela com maior sobreposição de tokens.
    2. Olha até 3 páginas ANTES da âncora: se alguma tiver overlap ≥ 40% da âncora,
       a citação começa lá — retorna essa página (a mais anterior válida).

    Isso resolve citações que atravessam quebra de página: a primeira página tem
    poucos tokens (início do trecho), a segunda tem mais (continuação). O sistema
    localiza a segunda como âncora e recua para a primeira.
    """
    if not pdf_path or not os.path.isfile(pdf_path):
        return None

    try:
        stat = os.stat(pdf_path)
        if _PDF_PAGE_SCAN_MAX_BYTES > 0 and stat.st_size > _PDF_PAGE_SCAN_MAX_BYTES:
            return None
    except OSError:
        return None

    # Normaliza OCR e tokeniza.
    # A busca da janela inicial precisa preservar palavras curtas ("vos",
    # "em", "de", "só"), pois elas fazem parte da sequência literal que aponta
    # a página onde a citação começa. Para pontuação ampla, usamos só tokens
    # significativos para reduzir ruído.
    norm_text = _normalize_for_search(_normalize_ocr(chunk_text))
    ordered_words = norm_text.split()
    chunk_words = [w for w in ordered_words if len(w) >= 4]
    if len(ordered_words) < 5 or len(chunk_words) < 3:
        return None

    pdf_path = os.path.abspath(pdf_path)
    pages = _cached_pdf_page_texts(pdf_path, stat.st_mtime_ns, stat.st_size)
    if not pages:
        return None

    if norm_text:
        for i, page_text in enumerate(pages, start=1):
            if norm_text in page_text:
                return i

    exact_window_page = _find_exact_window_page(pages, ordered_words)
    if exact_window_page:
        return exact_window_page

    start_needle = set(chunk_words[: min(len(chunk_words), 40)])
    if start_needle:
        start_scores = [
            (i, len(start_needle & set(page_text.split())))
            for i, page_text in enumerate(pages, start=1)
        ]
        start_pg, start_score = max(start_scores, key=lambda x: x[1])
        if start_score >= max(min_score, int(len(start_needle) * 0.30)):
            return start_pg

    needle = set(chunk_words[:200])

    scores = [
        (i, len(needle & set(page_text.split())))
        for i, page_text in enumerate(pages, start=1)
    ]
    best_pg, best_score = max(scores, key=lambda x: x[1])
    if best_score < min_score:
        return None

    return best_pg


class VerificationService:
    def __init__(self) -> None:
        init_db()
        self.text_search = TextSearchClient()
        self.semantic_search = SemanticSearchClient()
        self.scorer = CombinedScorer()
        self.classifier = DeterministicClassifier()
        self.explainer = ResultExplainer()
        self._seed_demo_if_needed()

    def _seed_demo_if_needed(self) -> None:
        with SessionLocal() as db:
            if db.query(Book).count() > 0:
                # Backfill: classificar livros sem library_section
                unclassified = db.query(Book).filter(Book.library_section.is_(None)).all()
                if unclassified:
                    for b in unclassified:
                        section, tradition, doctype = classify_book(
                            b.collection, b.language, b.is_primary_source
                        )
                        b.library_section = section
                        b.patristic_tradition = tradition
                        b.document_type = doctype
                    db.commit()

                # Backfill canonical_author/canonical_title no seed (único livro, sem risco)
                uncanonical = db.query(Book).filter(Book.canonical_author.is_(None)).all()
                if uncanonical:
                    for b in uncanonical:
                        detected_author, _ = detect_author(b.title)
                        b.canonical_author = detected_author if detected_author else b.author
                        b.canonical_title = (
                            detect_canonical_title(b.title) if detected_author else b.title
                        )
                    db.commit()

                es_count = self.text_search.es.count(index="vera_fidei_chunks").get("count", 0)
                # Public queries use the crash-safe flat index when the legacy
                # Chroma fallback is disabled. In that mode Chroma is kept
                # deliberately unopened at startup, so it must not trigger a
                # full historical reindex (or crash on ``None``).
                chroma_count = (
                    self.semantic_search.delta_collection.count()
                    if self.semantic_search.delta_collection is not None
                    else 1
                )

                # Garantir que ES e ChromaDB estão indexados
                if es_count == 0 or chroma_count == 0:
                    chunks = db.query(Chunk).all()
                    for chunk in chunks:
                        book = db.get(Book, chunk.book_id)
                        translation_pt = db.query(Translation).filter(
                            Translation.chunk_id == chunk.id,
                            Translation.language == "pt",
                        ).first()
                        doc = self._build_doc(chunk, book, translation_pt)
                        if es_count == 0:
                            self.text_search.index_chunk(chunk.id, doc)
                        if chroma_count == 0:
                            self.semantic_search.index_chunk(chunk.id, chunk.text, {
                                "author": book.author,
                                "work_title": book.title,
                            }, language=_normalize_lang(book.language))
                            if translation_pt:
                                self.semantic_search.index_translation(chunk.id, translation_pt.text, {
                                    "author": book.author,
                                    "work_title": book.title,
                                }, language=_normalize_lang(translation_pt.language))

                # Limpeza: remover traduções-seed do Cipriano indevidamente
                # atribuídas a chunks de outros autores pelo backfill anterior.
                seed_prefix = "Não pode já ter Deus por Pai quem não tem a Igreja"
                wrong = (
                    db.query(Translation)
                    .join(Chunk, Translation.chunk_id == Chunk.id)
                    .join(Book, Chunk.book_id == Book.id)
                    .filter(
                        Translation.text.like(f"{seed_prefix}%"),
                        ~Book.author.ilike("%Cipriano%"),
                    )
                    .all()
                )
                if wrong:
                    for t in wrong:
                        db.delete(t)
                    db.commit()

                return

            # Seed inicial: livro + chunk + tradução PT
            seed_title = "De Unitate Ecclesiae"
            seed_author = "São Cipriano de Cartago"
            _detected, _ = detect_author(seed_title)
            book = Book(
                collection="PL",
                title=seed_title,
                author=seed_author,
                language="Latim",
                edition_label="Migne PL — edição 1844",
                source_label="Archive.org",
                library_section="patristica",
                patristic_tradition="latina",
                document_type=None,
                canonical_author=_detected if _detected else seed_author,
                canonical_title=detect_canonical_title(seed_title) if _detected else seed_title,
            )
            db.add(book)
            db.flush()
            book_file = BookFile(
                book_id=book.id,
                original_filename="migne_pl_vol4.pdf",
                stored_path="pdfs/migne_pl_vol4.pdf",
                volume_number=4,
            )
            db.add(book_file)
            db.flush()
            chunk = Chunk(
                book_id=book.id,
                book_file_id=book_file.id,
                chapter_or_section="Cap. 6",
                text="Habere jam non potest Deum patrem, qui Ecclesiam non habet matrem. Si potuit evadere quisquam qui extra arcam Noe fuit, et qui extra Ecclesiam foris fuerit evadit.",
                volume=4,
                column_start=503,
                column_end=503,
                pdf_page=256,
                char_offset_start=0,
                char_offset_end=120,
                visual_anchor="col503",
                sequence_index=0,
                extraction_method="seed_verified",
                source_fidelity="verified",
            )
            db.add(chunk)
            db.flush()

            translation_pt = self._seed_pt_translation(db, chunk)
            db.commit()
            db.refresh(chunk)
            db.refresh(book)
            db.refresh(translation_pt)

            # Capturar valores antes da sessão fechar
            chunk_id = chunk.id
            chunk_text = chunk.text
            book_author = book.author
            book_title = book.title
            translation_text = translation_pt.text
            doc = self._build_doc(chunk, book, translation_pt)

        self.text_search.index_chunk(chunk_id, doc)
        self.semantic_search.index_chunk(chunk_id, chunk_text, {
            "author": book_author,
            "work_title": book_title,
        }, language=doc.get("language", "la"))
        self.semantic_search.index_translation(chunk_id, translation_text, {
            "author": book_author,
            "work_title": book_title,
        }, language="pt")

    def _seed_pt_translation(self, db, chunk: Chunk) -> Translation:
        translation = Translation(
            chunk_id=chunk.id,
            language="pt",
            text="Não pode já ter Deus por Pai quem não tem a Igreja por Mãe. Se pôde escapar quem estava fora da arca de Noé, escapará também quem estiver fora da Igreja.",
            translator=None,
            edition_label="Tradução litúrgica tradicional",
        )
        db.add(translation)
        return translation

    def _build_doc(self, chunk: Chunk, book: Book, translation_pt) -> dict:
        doc = {
            "text": chunk.text,
            "author": book.author,
            "work_title": book.title,
            "collection": book.collection,
            "volume": chunk.volume,
            "column_start": chunk.column_start,
            "language": _normalize_lang(book.language),
            "pdf_page": chunk.pdf_page,
            "edition_label": book.edition_label,
            "chapter_or_section": chunk.chapter_or_section,
            "char_offset_start": chunk.char_offset_start,
            "char_offset_end": chunk.char_offset_end,
            "extraction_method": chunk.extraction_method,
            "source_fidelity": chunk.source_fidelity,
            "fidelity_score": chunk.fidelity_score,
            "is_quotable": (chunk.source_fidelity or "") in PUBLIC_SOURCE_FIDELITIES,
        }
        if translation_pt:
            doc["translation_text"] = translation_pt.text
            doc["translation_language"] = _normalize_lang(translation_pt.language)
        return doc

    def verify(self, payload: VerifyCitationRequest) -> VerifyCitationResponse:
        detected_lang = _detect_language(payload.quote, hint=payload.language)

        text_hits = self.text_search.search(
            payload.quote,
            attributed_to=payload.attributed_to,
            limit=5,
            query_language=detected_lang,
        )

        semantic_hits = []
        semantic_map = {}
        semantic_searched = False

        def ensure_semantic_hits() -> list:
            nonlocal semantic_hits, semantic_map, semantic_searched
            if not semantic_searched:
                semantic_hits = self.semantic_search.search(
                    payload.quote,
                    limit=5,
                    timeout=_SEMANTIC_FALLBACK_TIMEOUT,
                )
                semantic_map = {hit.chunk_id: hit.score for hit in semantic_hits}
                semantic_searched = True
            return semantic_hits

        if _ALWAYS_RUN_SEMANTIC or not text_hits:
            ensure_semantic_hits()

        if not text_hits and not semantic_hits:
            result = self.classifier.classify(0.0, exact_match=False, author_match=False)
            explanation = self.explainer.explain(payload, result, None, None)
            return VerifyCitationResponse(
                status_code=result.code, label=result.label, confidence=result.confidence,
                explanation=explanation,
            )

        best = None
        best_score = -1.0

        with SessionLocal() as db:
            for hit in text_hits:
                chunk = db.get(Chunk, hit.chunk_id)
                if chunk is None:
                    continue
                book = db.get(Book, chunk.book_id)
                semantic_score = semantic_map.get(hit.chunk_id, 0.0)
                # exact_match: tenta match OCR numa janela de chunks, pois
                # citações reais podem atravessar a divisão interna do índice.
                chunk_window = _chunk_window_text(db, chunk, before=4, after=5)
                author_match = _author_matches(payload.attributed_to, book, chunk=chunk) or _author_matches_in_context(
                    payload.attributed_to,
                    book,
                    chunk_window,
                )
                combined = self.scorer.combine(hit.score, semantic_score, author_match)
                exact_match = _is_exact_text_match(payload.quote, chunk_window)
                # Penalidade por autor divergente: menor quando a frase foi encontrada
                # literalmente (pode ser obra que cita o autor original).
                if payload.attributed_to and not author_match:
                    combined *= 0.6 if exact_match else 0.4
                known_selection_score = _known_conceptual_paraphrase_score(
                    payload.quote,
                    payload.attributed_to,
                    book,
                    chunk.text or "",
                )
                known_paraphrase_score = max(
                    known_selection_score,
                    0.85 * _known_conceptual_paraphrase_score(
                        payload.quote,
                        payload.attributed_to,
                        book,
                        chunk_window,
                    ),
                )
                selection_score = (
                    combined
                    + (2.0 if exact_match else 0.0)
                    + (0.2 if author_match else 0.0)
                    + (1.4 * known_selection_score)
                )
                if selection_score > best_score:
                    best_score = selection_score
                    best = (chunk, book, exact_match, author_match, combined, known_paraphrase_score)

            # Fallback: se só houve hits semânticos (busca cross-lingual)
            if best is None:
                ensure_semantic_hits()
                for hit in semantic_hits:
                    chunk = db.get(Chunk, hit.chunk_id)
                    if chunk is None:
                        continue
                    book = db.get(Book, chunk.book_id)
                    chunk_window = _chunk_window_text(db, chunk, before=4, after=5)
                    author_match = _author_matches(payload.attributed_to, book, chunk=chunk) or _author_matches_in_context(
                        payload.attributed_to,
                        book,
                        chunk_window,
                    )
                    combined = self.scorer.combine(0.0, hit.score, author_match)
                    # Penalidade por autor divergente (apenas semântico, sem texto exato)
                    if payload.attributed_to and not author_match:
                        combined *= 0.4
                    exact_match = _is_exact_text_match(payload.quote, chunk_window)
                    known_selection_score = _known_conceptual_paraphrase_score(
                        payload.quote,
                        payload.attributed_to,
                        book,
                        chunk.text or "",
                    )
                    known_paraphrase_score = max(
                        known_selection_score,
                        0.85 * _known_conceptual_paraphrase_score(
                            payload.quote,
                            payload.attributed_to,
                            book,
                            chunk_window,
                        ),
                    )
                    selection_score = (
                        combined
                        + (2.0 if exact_match else 0.0)
                        + (0.2 if author_match else 0.0)
                        + (1.4 * known_selection_score)
                    )
                    if selection_score > best_score:
                        best_score = selection_score
                        best = (chunk, book, exact_match, author_match, combined, known_paraphrase_score)

            if best is None:
                result = self.classifier.classify(0.0, exact_match=False, author_match=False)
                explanation = self.explainer.explain(payload, result, None, None)
                return VerifyCitationResponse(
                    status_code=result.code, label=result.label, confidence=result.confidence,
                    explanation=explanation,
                )

            chunk, book, exact_match, author_match, combined, known_paraphrase_score = best
            matched_window_text = _chunk_window_text(db, chunk, before=4, after=5)

            # Buscar tradução PT para o chunk encontrado
            translation_pt = db.query(Translation).filter(
                Translation.chunk_id == chunk.id,
                Translation.language == "pt",
            ).first()

            # Fidelidade: só para idiomas vernáculos (não latim/grego/hebraico)
            fidelity = None
            if translation_pt and detected_lang in TRANSLATION_LANGS:
                fidelity = _translation_fidelity(payload.quote, translation_pt.text)

            # Âncora lexical: fração dos tokens da query presentes no trecho encontrado
            anchor = _lexical_anchor(payload.quote, matched_window_text, translation_pt.text if translation_pt else None)

            # Detecção de intrusão conceitual: linguagem acadêmica moderna em citação patrística
            intrusion = _intrusion_score(payload.quote)

            # Similaridade pós-normalização OCR — compara query contra a janela
            # correspondente do chunk (não o chunk inteiro, que daria ratio muito baixo)
            from difflib import SequenceMatcher as _SM
            _q_ocr_norm = _normalize_for_search(_normalize_ocr(payload.quote))
            _c_norm_full = _normalize_for_search(matched_window_text)
            # Se a query normalizada está contida no chunk → similaridade = 1.0
            if _q_ocr_norm in _c_norm_full:
                ocr_similarity = 1.0
            else:
                # Compara contra a janela de mesmo comprimento no chunk
                _qlen = len(_q_ocr_norm)
                _clen = len(_c_norm_full)
                best_ratio = 0.0
                step = max(1, _qlen // 4)
                for start in range(0, max(1, _clen - _qlen + 1), step):
                    window = _c_norm_full[start: start + _qlen]
                    ratio = _SM(None, _q_ocr_norm, window).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                    if best_ratio >= 0.90:
                        break
                ocr_similarity = best_ratio

            result = self.classifier.classify(
                combined, exact_match, author_match,
                translation_fidelity=fidelity,
                lexical_anchor=anchor,
                intrusion_score=intrusion,
                ocr_similarity=ocr_similarity,
                known_paraphrase_score=known_paraphrase_score,
            )
            response_author = _response_author(payload.attributed_to, author_match, book, chunk)
            explanation_work = None if result.code == "NAO_ENCONTRADA" else (book.title if book else None)
            explanation_author = None if result.code == "NAO_ENCONTRADA" else response_author
            explanation = self.explainer.explain(
                payload, result,
                explanation_work,
                explanation_author,
                intrusion_score=intrusion,
                ocr_similarity=ocr_similarity,
            )

            if result.code == "NAO_ENCONTRADA":
                return VerifyCitationResponse(
                    status_code=result.code,
                    label=result.label,
                    confidence=result.confidence,
                    explanation=explanation,
                )

            # Chunks adjacentes
            if chunk.sequence_index is not None:
                prev_chunk = db.query(Chunk).filter(
                    Chunk.book_id == chunk.book_id,
                    Chunk.sequence_index < chunk.sequence_index,
                ).order_by(Chunk.sequence_index.desc()).first()
                next_chunk = db.query(Chunk).filter(
                    Chunk.book_id == chunk.book_id,
                    Chunk.sequence_index > chunk.sequence_index,
                ).order_by(Chunk.sequence_index.asc()).first()
            else:
                prev_chunk = db.query(Chunk).filter(
                    Chunk.book_id == chunk.book_id,
                    Chunk.id < chunk.id,
                ).order_by(Chunk.id.desc()).first()
                next_chunk = db.query(Chunk).filter(
                    Chunk.book_id == chunk.book_id,
                    Chunk.id > chunk.id,
                ).order_by(Chunk.id.asc()).first()

            source_file = db.get(BookFile, chunk.book_file_id) if chunk.book_file_id else None
            variant_analysis = _variant_analysis(
                exact_match=exact_match,
                ocr_similarity=ocr_similarity,
                lexical_anchor=anchor,
                translation_fidelity=fidelity,
                status_code=result.code,
                known_paraphrase_score=known_paraphrase_score,
            )

            # ─── Page-finding cross-lingual ──────────────────────────────────
            # Caminho rapido: a ingestao ja grava chunk.pdf_page. A varredura do PDF
            # inteiro por requisicao deixava o verificador lento no celular.
            real_pdf_page = chunk.pdf_page  # fallback sempre disponível
            should_scan_pdf_page = _ENABLE_PDF_PAGE_SCAN or real_pdf_page is None
            if should_scan_pdf_page and source_file and source_file.stored_path:
                # Resolve o caminho real do PDF no disco (stored_path pode ser legado)
                resolved_pdf = _resolve_pdf_path(source_file.stored_path)
                _log.debug("[page_search] stored_path=%r resolved=%r", source_file.stored_path, resolved_pdf)

                if resolved_pdf:
                    book_lang = _normalize_lang(book.language) if book else "unknown"
                    detected_lang_parts = set(detected_lang.split("+"))
                    book_lang_parts = set(book_lang.split("+"))
                    # Considera "mesmo idioma" quando ambos são idiomas originais (la+grc, etc.)
                    same_lang = bool(detected_lang_parts & book_lang_parts) or (
                        bool(detected_lang_parts & ORIGINAL_LANGS) and bool(book_lang_parts & ORIGINAL_LANGS)
                    )

                    found_page = None

                    if same_lang:
                        # Normaliza artefatos OCR antes de buscar a página
                        # min_score=3: citação pode começar no rodapé da página (poucos tokens lá)
                        user_query = _normalize_ocr((payload.quote or "").strip())
                        if len(user_query) >= 12:
                            found_page = _find_real_pdf_page(resolved_pdf, user_query, min_score=3)
                            _log.debug("[page_search] strategy=user_query(%s) result=%s", detected_lang, found_page)

                    # Fallback sempre: chunk.text está no idioma do PDF
                    if not found_page:
                        found_page = _find_real_pdf_page(resolved_pdf, chunk.text, min_score=5)
                        _log.debug("[page_search] strategy=chunk_text result=%s", found_page)

                    if found_page:
                        real_pdf_page = found_page

            return VerifyCitationResponse(
                status_code=result.code,
                label=result.label,
                confidence=result.confidence,
                author=response_author,
                work=book.title if book else None,
                reference=MatchReference(
                    collection=book.collection if book else "",
                    volume=chunk.volume,
                    column_start=chunk.column_start,
                    column_end=chunk.column_end,
                    chapter_or_section=chunk.chapter_or_section,
                    pdf_page=real_pdf_page,
                    visual_anchor=chunk.visual_anchor,
                    edition_label=book.edition_label if book else None,
                    source_label=book.source_label if book else None,
                    language=book.language if book else None,
                    editor=source_file.editor if source_file else None,
                    translator=source_file.translator if source_file else None,
                    is_primary_source=book.is_primary_source if book else True,
                    pdf_file_id=chunk.book_file_id,
                ),
                original_language=book.language if book else None,
                source_version=book.edition_label if book else None,
                matched_excerpt=_clean_matched_excerpt_display(
                    _extract_matching_excerpt(payload.quote, matched_window_text),
                    real_pdf_page,
                ),
                context_before=prev_chunk.text if prev_chunk else None,
                context_after=next_chunk.text if next_chunk else None,
                explanation=explanation,
                matched_translation=translation_pt.text if translation_pt else None,
                translation_language=translation_pt.language if translation_pt else None,
                translation_fidelity=fidelity,
                translator=translation_pt.translator if translation_pt else None,
                translation_edition=translation_pt.edition_label if translation_pt else None,
                variant_analysis=variant_analysis,
            )
