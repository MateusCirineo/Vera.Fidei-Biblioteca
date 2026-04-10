from pydantic import BaseModel, Field


class VerifyCitationRequest(BaseModel):
    quote: str = Field(..., min_length=3)
    attributed_to: str = Field(..., min_length=2)
    language: str | None = None


class MatchReference(BaseModel):
    collection: str
    volume: int | None = None
    column_start: int | None = None
    column_end: int | None = None
    chapter_or_section: str | None = None
    pdf_page: int | None = None
    visual_anchor: str | None = None


class VerifyCitationResponse(BaseModel):
    status_code: str
    label: str
    confidence: str
    author: str | None = None
    work: str | None = None
    reference: MatchReference | None = None
    original_language: str | None = None
    source_version: str | None = None
    matched_excerpt: str | None = None
    context_before: str | None = None
    context_after: str | None = None
    explanation: str | None = None
