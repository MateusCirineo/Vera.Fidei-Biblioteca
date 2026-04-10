from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict


class BookCreate(BaseModel):
    collection: str
    title: str
    author: str
    language: str
    edition_label: str = ""
    source_label: str = ""
    is_primary_source: bool = True


class BookResponse(BaseModel):
    id: int
    collection: str
    title: str
    author: str
    language: str
    edition_label: str
    source_label: str
    is_primary_source: bool
    chunk_count: int


class BookFileResponse(BaseModel):
    id: int
    book_id: int
    original_filename: str
    volume_number: int | None
    editor: str | None
    translator: str | None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class IngestPDFResponse(BaseModel):
    book_id: int
    file_id: int
    chunks_indexed: int
    volume_number: int | None
    editor: str | None
    translator: str | None
