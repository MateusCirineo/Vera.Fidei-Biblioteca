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

from models.database import SessionLocal, Chunk, Book, BookFile, Translation, init_db
from schemas.citation import VerifyCitationRequest, VerifyCitationResponse, MatchReference
from search.text_search import TextSearchClient
from search.semantic_search import SemanticSearchClient
from confidence.scorer import CombinedScorer
from confidence.classifier import DeterministicClassifier
from confidence.explainer import ResultExplainer
from storage.pdf_storage import get_pdf_storage
from utils.language import (
    normalize_lang as _normalize_lang,
    detect_latin_heuristic,
    detect_script_heuristic,
    ORIGINAL_LANGS, TRANSLATION_LANGS,
    classify_book,
)
from utils.author_detection import detect_author, detect_canonical_title, resolve_author_alias, _normalize_for_alias


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

    return len(q_tokens & all_source) / len(q_tokens)


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

def _normalize_for_search(text: str) -> str:
    """Remove acentos, normaliza espaços e converte para minúsculas."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


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
    from difflib import SequenceMatcher

    norm_q = _normalize_for_search(_normalize_ocr(query))
    norm_c = _normalize_for_search(chunk_text)

    # Tentativa de substring exata após normalização OCR
    if norm_q in norm_c:
        start = norm_c.index(norm_q)
        end = start + len(norm_q)
        # Mapeia de volta para o texto original (aproximado por proporção)
        ratio = len(chunk_text) / max(len(norm_c), 1)
        orig_start = max(0, int(start * ratio) - 20)
        orig_end = min(len(chunk_text), int(end * ratio) + 20)
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
    return (q_raw in c_raw) or bool(q_ocr and q_ocr in c_norm)


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
    candidate_sizes = [
        min(len(beginning), size)
        for size in (24, 18, 14, 10, 8, 6, 5)
        if len(beginning) >= size
    ]

    seen_sizes: set[int] = set()
    for size in candidate_sizes:
        if size in seen_sizes:
            continue
        seen_sizes.add(size)
        for offset in range(0, len(beginning) - size + 1):
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

    # Normaliza OCR e tokeniza
    norm_text = _normalize_for_search(_normalize_ocr(chunk_text))
    chunk_words = [w for w in norm_text.split() if len(w) >= 4]
    if len(chunk_words) < 5:
        return None

    pdf_path = os.path.abspath(pdf_path)
    pages = _cached_pdf_page_texts(pdf_path, stat.st_mtime_ns, stat.st_size)
    if not pages:
        return None

    if norm_text:
        for i, page_text in enumerate(pages, start=1):
            if norm_text in page_text:
                return i

    exact_window_page = _find_exact_window_page(pages, chunk_words)
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

                chunks = db.query(Chunk).all()
                es_count = self.text_search.es.count(index="vera_fidei_chunks").get("count", 0)
                chroma_count = self.semantic_search.delta_collection.count()

                # Garantir que ES e ChromaDB estão indexados
                if es_count == 0 or chroma_count == 0:
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
                author_match = _author_matches(payload.attributed_to, book, chunk=chunk)
                semantic_score = semantic_map.get(hit.chunk_id, 0.0)
                combined = self.scorer.combine(hit.score, semantic_score, author_match)
                # exact_match: tenta match OCR numa janela de chunks, pois
                # citações reais podem atravessar a divisão interna do índice.
                chunk_window = _chunk_window_text(db, chunk)
                exact_match = _is_exact_text_match(payload.quote, chunk_window)
                # Penalidade por autor divergente: menor quando a frase foi encontrada
                # literalmente (pode ser obra que cita o autor original).
                if payload.attributed_to and not author_match:
                    combined *= 0.6 if exact_match else 0.4
                selection_score = combined + (2.0 if exact_match else 0.0) + (0.2 if author_match else 0.0)
                if selection_score > best_score:
                    best_score = selection_score
                    best = (chunk, book, exact_match, author_match, combined)

            # Fallback: se só houve hits semânticos (busca cross-lingual)
            if best is None:
                ensure_semantic_hits()
                for hit in semantic_hits:
                    chunk = db.get(Chunk, hit.chunk_id)
                    if chunk is None:
                        continue
                    book = db.get(Book, chunk.book_id)
                    author_match = _author_matches(payload.attributed_to, book, chunk=chunk)
                    combined = self.scorer.combine(0.0, hit.score, author_match)
                    # Penalidade por autor divergente (apenas semântico, sem texto exato)
                    if payload.attributed_to and not author_match:
                        combined *= 0.4
                    chunk_window = _chunk_window_text(db, chunk)
                    exact_match = _is_exact_text_match(payload.quote, chunk_window)
                    selection_score = combined + (2.0 if exact_match else 0.0) + (0.2 if author_match else 0.0)
                    if selection_score > best_score:
                        best_score = selection_score
                        best = (chunk, book, exact_match, author_match, combined)

            if best is None:
                result = self.classifier.classify(0.0, exact_match=False, author_match=False)
                explanation = self.explainer.explain(payload, result, None, None)
                return VerifyCitationResponse(
                    status_code=result.code, label=result.label, confidence=result.confidence,
                    explanation=explanation,
                )

            chunk, book, exact_match, author_match, combined = best
            matched_window_text = _chunk_window_text(db, chunk)

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
            )
            explanation_work = None if result.code == "NAO_ENCONTRADA" else (book.title if book else None)
            explanation_author = None if result.code == "NAO_ENCONTRADA" else (book.author if book else None)
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
                author=(chunk.chunk_author or book.author) if book else None,
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
                matched_excerpt=_extract_matching_excerpt(payload.quote, matched_window_text),
                context_before=prev_chunk.text if prev_chunk else None,
                context_after=next_chunk.text if next_chunk else None,
                explanation=explanation,
                matched_translation=translation_pt.text if translation_pt else None,
                translation_language=translation_pt.language if translation_pt else None,
                translation_fidelity=fidelity,
                translator=translation_pt.translator if translation_pt else None,
                translation_edition=translation_pt.edition_label if translation_pt else None,
            )

