import logging
import os
import re
import unicodedata

import pdfplumber

_log = logging.getLogger(__name__)
from langdetect import detect, LangDetectException

from models.database import SessionLocal, Chunk, Book, BookFile, Translation, init_db
from schemas.citation import VerifyCitationRequest, VerifyCitationResponse, MatchReference
from search.text_search import TextSearchClient
from search.semantic_search import SemanticSearchClient
from confidence.scorer import CombinedScorer
from confidence.classifier import DeterministicClassifier
from confidence.explainer import ResultExplainer
from utils.language import (
    normalize_lang as _normalize_lang,
    detect_latin_heuristic,
    detect_script_heuristic,
    ORIGINAL_LANGS, TRANSLATION_LANGS,
    classify_book,
)
from utils.author_detection import detect_author, detect_canonical_title


def _detect_language(text: str, hint: str | None = None) -> str:
    """
    Detecta o idioma da query.
    Prioridade: hint > script Unicode (grego/siríaco/copta/etc.) > heurística latina > langdetect.
    "unknown" ≠ "la": evita enviesar o boosting de busca.
    """
    if hint:
        return hint.strip().lower()
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


def _author_matches(attributed_to: str, book) -> bool:
    """Verifica se o autor atribuído bate com o livro encontrado (author ou canonical_author)."""
    if not attributed_to or not book:
        return False
    needle = attributed_to.strip().lower()
    return (
        needle == book.author.lower()
        or (book.canonical_author is not None and needle == book.canonical_author.lower())
    )


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


# ─── Busca de página real no PDF ─────────────────────────────────────────────

