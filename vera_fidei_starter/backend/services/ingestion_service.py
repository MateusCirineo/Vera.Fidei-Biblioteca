from __future__ import annotations

import os
import re
import tempfile
import threading

import pdfplumber
from fastapi import HTTPException
from langdetect import detect, LangDetectException
from sqlalchemy import func

from models.database import SessionLocal, Book, Chunk, BookFile, Translation
from search.text_search import TextSearchClient
from search.semantic_search import SemanticSearchClient
from storage.pdf_storage import get_pdf_storage
from ingestion.pdf_extractor import PDFExtractor
from ingestion.chunker import Chunker
from utils.patristic_parser import parse_patristic_book
from utils.author_detection import detect_author, detect_canonical_title, detect_church_document
from utils.language import detect_latin_heuristic, normalize_lang

PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "pdfs")

# ─── Detecção de tradutor nas primeiras páginas ───────────────────────────────

_BAD_TRANSLATOR_WORDS = frozenset({
    "edição", "edicao", "editora", "coleção", "colecao", "prefácio", "prefacio",
    "introducao", "revisão", "revisao", "apresentação", "coordenação", "organizacao",
    "volume", "tomo", "copyright", "isbn", "paulus", "loyola", "vozes", "paulinas",
})

_TRANSLATOR_RE = [
    re.compile(r"[Tt]radu[çc][aã]o\s+d[eo]\s+([A-ZÀ-Ÿ][A-Za-zÀ-ÿ '\-\.]{3,80})(?:\n|[,;]|$)"),
    re.compile(r"[Tt]raduzido\s+por\s+([A-ZÀ-Ÿ][A-Za-zÀ-ÿ '\-\.]{3,80})(?:\n|[,;]|$)"),
    re.compile(r"[Tt]radutora?\s*:\s*([A-ZÀ-Ÿ][A-Za-zÀ-ÿ '\-\.]{3,80})(?:\n|[,;]|$)"),
    re.compile(r"[Tt]ranslated\s+by\s+([A-Z][A-Za-z '\-\.]{3,80})(?:\n|[,;]|$)"),
]

_PUBLISHER_RE = [
    (re.compile(r"\bPaulus\b", re.IGNORECASE), "Paulus"),
    (re.compile(r"\b(?:Editora|Edi[çc][õo]es)\s+Loyola\b|\bLoyola\s+Editora\b", re.IGNORECASE), "Loyola"),
    (re.compile(r"\bVozes\b", re.IGNORECASE), "Vozes"),
    (re.compile(r"\bPaulinas\b", re.IGNORECASE), "Paulinas"),
    (re.compile(r"\bEcclesiae\b", re.IGNORECASE), "Ecclesiae"),
    (re.compile(r"\bEditora\s+Fam[ií]lia\s+Cat[oó]lica\b|\bFam[ií]lia\s+Cat[oó]lica\b", re.IGNORECASE), "Editora Família Católica"),
    (re.compile(r"\bApostolado\s+Sociedade\s+Cat[oó]lica\b", re.IGNORECASE), "Apostolado Sociedade Católica"),
    (re.compile(r"\bRealeza\b", re.IGNORECASE), "Realeza"),
    (re.compile(r"\bQuadrante\b", re.IGNORECASE), "Quadrante"),
    (re.compile(r"\bCultor\s+de\s+Livros\b", re.IGNORECASE), "Cultor de Livros"),
    (re.compile(r"\bPerman[eê]ncia\b", re.IGNORECASE), "Permanência"),
    (re.compile(r"\bCristo\s+Rei\b", re.IGNORECASE), "Cristo Rei"),
    (re.compile(r"\bCl[eé]ofas\b", re.IGNORECASE), "Cléofas"),
    (re.compile(r"\bMolokai\b", re.IGNORECASE), "Molokai"),
    (re.compile(r"\bSantu[aá]rio\b", re.IGNORECASE), "Santuário"),
]


