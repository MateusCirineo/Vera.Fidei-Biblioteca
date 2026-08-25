from models.database import SessionLocal, Book, Chunk, init_db
from search.content_quality import assess_content
from search.text_search import PATRISTIC_COLLECTIONS, TextSearchClient
from search.semantic_search import SemanticSearchClient


class Indexer:
    def __init__(self) -> None:
        init_db()
        self.text_search = TextSearchClient()
        self.semantic_search = SemanticSearchClient()

    def index(self, chunks: list[dict], book_meta: dict) -> None:
        with SessionLocal() as db:
            is_patristic = bool(
                book_meta.get("library_section") == "patristica"
                or book_meta.get("patristic_tradition")
                or book_meta.get("collection") in PATRISTIC_COLLECTIONS
            )
            book = Book(
                collection=book_meta["collection"],
                title=book_meta["title"],
                author=book_meta["author"],
                language=book_meta["language"],
                edition_label=book_meta.get("edition_label", ""),
                source_label=book_meta.get("source_label", ""),
                library_section=book_meta.get("library_section"),
                patristic_tradition=book_meta.get("patristic_tradition"),
            )
            db.add(book)
            db.flush()

            for chunk_data in chunks:
                quality = assess_content(
                    chunk_data["text"],
                    section=chunk_data.get("chapter_or_section", ""),
                    author=book_meta["author"],
                    work_title=book_meta["title"],
                    pdf_page=chunk_data.get("pdf_page"),
                )
                chunk = Chunk(
                    book_id=book.id,
                    chapter_or_section=chunk_data.get("chapter_or_section", ""),
                    text=chunk_data["text"],
                    volume=chunk_data.get("volume_number"),
                    column_start=chunk_data.get("column_start"),
                    column_end=chunk_data.get("column_end"),
                    pdf_page=chunk_data.get("pdf_page"),
                    char_offset_start=chunk_data.get("char_offset_start"),
                    char_offset_end=chunk_data.get("char_offset_end"),
                    visual_anchor=f"col{chunk_data.get('column_start', '')}",
                    extraction_method=chunk_data.get("extraction_method", "legacy_unknown"),
                    source_fidelity=chunk_data.get("source_fidelity", "unverified"),
                    fidelity_score=chunk_data.get("fidelity_score"),
                    fidelity_reasons=chunk_data.get("fidelity_reasons"),
                )
                db.add(chunk)
                db.flush()

                source_is_public = chunk.source_fidelity in {"source_text", "verified"}
                es_doc = {
                    "book_id":           book.id,
                    "text":              chunk_data["text"],
                    "author":            book_meta["author"],
                    "work_title":        book_meta["title"],
                    "collection":        book_meta["collection"],
                    "volume":            chunk_data.get("volume_number"),
                    "column_start":      chunk_data.get("column_start"),
                    "language":          book_meta["language"],
                    "pdf_page":          chunk_data.get("pdf_page"),
                    "edition_label":     book_meta.get("edition_label", ""),
                    "chapter_or_section":chunk_data.get("chapter_or_section", ""),
                    "char_offset_start": chunk_data.get("char_offset_start"),
                    "char_offset_end":   chunk_data.get("char_offset_end"),
                    "content_role":      quality.role,
                    "is_quotable":       quality.is_quotable and source_is_public,
                    "content_quality_score": quality.quality_score,
                    "extraction_method": chunk.extraction_method,
                    "source_fidelity": chunk.source_fidelity,
                    "fidelity_score": chunk.fidelity_score,
                }
                self.text_search.index_chunk(chunk.id, es_doc)

                chroma_meta = {
                    "book_id":           book.id,
                    "author":            book_meta["author"],
                    "work_title":        book_meta["title"],
                    "collection":        book_meta["collection"],
                    "volume":            str(chunk_data.get("volume_number", "")),
                    "column_start":      str(chunk_data.get("column_start", "")),
                    "language":          book_meta["language"],
                    "edition_label":     book_meta.get("edition_label", ""),
                }
                # Only patristic citation search excludes editorial material
                # from its semantic corpus. Other library sections retain the
                # existing full-document semantic behaviour.
                if source_is_public and (not is_patristic or quality.is_quotable):
                    self.semantic_search.index_chunk(chunk.id, chunk_data["text"], chroma_meta)

            db.commit()
            print(f"{len(chunks)} chunks indexados — livro ID {book.id}")
