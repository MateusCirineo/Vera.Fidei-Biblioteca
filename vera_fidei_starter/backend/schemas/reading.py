from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, model_validator


ReadingEvent = Literal["open", "progress", "restart"]


class ReadingProgressUpdate(BaseModel):
    """One deliberate reading-session update from the PDF viewer."""

    book_id: int | None = Field(default=None, ge=1)
    current_page: int = Field(ge=1)
    total_pages: int | None = Field(default=None, ge=1)
    event: ReadingEvent = "progress"
    base_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_page_range(self) -> "ReadingProgressUpdate":
        if self.total_pages is not None and self.current_page > self.total_pages:
            raise ValueError("current_page nao pode ser maior que total_pages")
        return self


class ReadingBookMetadata(BaseModel):
    id: int
    title: str
    author: str
    collection: str | None
    language: str
    edition_label: str
    canonical_title: str | None
    canonical_author: str | None


class ReadingFileMetadata(BaseModel):
    id: int
    original_filename: str
    volume_number: int | None
    editor: str | None
    translator: str | None


class ReadingProgressResponse(BaseModel):
    book_file_id: int
    book_id: int
    revision: int
    current_page: int
    total_pages: int | None
    progress_percent: float | None
    completed: bool
    start_page: int
    end_page: int | None
    first_opened_at: datetime.datetime
    last_read_at: datetime.datetime
    viewer_href: str
    book: ReadingBookMetadata
    file: ReadingFileMetadata

    @field_serializer("first_opened_at", "last_read_at")
    def serialize_utc_datetime(self, value: datetime.datetime) -> str:
        """The database stores naive UTC; the API must make that explicit."""

        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        else:
            value = value.astimezone(datetime.timezone.utc)
        return value.isoformat().replace("+00:00", "Z")


class ReadingHistoryResponse(BaseModel):
    items: list[ReadingProgressResponse]
    total: int
    limit: int
    offset: int
