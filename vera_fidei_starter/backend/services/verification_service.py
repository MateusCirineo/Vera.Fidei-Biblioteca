from models.database import SessionLocal, Chunk, Book, BookFile, init_db
from schemas.citation import VerifyCitationRequest, VerifyCitationResponse, MatchReference
from search.text_search import TextSearchClient
from search.semantic_search import SemanticSearchClient
from confidence.scorer import CombinedScorer
from confidence.classifier import DeterministicClassifier
from confidence.explainer import ResultExplainer


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
                # PostgreSQL já tem dados — garantir que ES e ChromaDB também estão indexados
                chunks = db.query(Chunk).all()
                es_count = self.text_search.es.count(index="vera_fidei_chunks").get("count", 0)
                chroma_count = self.semantic_search.collection.count()
                if es_count == 0 or chroma_count == 0:
                    for chunk in chunks:
                        book = db.get(Book, chunk.book_id)
                        doc = {
                            "text": chunk.text,
                            "author": book.author,
                            "work_title": book.title,
                            "collection": book.collection,
                            "volume": chunk.volume,
                            "column_start": chunk.column_start,
                            "language": book.language,
                            "pdf_page": chunk.pdf_page,
                            "edition_label": book.edition_label,
                            "chapter_or_section": chunk.chapter_or_section,
                            "char_offset_start": chunk.char_offset_start,
                            "char_offset_end": chunk.char_offset_end,
                        }
                        if es_count == 0:
                            self.text_search.index_chunk(chunk.id, doc)
                        if chroma_count == 0:
                            self.semantic_search.index_chunk(chunk.id, chunk.text, {
                                "author": book.author,
                                "work_title": book.title,
                            })
                WRONG_TEXT = "Habere non potest Deum patrem qui Ecclesiam non habet matrem. Hoc testimonium ad unitatem Ecclesiae refertur."
                CORRECT_TEXT = "Habere jam non potest Deum patrem, qui Ecclesiam non habet matrem. Si potuit evadere quisquam qui extra arcam Noe fuit, et qui extra Ecclesiam foris fuerit evadit."
                needs_reindex = False

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

                # Corrigir texto errado em qualquer chunk (independente de book_file_id)
                for chunk in db.query(Chunk).filter(Chunk.text == WRONG_TEXT).all():
                    chunk.text = CORRECT_TEXT
                    needs_reindex = True

                db.commit()

                if needs_reindex:
                    chunks_to_reindex = db.query(Chunk).all()
                    self.text_search.es.delete_by_query(index="vera_fidei_chunks", body={"query": {"match_all": {}}})
                    try:
                        self.semantic_search.collection.delete(where={"chunk_id": {"$gte": 0}})
                    except Exception:
                        pass
                    for c in chunks_to_reindex:
                        b = db.get(Book, c.book_id)
                        self.text_search.index_chunk(c.id, {
                            "text": c.text,
                            "author": b.author,
                            "work_title": b.title,
                            "collection": b.collection,
                            "volume": c.volume,
                            "column_start": c.column_start,
                            "language": b.language,
                            "pdf_page": c.pdf_page,
                            "edition_label": b.edition_label,
                            "chapter_or_section": c.chapter_or_section,
                            "char_offset_start": c.char_offset_start,
                            "char_offset_end": c.char_offset_end,
                        })
                        self.semantic_search.index_chunk(c.id, c.text, {
                            "author": b.author,
                            "work_title": b.title,
                        })
                return
            book = Book(
                collection="PL",
                title="De Unitate Ecclesiae",
                author="São Cipriano de Cartago",
                language="Latim",
                edition_label="Migne PL — edição 1844",
                source_label="Archive.org",
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
            db.commit()
            db.refresh(chunk)
            db.refresh(book)

        self.text_search.index_chunk(chunk.id, {
            "text": chunk.text,
            "author": book.author,
            "work_title": book.title,
            "collection": book.collection,
            "volume": chunk.volume,
            "column_start": chunk.column_start,
            "language": book.language,
            "pdf_page": chunk.pdf_page,
            "edition_label": book.edition_label,
            "chapter_or_section": chunk.chapter_or_section,
            "char_offset_start": chunk.char_offset_start,
            "char_offset_end": chunk.char_offset_end,
        })
        self.semantic_search.index_chunk(chunk.id, chunk.text, {
            "author": book.author,
            "work_title": book.title,
        })

    def verify(self, payload: VerifyCitationRequest) -> VerifyCitationResponse:
        text_hits = self.text_search.search(payload.quote, attributed_to=payload.attributed_to, limit=5)
        semantic_hits = self.semantic_search.search(payload.quote, limit=5)
        semantic_map = {hit.chunk_id: hit.score for hit in semantic_hits}

        if not text_hits and not semantic_hits:
            result = self.classifier.classify(0.0, exact_match=False, author_match=False)
            explanation = self.explainer.explain(payload, result, None, None)
            return VerifyCitationResponse(status_code=result.code, label=result.label, confidence=result.confidence, explanation=explanation)

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

            if best is None:
                result = self.classifier.classify(0.0, exact_match=False, author_match=False)
                explanation = self.explainer.explain(payload, result, None, None)
                return VerifyCitationResponse(status_code=result.code, label=result.label, confidence=result.confidence, explanation=explanation)

            chunk, book, exact_match, author_match, combined = best
            result = self.classifier.classify(combined, exact_match, author_match)
            explanation = self.explainer.explain(payload, result, book.title if book else None, book.author if book else None)

            # Chunks adjacentes para context_before / context_after
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
                # fallback por id quando sequence_index não disponível
                prev_chunk = db.query(Chunk).filter(
                    Chunk.book_id == chunk.book_id,
                    Chunk.id < chunk.id,
                ).order_by(Chunk.id.desc()).first()
                next_chunk = db.query(Chunk).filter(
                    Chunk.book_id == chunk.book_id,
                    Chunk.id > chunk.id,
                ).order_by(Chunk.id.asc()).first()

            # Metadados do arquivo PDF de origem (se disponível)
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
            )
