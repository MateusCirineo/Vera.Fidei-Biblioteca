from models.database import SessionLocal, Book, Chunk, init_db
from search.text_search import TextSearchClient
from search.semantic_search import SemanticSearchClient


class Indexer:
    def __init__(self) -> None:
        init_db()
        self.text_search = TextSearchClient()
        self.semantic_search = SemanticSearchClient()

    def index(self, chunks: list[dict], book_meta: dict) -> None:
        with SessionLocal() as db:
            book = Book(
                collection=book_meta["collection"],
                title=book_meta["title"],
                author=book_meta["author"],
                language=book_meta["language"],
                edition_label=book_meta.get("edition_label", ""),
                source_label=book_meta.get("source_label", ""),
            )
            db.add(book)
            db.flush()

            for chunk_data in chunks:
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
                )
                db.add(chunk)
                db.flush()

                es_doc = {
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
                }
                self.text_search.index_chunk(chunk.id, es_doc)

                chroma_meta = {
                    "author":            book_meta["author"],
                    "work_title":        book_meta["title"],
                    "collection":        book_meta["collection"],
                    "volume":            str(chunk_data.get("volume_number", "")),
                    "column_start":      str(chunk_data.get("column_start", "")),
                    "language":          book_meta["language"],
                    "edition_label":     book_meta.get("edition_label", ""),
                }
                self.semantic_search.index_chunk(chunk.id, chunk_data["text"], chroma_meta)

            db.commit()
            print(f"{len(chunks)} chunks indexados — livro ID {book.id}")
