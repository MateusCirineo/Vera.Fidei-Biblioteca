from models.database import SessionLocal, Chunk, Book, init_db
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
            chunk = Chunk(
                book_id=book.id,
                chapter_or_section="Cap. 6",
                text="Habere non potest Deum patrem qui Ecclesiam non habet matrem. Hoc testimonium ad unitatem Ecclesiae refertur.",
                volume=4,
                column_start=503,
                column_end=503,
                pdf_page=256,
                char_offset_start=0,
                char_offset_end=120,
                visual_anchor="col503",
            )
            db.add(chunk)
            db.commit()

    def verify(self, payload: VerifyCitationRequest) -> VerifyCitationResponse:
        text_hits = self.text_search.search(payload.quote, limit=5)
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
                ),
                original_language=book.language if book else None,
                source_version=book.edition_label if book else None,
                matched_excerpt=chunk.text,
                explanation=explanation,
            )
