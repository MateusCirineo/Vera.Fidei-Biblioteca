from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from utils.language import classify_book


class BookCreate(BaseModel):
    collection: str | None = None
    title: str
    author: str
    language: str
    edition_label: str = ""
    source_label: str = ""
    is_primary_source: bool = True

    # Classificação automática — preenchida se não fornecida
    library_section: str | None = None
    patristic_tradition: str | None = None
    document_type: str | None = None

    # Campos canônicos e metadados de documento
    canonical_author: str | None = None
    canonical_title: str | None = None
    pope: str | None = None
    document_year: int | None = None
    is_ecumenical: bool | None = None
    document_status: str | None = None

    @model_validator(mode="after")
    def auto_classify(self) -> "BookCreate":
        if self.library_section is None and self.collection is not None:
            section, tradition, doctype = classify_book(
                self.collection, self.language, self.is_primary_source
            )
            self.library_section = section
            self.patristic_tradition = tradition
            self.document_type = doctype
        return self


class BookFileResponse(BaseModel):
    id: int
    book_id: int
    original_filename: str
    volume_number: int | None
    editor: str | None
    translator: str | None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class BookResponse(BaseModel):
    id: int
    collection: str | None
    title: str
    author: str
    language: str
    edition_label: str
    source_label: str
    is_primary_source: bool
    chunk_count: int

    # Organização da biblioteca
    library_section: str | None
    patristic_tradition: str | None
    document_type: str | None

    # Campos canônicos e metadados de documento
    canonical_author: str | None
    canonical_title: str | None
    pope: str | None
    document_year: int | None
    is_ecumenical: bool | None
    document_status: str | None
    volume_number: int | None = None

    # Arquivos vinculados (populados via GET /books/{id})
    files: list[BookFileResponse] | None = None

    model_config = ConfigDict(from_attributes=True)


class IngestPDFResponse(BaseModel):
    book_id: int
    file_id: int
    chunks_indexed: int
    volume_number: int | None
    editor: str | None
    translator: str | None


class AutoIngestResponse(BaseModel):
    id: int
    file_id: int | None
    title: str
    author: str
    collection: str | None
    language: str
    canonical_author: str | None
    canonical_title: str | None
    library_section: str | None
    patristic_tradition: str | None
    chunks_indexed: int
    status: str  # "processing" | "done" | "error"


class BookStatusResponse(BaseModel):
    book_id: int
    status: str   # "processing" | "done" | "error"
    chunks_indexed: int
