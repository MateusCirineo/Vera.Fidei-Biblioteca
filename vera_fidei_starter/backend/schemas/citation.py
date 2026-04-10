from pydantic import BaseModel, Field


class VerifyCitationRequest(BaseModel):
    quote: str = Field(..., min_length=3)
    attributed_to: str = Field(..., min_length=2)
    language: str | None = None


class MatchReference(BaseModel):
    """Localização exata do trecho na fonte primária."""
    collection: str
    volume: int | None = None
    column_start: int | None = None
    column_end: int | None = None
    chapter_or_section: str | None = None
    pdf_page: int | None = None
    visual_anchor: str | None = None
    # Proveniência completa da versão
    edition_label: str | None = None
    source_label: str | None = None
    language: str | None = None
    editor: str | None = None
    translator: str | None = None
    is_primary_source: bool = True
    # Navegação no PDF
    pdf_file_id: int | None = None


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
    matched_translation: str | None = None
    translation_language: str | None = None
    translation_fidelity: str | None = None
    translator: str | None = None