def _detect_translator(text: str) -> str | None:
    for pattern in _TRANSLATOR_RE:
        m = pattern.search(text)
        if m:
            name = m.group(1).strip().rstrip(".,;:-")
            name = re.split(
                r"\b(?:revis[aã]o|edi[cç][aã]o|cole[cç][aã]o|pref[aá]cio|introdu[cç][aã]o)\b",
                name, flags=re.IGNORECASE,
            )[0].strip()
            if len(name) < 5 or len(name) > 80:
                continue
            if any(w in name.lower() for w in _BAD_TRANSLATOR_WORDS):
                continue
            parts = name.split()
            if sum(1 for p in parts if p[:1].isupper()) < 2:
                continue
            return name
    return None


def _detect_publisher(text: str) -> str | None:
    for pattern, label in _PUBLISHER_RE:
        if pattern.search(text):
            return label
    return None


# Status em memória: book_id → "processing" | "done" | "error"
_processing_status: dict[int, str] = {}
_status_lock = threading.Lock()


def _set_status(book_id: int, status: str, error: str | None = None) -> None:
    with _status_lock:
        _processing_status[book_id] = status

    try:
        with SessionLocal() as db:
            book = db.get(Book, book_id)
            if book is not None:
                book.ingest_status = status
                book.ingest_error = error
                db.commit()
    except Exception as exc:
        print(f"[ingest] could not persist status for book_id={book_id}: {exc}")


def get_processing_status(book_id: int) -> str:
    return get_processing_state(book_id)[0]


def get_processing_state(book_id: int) -> tuple[str, str | None]:
    with _status_lock:
        cached = _processing_status.get(book_id)

    try:
        with SessionLocal() as db:
            book = db.get(Book, book_id)
            if book is not None:
                return cached or book.ingest_status or "done", book.ingest_error
    except Exception:
        pass

    return cached or "done", None


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)


def _detect_lang(text: str) -> str:
    """Detecta idioma. Prioriza heurística latina antes do langdetect."""
    if not text.strip():
        return "la"
    if detect_latin_heuristic(text):
        return "la"
    try:
        return detect(text)
    except LangDetectException:
        return "la"


def _count_greek_chars(text: str) -> int:
    return sum(
        1
        for ch in text
        if "\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff"
    )


def _detect_extracted_language(
    pages: list[dict],
    current_language: str | None,
    collection: str | None,
) -> str | None:
    """
    Detecta combinações de idiomas depois da extração completa.
    Isso pega casos como PG001, cujo OCR contém latim e grego na mesma obra.
    """
    current = current_language or ""
    normalized = normalize_lang(current)
    parts = set(normalized.split("+")) if normalized else set()
    collection_code = (collection or "").upper().strip()

    # Não reclassifica traduções modernas por causa de citações soltas em rodapé.
    if parts & {"pt", "es", "fr", "it", "en", "de"} and collection_code not in {"PG", "PL", "PO"}:
        return current_language

    sample_parts: list[str] = []
    total_chars = 0
    greek_chars = 0
    for page in pages:
        text = page.get("text", "") if isinstance(page, dict) else str(page)
        if not text:
            continue
        greek_chars += _count_greek_chars(text)
        if total_chars < 200_000:
            remaining = 200_000 - total_chars
            sample_parts.append(text[:remaining])
            total_chars += min(len(text), remaining)

    sample = "\n".join(sample_parts)
    has_latin = "la" in parts or detect_latin_heuristic(sample)
    has_greek = "grc" in parts or "el" in parts or greek_chars >= 20

    labels: list[str] = []
    if has_latin:
        labels.append("latim")
    if has_greek:
        labels.append("grego")

    if labels:
        return "/".join(labels)
    return current_language


