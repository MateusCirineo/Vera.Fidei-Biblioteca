from __future__ import annotations

import os
import re
import tempfile
import datetime

from fastapi import HTTPException
from sqlalchemy import func

from models.database import SessionLocal, Book, Chunk, BookFile
from search.text_search import TextSearchClient
from search.semantic_search import SemanticSearchClient
from ingestion.pdf_extractor import PDFExtractor
from ingestion.chunker import Chunker
from utils.author_detection import detect_author, detect_canonical_title

PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "pdfs")


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)


class IngestionService:
    def __init__(self) -> None:
        self.text_search = TextSearchClient()
        self.semantic_search = SemanticSearchClient()
        self.extractor = PDFExtractor()
        self.chunker = Chunker()

    def ingest(
        self,
        book_id: int,
        pdf_bytes: bytes,
        original_filename: str,
        volume_number: int | None,
        editor: str | None = None,
        translator: str | None = None,
    ) -> tuple[BookFile, int]:
        os.makedirs(PDF_DIR, exist_ok=True)

        with SessionLocal() as db:
            book = db.get(Book, book_id)
            if book is None:
                raise HTTPException(status_code=404, detail=f"Livro {book_id} não encontrado.")

            # Calcular sequence_index de partida (aditivo)
            max_seq = db.query(func.max(Chunk.sequence_index)).filter(
                Chunk.book_id == book_id
            ).scalar()
            next_seq = (max_seq + 1) if max_seq is not None else 0

        # Salvar PDF em disco com nome único
        timestamp = int(datetime.datetime.utcnow().timestamp())
        safe_name = _sanitize_filename(original_filename)
        stored_filename = f"{book_id}_{timestamp}_{safe_name}"
        stored_path = os.path.join(PDF_DIR, stored_filename)

        with open(stored_path, "wb") as f:
            f.write(pdf_bytes)

        # Extrair texto e gerar chunks
        try:
            pages = self.extractor.extract(stored_path)
            document_meta: dict = {}
            if volume_number is not None:
                document_meta["volume_number"] = volume_number
            raw_chunks = self.chunker.chunk(pages, document_meta)
        except Exception as exc:
            os.remove(stored_path)
            raise HTTPException(status_code=500, detail=f"Falha na extração do PDF: {exc}")

        if not raw_chunks:
            os.remove(stored_path)
            raise HTTPException(status_code=422, detail="Nenhum texto extraído do PDF.")

        # Preparar dados dos chunks com sequence_index
        for i, chunk_data in enumerate(raw_chunks):
            chunk_data["sequence_index"] = next_seq + i

        # Amostra do conteúdo das primeiras páginas para detecção de metadados
        content_sample = " ".join(
            p.get("text", "") for p in pages[:3] if isinstance(p, dict)
        )
        if not content_sample and pages:
            # extrator retorna strings diretas em vez de dicts
            content_sample = " ".join(str(p) for p in pages[:3])
        content_sample = content_sample[:1000]

        # Detectar autor e título canônicos ANTES de salvar definitivamente
        with SessionLocal() as db:
            book = db.get(Book, book_id)
            if book is None:
                raise HTTPException(status_code=404, detail=f"Livro {book_id} não encontrado.")
            if book.canonical_author is None:
                detected_author, _ = detect_author(book.title, content_sample)
                book.canonical_author = detected_author if detected_author else book.author
                book.canonical_title = (
                    detect_canonical_title(book.title, content_sample)
                    if detected_author
                    else book.title
                )
                db.commit()

        # Abrir sessão, fazer flush para obter IDs, tentar indexar ES/Chroma,
        # só commit se tudo der certo — rollback se qualquer indexação falhar.
        with SessionLocal() as db:
            book_file = BookFile(
                book_id=book_id,
                original_filename=original_filename,
                stored_path=stored_path,
                volume_number=volume_number,
                editor=editor,
                translator=translator,
            )
            db.add(book_file)
            db.flush()

            chunk_records: list[Chunk] = []
            for chunk_data in raw_chunks:
                chunk = Chunk(
                    book_id=book_id,
                    book_file_id=book_file.id,
                    text=chunk_data["text"],
                    sequence_index=chunk_data["sequence_index"],
                    volume=chunk_data.get("volume_number"),
                    column_start=chunk_data.get("column_start"),
                    column_end=chunk_data.get("column_end"),
                    pdf_page=chunk_data.get("pdf_page"),
                    char_offset_start=chunk_data.get("char_offset_start"),
                    char_offset_end=chunk_data.get("char_offset_end"),
                    visual_anchor=f"col{chunk_data.get('column_start', '')}",
                    chapter_or_section=chunk_data.get("chapter_or_section", ""),
                )
                db.add(chunk)
                chunk_records.append(chunk)

            db.flush()  # obtém IDs sem commit

            book = db.get(Book, book_id)
            try:
                for chunk in chunk_records:
                    es_doc = {
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
                    self.text_search.index_chunk(chunk.id, es_doc)

                    chroma_meta = {
                        "author": book.author,
                        "work_title": book.title,
                    }
                    self.semantic_search.index_chunk(chunk.id, chunk.text, chroma_meta)

            except Exception as exc:
                db.rollback()
                os.remove(stored_path)
                raise HTTPException(
                    status_code=500,
                    detail=f"Falha ao indexar no motor de busca: {exc}",
                )

            db.commit()
            db.refresh(book_file)
            return book_file, len(chunk_records)