def _normalize_for_search(text: str) -> str:
    """Remove acentos, normaliza espaços e converte para minúsculas."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _find_real_pdf_page(pdf_path: str, chunk_text: str) -> int | None:
    """
    Varre TODAS as páginas do PDF e retorna aquela onde a maior parte do
    chunk está concentrada.

    Estratégia de pontuação por sobreposição de palavras:
    - Para cada página, conta quantas palavras únicas do chunk aparecem nela.
    - Retorna a página com maior sobreposição.
    - Isso é robusto contra words que aparecem no final/início de outra página,
      OCR imperfeito e variações de espaço.

    Fallback: se nenhuma página tiver sobreposição mínima, retorna None.
    """
    if not pdf_path or not os.path.isfile(pdf_path):
        return None

    # Vocabulário do chunk — ignora palavras muito curtas (artigos, preposições)
    # para não poluir o score com tokens que aparecem em todas as páginas.
    chunk_words = [
        w for w in _normalize_for_search(chunk_text).split()
        if len(w) >= 4
    ]
    if len(chunk_words) < 5:
        return None

    # Usa uma janela central do chunk (pula os primeiros 30 tokens que podem estar
    # na página anterior devido ao overlap, e limita a 250 tokens do meio)
    needle_set = set(chunk_words[30:280])

    try:
        with pdfplumber.open(pdf_path) as pdf:
            best_page  = None
            best_score = 0
            for i, page in enumerate(pdf.pages, start=1):
                page_text  = _normalize_for_search(page.extract_text() or "")
                page_words = set(page_text.split())
                score = len(needle_set & page_words)
                if score > best_score:
                    best_score = score
                    best_page  = i
            # Exige pelo menos 5 palavras em comum para considerar válido
            return best_page if best_score >= 5 else None
    except Exception:
        return None


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
                chroma_count = self.semantic_search.collection.count()

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

                # Corrigir chunks sem book_file_id
                for chunk in db.query(Chunk).filter(Chunk.book_file_id.is_(None)).all():
                    book = db.get(Book, chunk.book_id)
                    if book:
                        book_file = BookFile(
                            book_id=book.id,
                            original_filename="migne_pl_vol4.pdf",
                            stored_path="pdfs/migne_pl_vol4.pdf",
                            volume_number=chunk.volume,
                        )
                        db.add(book_file)
                        db.flush()
                        chunk.book_file_id = book_file.id
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
        semantic_hits = self.semantic_search.search(payload.quote, limit=5)
        semantic_map = {hit.chunk_id: hit.score for hit in semantic_hits}

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
                author_match = _author_matches(payload.attributed_to, book)
                semantic_score = semantic_map.get(hit.chunk_id, 0.0)
                combined = self.scorer.combine(hit.score, semantic_score, author_match)
                # Penalidade forte: autor atribuído não coincide com a obra encontrada
                if payload.attributed_to and not author_match:
                    combined *= 0.4
                exact_match = payload.quote.lower() in chunk.text.lower()
                if combined > best_score:
                    best_score = combined
                    best = (chunk, book, exact_match, author_match, combined)

            # Fallback: se só houve hits semânticos (busca cross-lingual)
            if best is None:
                for hit in semantic_hits:
                    chunk = db.get(Chunk, hit.chunk_id)
                    if chunk is None:
                        continue
                    book = db.get(Book, chunk.book_id)
                    author_match = _author_matches(payload.attributed_to, book)
                    combined = self.scorer.combine(0.0, hit.score, author_match)
                    # Penalidade forte: autor atribuído não coincide com a obra encontrada
                    if payload.attributed_to and not author_match:
                        combined *= 0.4
                    exact_match = False
                    if combined > best_score:
                        best_score = combined
                        best = (chunk, book, exact_match, author_match, combined)

            if best is None:
                result = self.classifier.classify(0.0, exact_match=False, author_match=False)
                explanation = self.explainer.explain(payload, result, None, None)
                return VerifyCitationResponse(
                    status_code=result.code, label=result.label, confidence=result.confidence,
                    explanation=explanation,
                )

            chunk, book, exact_match, author_match, combined = best

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
            anchor = _lexical_anchor(payload.quote, chunk.text, translation_pt.text if translation_pt else None)

            # Detecção de intrusão conceitual: linguagem acadêmica moderna em citação patrística
            intrusion = _intrusion_score(payload.quote)

            result = self.classifier.classify(
                combined, exact_match, author_match,
                translation_fidelity=fidelity,
                lexical_anchor=anchor,
                intrusion_score=intrusion,
            )
            explanation = self.explainer.explain(
                payload, result,
                book.title if book else None,
                book.author if book else None,
                intrusion_score=intrusion,
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
            # chunk.text está sempre no idioma do PDF; payload.quote pode estar
            # em qualquer idioma digitado pelo usuário.
            # Só tentamos a query do usuário quando ela está no mesmo idioma do PDF
            # para evitar varredura inútil (PT vs latim/grego).
            real_pdf_page = chunk.pdf_page  # fallback sempre disponível
            if source_file and source_file.stored_path:
                book_lang = _normalize_lang(book.language) if book else "unknown"
                # Considera "mesmo idioma" quando ambos são idiomas originais (la+grc, etc.)
                same_lang = (detected_lang == book_lang) or (
                    detected_lang in ORIGINAL_LANGS and book_lang in ORIGINAL_LANGS
                )

                found_page = None

                if same_lang:
                    user_query = (payload.quote or "").strip()
                    if len(user_query) >= 12:
                        found_page = _find_real_pdf_page(source_file.stored_path, user_query)
                        _log.debug("[page_search] strategy=user_query(%s) result=%s", detected_lang, found_page)

                # Fallback sempre: chunk.text está no idioma do PDF
                if not found_page:
                    found_page = _find_real_pdf_page(source_file.stored_path, chunk.text)
                    _log.debug("[page_search] strategy=chunk_text result=%s", found_page)

                if found_page:
                    real_pdf_page = found_page

            return VerifyCitationResponse(
                status_code=result.code,
                label=result.label,
                confidence=result.confidence,
                author=book.author if book else None,
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
                matched_excerpt=chunk.text,
                context_before=prev_chunk.text if prev_chunk else None,
                context_after=next_chunk.text if next_chunk else None,
                explanation=explanation,
                matched_translation=translation_pt.text if translation_pt else None,
                translation_language=translation_pt.language if translation_pt else None,
                translation_fidelity=fidelity,
                translator=translation_pt.translator if translation_pt else None,
                translation_edition=translation_pt.edition_label if translation_pt else None,
            )