def _extract_sample_pages(pdf_path: str, n: int = 8) -> list[dict]:
    """Extrai as primeiras N páginas com pdfplumber (rápido, sem OCR).
    N=8 porque PDFs com capa/índice imageados só têm texto a partir da p. 4-5.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return [
                {"page_number": i + 1, "text": (page.extract_text() or "")}
                for i, page in enumerate(pdf.pages[:n])
            ]
    except Exception:
        return []


class IngestionService:
    def __init__(self) -> None:
        self.text_search = TextSearchClient()
        self.semantic_search = SemanticSearchClient()
        self.extractor = PDFExtractor()
        self.chunker = Chunker()

    # ─── Fluxo manual (POST /books/{id}/ingest-pdf) ──────────────────────────

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

            max_seq = db.query(func.max(Chunk.sequence_index)).filter(
                Chunk.book_id == book_id
            ).scalar()
            next_seq = (max_seq + 1) if max_seq is not None else 0

        pdf_storage = get_pdf_storage()
        stored_pdf = pdf_storage.save_pdf(book_id, original_filename, pdf_bytes)
        stored_path = stored_pdf.stored_path
        local_pdf_path = stored_pdf.local_path

        try:
            pages = self.extractor.extract(local_pdf_path)
            document_meta: dict = {}
            if volume_number is not None:
                document_meta["volume_number"] = volume_number
            raw_chunks = self.chunker.chunk(pages, document_meta)
        except Exception as exc:
            pdf_storage.delete_pdf(stored_path)
            raise HTTPException(status_code=500, detail=f"Falha na extração do PDF: {exc}")

        if not raw_chunks:
            pdf_storage.delete_pdf(stored_path)
            raise HTTPException(status_code=422, detail="Nenhum texto extraído do PDF.")

        for i, chunk_data in enumerate(raw_chunks):
            chunk_data["sequence_index"] = next_seq + i

        content_sample = " ".join(
            p.get("text", "") for p in pages[:3] if isinstance(p, dict)
        )
        if not content_sample and pages:
            content_sample = " ".join(str(p) for p in pages[:3])
        content_sample = content_sample[:1000]

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

            db.flush()

            book = db.get(Book, book_id)
            semantic_language = normalize_lang(book.language if book else "la")
            es_items: list[tuple[int, dict]] = []
            chroma_items: list[tuple[int, str, dict]] = []
            for chunk in chunk_records:
                es_items.append((
                    chunk.id,
                    {
                        "book_id": book_id,
                        "book_file_id": book_file.id,
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
                    },
                ))
                chroma_items.append((
                    chunk.id,
                    chunk.text,
                    {
                        "book_id": book_id,
                        "book_file_id": book_file.id,
                        "author": book.author,
                        "work_title": book.title,
                    },
                ))

            try:
                self.text_search.index_chunks(es_items)
                self.semantic_search.index_chunks(chroma_items, language=semantic_language)

            except Exception as exc:
                db.rollback()
                pdf_storage.delete_pdf(stored_path)
                raise HTTPException(
                    status_code=500,
                    detail=f"Falha ao indexar no motor de busca: {exc}",
                )

            db.commit()
            db.refresh(book_file)
            return book_file, len(chunk_records)

    # ─── Fluxo automático (POST /books/ingest-auto) ───────────────────────────

    def ingest_auto(
        self,
        pdf_bytes: bytes,
        original_filename: str,
        title_override: str | None = None,
        editor: str | None = None,
        translator: str | None = None,
    ) -> dict:
        """
        Fase 1 (síncrona, rápida): detecta metadados das primeiras páginas,
        cria o Book e responde imediatamente.

        Fase 2 (background thread): extrai todas as páginas, cria chunks,
        indexa ES + ChromaDB.
        """
        os.makedirs(PDF_DIR, exist_ok=True)

        # Fase 1 — amostra rápida das 3 primeiras páginas (sem OCR completo)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            sample_pages = _extract_sample_pages(tmp_path, n=8)
        finally:
            os.remove(tmp_path)

        full_sample_text = "\n".join(p.get("text", "") for p in sample_pages)
        content_sample = full_sample_text[:1000]

        raw_title = (
            title_override
            or os.path.splitext(original_filename)[0]
               .replace("_", " ").replace("-", " ").strip()
        )

        metadata_text = raw_title + "\n" + content_sample
        parsed = parse_patristic_book(metadata_text)
        detected_author = parsed.author
        canonical_title = parsed.canonical_title or raw_title
        language = parsed.language or _detect_lang(content_sample)
        # "PT" para edições Paulus em português; None para desconhecido (não assumir PG/PL)
        collection = "PT" if (parsed.publisher == "Paulus" and language == "pt") else None

        # Auto-detecção de editora e tradutor (quando não fornecidos pelo usuário)
        auto_editor = editor or parsed.publisher or _detect_publisher(full_sample_text) or None
        auto_translator = translator or _detect_translator(full_sample_text) or None
        # Fallback: editoras como Paulus são responsáveis pela tradução quando não há tradutor individual
        if not auto_translator and auto_editor:
            auto_translator = f"{auto_editor} Editora" if not auto_editor.lower().endswith("editora") else auto_editor
        tradition = parsed.patristic_tradition
        section = parsed.library_section or "patristica"
        doctype = None
        edition_label = ""

        # Auto-detecção de documentos oficiais da Igreja (CIC, CCEO, Catecismo, encíclicas…)
        church_meta = detect_church_document(raw_title, content_sample)
        if church_meta:
            detected_author = church_meta["author"]
            canonical_title = church_meta["canonical_title"] or canonical_title
            collection = church_meta["collection"]
            section = church_meta["library_section"]
            doctype = church_meta["document_type"]
            tradition = None
            edition_label = church_meta["edition_label"]

        final_canonical_author = church_meta["canonical_author"] if church_meta else parsed.canonical_author
        final_canonical_title = (
            church_meta["canonical_title"]
            if church_meta
            else (parsed.canonical_title if parsed.canonical_author else None)
        )

        # Criar Book no banco
        with SessionLocal() as db:
            book = Book(
                collection=collection,
                title=canonical_title,
                author=detected_author or "Desconhecido",
                language=language,
                edition_label=edition_label,
                source_label="",
                is_primary_source=True,
                library_section=section,
                patristic_tradition=tradition,
                document_type=doctype,
                canonical_author=final_canonical_author,
                canonical_title=final_canonical_title,
                ingest_status="processing",
                ingest_error=None,
            )
            db.add(book)
            db.commit()
            db.refresh(book)
            book_id = book.id
            book_snapshot = {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "collection": book.collection,
                "language": book.language,
                "canonical_author": book.canonical_author,
                "canonical_title": book.canonical_title,
                "library_section": book.library_section,
                "patristic_tradition": book.patristic_tradition,
                "ingest_error": book.ingest_error,
            }

        # Salvar PDF no backend configurado (local por padrao, S3/R2 quando ativado)
        pdf_storage = get_pdf_storage()
        stored_pdf = pdf_storage.save_pdf(book_id, original_filename, pdf_bytes)
        stored_path = stored_pdf.stored_path

        # Criar BookFile na fase síncrona para ter file_id real na resposta
        with SessionLocal() as db:
            book_file = BookFile(
                book_id=book_id,
                original_filename=original_filename,
                stored_path=stored_path,
                volume_number=None,
                editor=auto_editor,
                translator=auto_translator,
            )
            db.add(book_file)
            db.commit()
            db.refresh(book_file)
            file_id = book_file.id

        # Marcar como em processamento e iniciar thread
        _set_status(book_id, "processing")
        thread = threading.Thread(
            target=self._ingest_background,
            args=(book_id, file_id, stored_path),
            daemon=True,
        )
        thread.start()

        return {
            **book_snapshot,
            "file_id": file_id,
            "chunks_indexed": 0,
            "status": "processing",
        }

    # ─── Remoção completa de um livro ────────────────────────────────────────

    def delete_book(self, book_id: int) -> None:
        """
        Remove um livro e todo seu conteúdo:
        ES, ChromaDB, Chunks, BookFiles, PDF em disco e o Book em si.
        """
        from fastapi import HTTPException

        with SessionLocal() as db:
            book = db.get(Book, book_id)
            if book is None:
                raise HTTPException(status_code=404, detail="Livro não encontrado.")

            chunks = db.query(Chunk).filter(Chunk.book_id == book_id).all()

            # 1. Remover do ES e ChromaDB
            for chunk in chunks:
                self.text_search.delete_chunk(chunk.id)
                self.semantic_search.delete_chunk(chunk.id)

            # 2. Remover PDFs do storage configurado
            files = db.query(BookFile).filter(BookFile.book_id == book_id).all()
            pdf_storage = get_pdf_storage()
            for f in files:
                pdf_storage.delete_pdf(f.stored_path)

            # 3. Deletar registros (Translation → Chunk → BookFile → Book)
            chunk_ids = [c.id for c in chunks]
            if chunk_ids:
                db.query(Translation).filter(Translation.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
            db.query(Chunk).filter(Chunk.book_id == book_id).delete()
            db.query(BookFile).filter(BookFile.book_id == book_id).delete()
            db.delete(book)
            db.commit()

    def _ingest_background(
        self,
        book_id: int,
        book_file_id: int,
        stored_path: str,
    ) -> None:
        """Thread de background: extrai todas as páginas, cria chunks, indexa."""
        try:
            local_pdf_path = get_pdf_storage().resolve_for_processing(stored_path)
            if not local_pdf_path:
                _set_status(book_id, "error", f"PDF file not found: {stored_path}")
                return

            pages = self.extractor.extract(local_pdf_path)

            with SessionLocal() as db:
                book = db.get(Book, book_id)
                if book is not None:
                    detected_language = _detect_extracted_language(
                        pages,
                        book.language,
                        book.collection,
                    )
                    if detected_language and detected_language != book.language:
                        book.language = detected_language
                        db.commit()

            raw_chunks = self.chunker.chunk(pages, {})

            if not raw_chunks:
                # Diagnóstico: conta páginas do PDF para distinguir falha de OCR de PDF vazio
                try:
                    with pdfplumber.open(local_pdf_path) as _pdf:
                        _total_pages = len(_pdf.pages)
                except Exception:
                    _total_pages = 0
                _pages_extracted = len(pages) if pages else 0
                error_message = (
                    f"PDF has {_total_pages} pages, extractor returned "
                    f"{_pages_extracted} pages, but chunker generated 0 chunks."
                )
                if _total_pages >= 10:
                    error_message += " Possible OCR/Tesseract failure."
                print(
                    f"[ingest] book_id={book_id}: PDF tem {_total_pages} páginas, "
                    f"extrator retornou {_pages_extracted} páginas, "
                    f"chunker gerou 0 chunks — marcando como erro."
                )
                _set_status(book_id, "error", error_message)
                return

            with SessionLocal() as db:
                max_seq = db.query(func.max(Chunk.sequence_index)).filter(
                    Chunk.book_id == book_id
                ).scalar()
                next_seq = (max_seq + 1) if max_seq is not None else 0

            for i, chunk_data in enumerate(raw_chunks):
                chunk_data["sequence_index"] = next_seq + i

            with SessionLocal() as db:
                chunk_records: list[Chunk] = []
                for chunk_data in raw_chunks:
                    chunk = Chunk(
                        book_id=book_id,
                        book_file_id=book_file_id,
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

                db.flush()

                book = db.get(Book, book_id)
                semantic_language = normalize_lang(book.language if book else "la")
                es_items: list[tuple[int, dict]] = []
                chroma_items: list[tuple[int, str, dict]] = []
                for chunk in chunk_records:
                    es_items.append((
                        chunk.id,
                        {
                            "book_id": book_id,
                            "book_file_id": book_file_id,
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
                        },
                    ))
                    chroma_items.append((
                        chunk.id,
                        chunk.text,
                        {
                            "book_id": book_id,
                            "book_file_id": book_file_id,
                            "author": book.author,
                            "work_title": book.title,
                        },
                    ))
                db.commit()

            try:
                self.text_search.index_chunks(es_items)
                self.semantic_search.index_chunks(chroma_items, language=semantic_language)
            except Exception as exc:
                _set_status(book_id, "error", f"Search indexing failed: {exc}")
                return

            _set_status(book_id, "done")

        except Exception as exc:
            _set_status(book_id, "error", f"Background ingest failed: {exc}")
