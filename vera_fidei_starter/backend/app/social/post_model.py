from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SocialPostCandidate:
    """Conteúdo de uma publicação ligado a uma única fonte do acervo.

    Autor, obra, trecho, referência e página nunca são aceitos separadamente:
    todos os campos abaixo precisam nascer do mesmo ``chunk_id``.
    """

    chunk_id: int
    book_id: int
    book_file_id: int | None
    author: str
    work_title: str
    quote: str
    original_text: str
    language: str
    collection: str | None = None
    volume: int | None = None
    edition_label: str | None = None
    chapter_or_section: str | None = None
    pdf_page: int | None = None
    column_start: int | None = None
    column_end: int | None = None
    stored_path: str | None = None
    author_dates: str | None = None
    century: str | None = None
    day_of_year: int = 0
    source_fingerprint: str = ""
    highlight_terms: list[str] = field(default_factory=list)

    @property
    def quote_full(self) -> str:
        return self.quote

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
