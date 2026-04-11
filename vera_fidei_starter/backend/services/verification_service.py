from langdetect import detect, LangDetectException

from models.database import SessionLocal, Chunk, Book, BookFile, Translation, init_db
from schemas.citation import VerifyCitationRequest, VerifyCitationResponse, MatchReference
from search.text_search import TextSearchClient
from search.semantic_search import SemanticSearchClient
from confidence.scorer import CombinedScorer
from confidence.classifier import DeterministicClassifier
from confidence.explainer import ResultExplainer
from utils.language import normalize_lang as _normalize_lang, ORIGINAL_LANGS, TRANSLATION_LANGS, classify_book, detect_latin_heuristic
from utils.author_detection import detect_author, detect_canonical_title


def _detect_language(text: str, hint: str | None = None) -> str:
    """
    Detecta o idioma da query.
    Prioridade: hint do payload > heurística latina > langdetect > "unknown".
    "unknown" ≠ "la": evita enviesar o boosting de busca.
    A heurística latina previne que langdetect retorne "it" ou "es" em textos
    curtos com vocabulário patrístico.
    """
    if hint:
        return hint.strip().lower()
    if detect_latin_heuristic(text):
        return "la"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def _translation_fidelity(query: str, reference: str) -> str:
    """Avalia fidelidade da tradução por sobreposição de tokens."""
    q_tokens = set(query.lower().split())
    r_tokens = set(reference.lower().split())
    if not r_tokens:
        return "nao_encontrada"
    overlap = len(q_tokens & r_tokens) / len(r_tokens)
    if overlap >= 0.5:
        return "fiel"
    if overlap >= 0.25:
        return "imprecisa"
    return "nao_encontrada"


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

                # Garantir tradução PT no banco para chunks sem ela
                for chunk in chunks:
                    has_pt = db.query(Translation).filter(
                        Translation.chunk_id == chunk.id,
                        Translation.language == "pt",
                    ).first()
                    if not has_pt:
                        self._seed_pt_translation(db, chunk)
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
            translator="Anônimo",
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
                author_match = payload.attributed_to.strip().lower() == (book.author.lower() if book else "")
                semantic_score = semantic_map.get(hit.chunk_id, 0.0)
                combined = self.scorer.combine(hit.score, semantic_score, author_match)
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
                    author_match = payload.attributed_to.strip().lower() == (book.author.lower() if book else "")
                    combined = self.scorer.combine(0.0, hit.score, author_match)
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

            # Avaliar fidelidade apenas para idiomas vernáculos (não para latim/grego/hebraico nem desconhecido)
            fidelity = None
            if translation_pt and detected_lang in TRANSLATION_LANGS:
                fidelity = _translation_fidelity(payload.quote, translation_pt.text)

            result = self.classifier.classify(combined, exact_match, author_match, translation_fidelity=fidelity)
            explanation = self.explainer.explain(payload, result, book.title if book else None, book.author if book else None)

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
                    pdf_page=chunk.pdf_page,
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
            )
