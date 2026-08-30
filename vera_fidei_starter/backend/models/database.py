from __future__ import annotations

import datetime
import threading

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from core.config import settings
import json


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(30), default="fiel")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    billing_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    billing_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    billing_current_period_end: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    billing_cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    google_play_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    # Incrementing this value invalidates every JWT issued with an older value.
    # Existing tokens did not carry the claim and are treated as version zero,
    # which keeps them compatible until the next password reset.
    session_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    avatar_content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar_updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    verifications: Mapped[list["VerificationHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    favorites: Mapped[list["UserFavorite"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reading_progress: Mapped[list["UserReadingProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserFavorite(Base):
    __tablename__ = "user_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "item_id", name="uq_user_favorites_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    href: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    user: Mapped["User"] = relationship(back_populates="favorites")


class VerificationHistory(Base):
    __tablename__ = "verification_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    citation_text: Mapped[str] = mapped_column(Text)
    attributed_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    user: Mapped["User | None"] = relationship(back_populates="verifications")


class BillingRequest(Base):
    __tablename__ = "billing_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plan: Mapped[str] = mapped_column(String(30))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    provider: Mapped[str] = mapped_column(String(30), default="manual_pix")
    reference_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    user: Mapped["User"] = relationship()


class BillingSubscription(Base):
    """Provider subscription state without exposing provider secrets to clients."""

    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "package_name",
            "purchase_token_hash",
            name="uq_billing_subscription_purchase_token",
        ),
        UniqueConstraint(
            "provider",
            "external_subscription_id",
            name="uq_billing_subscription_external_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    package_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    provider_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purchase_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    purchase_token_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_purchase_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_status: Mapped[str] = mapped_column(String(80), default="unknown", nullable=False)
    entitlement_state: Mapped[str] = mapped_column(String(50), default="inactive", nullable=False)
    acknowledgement_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    current_period_end: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    auto_renew_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    test_purchase: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider_event_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    last_verified_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    last_order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    user: Mapped["User"] = relationship()
    items: Mapped[list["BillingSubscriptionItem"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )


class BillingSubscriptionItem(Base):
    __tablename__ = "billing_subscription_items"
    __table_args__ = (
        UniqueConstraint(
            "billing_subscription_id",
            "item_key",
            name="uq_billing_subscription_item_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    billing_subscription_id: Mapped[int] = mapped_column(
        ForeignKey("billing_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_key: Mapped[str] = mapped_column(String(700), nullable=False)
    product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    base_plan_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    offer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(String(30), nullable=False)
    expiry_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    auto_renew_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    entitled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    subscription: Mapped["BillingSubscription"] = relationship(back_populates="items")


class BillingEvent(Base):
    """Idempotency ledger. Payloads and raw purchase tokens are never stored."""

    __tablename__ = "billing_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_billing_event_provider_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    package_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purchase_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="received", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    processed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)


class BillingRateLimit(Base):
    """Cross-worker per-user limiter for sensitive billing synchronization."""

    __tablename__ = "billing_rate_limits"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", name="uq_billing_rate_limit_user_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    window_started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    admin: Mapped["User"] = relationship(foreign_keys=[admin_user_id])
    members: Mapped[list["InstitutionMember"]] = relationship(back_populates="institution", cascade="all, delete-orphan")


class InstitutionMember(Base):
    __tablename__ = "institution_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20), default="membro")
    joined_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    institution: Mapped["Institution"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key_hash: Mapped[str] = mapped_column(String(64))
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship()


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    user: Mapped["User"] = relationship()


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    user: Mapped["User"] = relationship()


class SearchUsage(Base):
    __tablename__ = "search_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_search_usage_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    usage_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship()


class SiteVisitor(Base):
    """First-party, pseudonymous browser used for aggregate site metrics."""

    __tablename__ = "site_visitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visitor_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False, index=True
    )
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False, index=True
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_path: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SitePageView(Base):
    """A route view without IP address, user-agent or account identity."""

    __tablename__ = "site_page_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visitor_id: Mapped[int] = mapped_column(
        ForeignKey("site_visitors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    viewed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False, index=True
    )


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(50))
    edition_label: Mapped[str] = mapped_column(String(255), default="")
    source_label: Mapped[str] = mapped_column(String(255), default="")
    is_primary_source: Mapped[bool] = mapped_column(Boolean, default=True)

    # Organização da biblioteca
    # library_section:     "patristica" | "documentos"
    # patristic_tradition: "grega" | "oriental" | "latina" | "portuguesa"
    # document_type:       "concilio" | "bula" | "enciclica" | "constituicao_apostolica" | "carta_apostolica" | "outro"
    library_section: Mapped[str | None] = mapped_column(String(30), nullable=True)
    patristic_tradition: Mapped[str | None] = mapped_column(String(30), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Campos canônicos (auto-detectados na ingestão)
    canonical_author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Metadados para Documentos da Igreja
    pope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_ecumenical: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    document_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    volume_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingest_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ingest_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan"
    )
    files: Mapped[list["BookFile"]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan"
    )
    reading_progress: Mapped[list["UserReadingProgress"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    book_file_id: Mapped[int | None] = mapped_column(ForeignKey("book_files.id"), nullable=True)
    chapter_or_section: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(Text)
    sequence_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chunk_author: Mapped[str | None] = mapped_column(String(255), nullable=True)

    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_offset_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_offset_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_anchor: Mapped[str] = mapped_column(String(100), default="")
    # OCR is never equivalent to a source-verified transcription. These fields
    # keep the extraction origin explicit so public citation paths can fail
    # closed instead of presenting machine guesses as words from the edition.
    extraction_method: Mapped[str] = mapped_column(String(30), default="legacy_unknown")
    source_fidelity: Mapped[str] = mapped_column(String(30), default="unverified")
    fidelity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fidelity_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)

    book: Mapped["Book"] = relationship(back_populates="chunks")
    source_file: Mapped["BookFile | None"] = relationship(back_populates="chunks")
    translations: Mapped[list["Translation"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )


class VerifiedPassage(Base):
    """Literal transcription checked against one physical PDF page."""

    __tablename__ = "verified_passages"
    __table_args__ = (
        UniqueConstraint("book_id", "pdf_page", "text_sha256", name="uq_verified_passage_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    book_file_id: Mapped[int | None] = mapped_column(ForeignKey("book_files.id", ondelete="CASCADE"), nullable=True)
    pdf_page: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str | None] = mapped_column(String(30), nullable=True)
    verification_method: Mapped[str] = mapped_column(String(50), default="visual_pdf")
    evidence_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class VerifiedPageReview(Base):
    """Audited full-page transcription checked against rendered PDF pixels."""

    __tablename__ = "verified_page_reviews"
    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "pdf_page",
            "text_sha256",
            "pdf_sha256",
            "render_pixel_sha256",
            name="uq_verified_page_review_evidence",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    book_file_id: Mapped[int] = mapped_column(ForeignKey("book_files.id", ondelete="CASCADE"), nullable=False)
    pdf_page: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    pdf_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    render_pixel_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    render_dpi: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(30), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    verification_method: Mapped[str] = mapped_column(String(50), default="visual_pdf")
    evidence_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class BookFile(Base):
    __tablename__ = "book_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    volume_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    editor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    translator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    book: Mapped["Book"] = relationship(back_populates="files")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="source_file")
    reading_progress: Mapped[list["UserReadingProgress"]] = relationship(
        back_populates="book_file", cascade="all, delete-orphan"
    )


class UserReadingProgress(Base):
    """Durable, account-scoped resume position for one concrete PDF edition."""

    __tablename__ = "user_reading_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "book_id",
            "book_file_id",
            name="uq_user_reading_progress_file",
        ),
        CheckConstraint("current_page >= 1", name="ck_user_reading_progress_current_page"),
        CheckConstraint(
            "total_pages IS NULL OR total_pages >= 1",
            name="ck_user_reading_progress_total_pages",
        ),
        CheckConstraint(
            "total_pages IS NULL OR current_page <= total_pages",
            name="ck_user_reading_progress_page_range",
        ),
        CheckConstraint("revision >= 1", name="ck_user_reading_progress_revision"),
        Index(
            "idx_user_reading_progress_history",
            "user_id",
            "last_read_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    book_file_id: Mapped[int] = mapped_column(
        ForeignKey("book_files.id", ondelete="CASCADE"), nullable=False
    )
    current_page: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_opened_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )
    last_read_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    user: Mapped["User"] = relationship(back_populates="reading_progress")
    book: Mapped["Book"] = relationship(back_populates="reading_progress")
    book_file: Mapped["BookFile"] = relationship(back_populates="reading_progress")


class Translation(Base):
    __tablename__ = "translations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.id"))
    language: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    translator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    edition_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    chunk: Mapped["Chunk"] = relationship(back_populates="translations")


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
_init_db_lock = threading.Lock()
_init_db_complete = False


def init_db(reset: bool = False) -> None:
    global _init_db_complete
    with _init_db_lock:
        if _init_db_complete and not reset:
            return
        if reset:
            Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        _migrate_add_library_columns()
        _backfill_legacy_billing_subscriptions()
        _init_db_complete = True


def _migrate_add_library_columns() -> None:
    """Migração incremental: adiciona colunas de organização e enriquecimento se não existirem."""
    migrations = [
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS library_section VARCHAR(30)",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS patristic_tradition VARCHAR(30)",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS document_type VARCHAR(50)",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS canonical_author VARCHAR(255)",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS canonical_title VARCHAR(255)",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS pope VARCHAR(255)",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS document_year INTEGER",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS is_ecumenical BOOLEAN",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS document_status VARCHAR(50)",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_author VARCHAR(255)",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(30) DEFAULT 'legacy_unknown'",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS source_fidelity VARCHAR(30) DEFAULT 'unverified'",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS fidelity_score DOUBLE PRECISION",
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS fidelity_reasons TEXT",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS volume_number INTEGER",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS ingest_status VARCHAR(30)",
        "ALTER TABLE books ADD COLUMN IF NOT EXISTS ingest_error TEXT",
        "ALTER TABLE book_files ADD COLUMN IF NOT EXISTS volume_number INTEGER",
        "ALTER TABLE book_files ADD COLUMN IF NOT EXISTS editor VARCHAR(255)",
        "ALTER TABLE book_files ADD COLUMN IF NOT EXISTS translator VARCHAR(255)",
        "ALTER TABLE book_files ADD COLUMN IF NOT EXISTS created_at TIMESTAMP",
        # Fix spelling variant: "Irineu" → "Ireneu" (key in PATRISTIC_AUTHORS)
        "UPDATE books SET canonical_author = 'Santo Ireneu de Lião' WHERE canonical_author = 'Santo Irineu de Lião'",
        # Indexes for performance — critical for COUNT queries run per-book/per-author
        "CREATE INDEX IF NOT EXISTS idx_chunks_book_id ON chunks(book_id)",
        "CREATE INDEX IF NOT EXISTS idx_chunks_chunk_author ON chunks(chunk_author)",
        "CREATE INDEX IF NOT EXISTS idx_chunks_source_fidelity ON chunks(source_fidelity)",
        "CREATE INDEX IF NOT EXISTS idx_books_canonical_author ON books(canonical_author)",
        "CREATE INDEX IF NOT EXISTS idx_books_library_section ON books(library_section)",
        # Tabela de usuários
        "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, name VARCHAR(255) NOT NULL, password_hash VARCHAR(255) NOT NULL, plan VARCHAR(30) DEFAULT 'fiel', is_active BOOLEAN DEFAULT TRUE, session_version INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_provider VARCHAR(30)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_customer_id VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_subscription_id VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_status VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_current_period_end TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_cancel_at_period_end BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_play_account_id VARCHAR(64)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_data BYTEA",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_content_type VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_updated_at TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS idx_users_billing_customer_id ON users(billing_customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_billing_subscription_id ON users(billing_subscription_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_play_account_id ON users(google_play_account_id) WHERE google_play_account_id IS NOT NULL",
        "UPDATE users SET plan = 'magisterio', billing_status = 'owner', billing_cancel_at_period_end = FALSE WHERE lower(email) = 'mateuscirineo@gmail.com'",
        "CREATE TABLE IF NOT EXISTS user_favorites (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, kind VARCHAR(30) NOT NULL, item_id VARCHAR(255) NOT NULL, title VARCHAR(500) NOT NULL, subtitle VARCHAR(500), href VARCHAR(500) NOT NULL, source VARCHAR(255), metadata_json TEXT, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW())",
        "ALTER TABLE user_favorites DROP CONSTRAINT IF EXISTS user_favorites_user_id_fkey",
        "ALTER TABLE user_favorites ADD CONSTRAINT user_favorites_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_favorites_unique ON user_favorites(user_id, kind, item_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_favorites_user_kind ON user_favorites(user_id, kind)",
        "CREATE TABLE IF NOT EXISTS user_reading_progress (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE, book_file_id INTEGER NOT NULL REFERENCES book_files(id) ON DELETE CASCADE, current_page INTEGER NOT NULL DEFAULT 1 CHECK (current_page >= 1), total_pages INTEGER CHECK (total_pages IS NULL OR total_pages >= 1), completed BOOLEAN NOT NULL DEFAULT FALSE, revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1), first_opened_at TIMESTAMP NOT NULL DEFAULT NOW(), last_read_at TIMESTAMP NOT NULL DEFAULT NOW(), CONSTRAINT ck_user_reading_progress_page_range CHECK (total_pages IS NULL OR current_page <= total_pages))",
        "ALTER TABLE user_reading_progress ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1",
        "UPDATE user_reading_progress SET revision = 1 WHERE revision IS NULL OR revision < 1",
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_user_reading_progress_revision' AND conrelid = 'user_reading_progress'::regclass) THEN ALTER TABLE user_reading_progress ADD CONSTRAINT ck_user_reading_progress_revision CHECK (revision >= 1); END IF; END $$",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_reading_progress_file ON user_reading_progress(user_id, book_id, book_file_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_reading_progress_history ON user_reading_progress(user_id, last_read_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_user_reading_progress_file ON user_reading_progress(book_file_id)",
        # Tabela de histórico de verificações
        "CREATE TABLE IF NOT EXISTS verification_history (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, citation_text TEXT NOT NULL, attributed_to VARCHAR(255), status_code VARCHAR(50), label VARCHAR(100), confidence VARCHAR(20), author VARCHAR(255), work VARCHAR(255), reference_json TEXT, matched_excerpt TEXT, explanation TEXT, response_json TEXT, created_at TIMESTAMP DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS idx_vhist_user_id ON verification_history(user_id)",
        # Para ambientes onde a tabela já existe sem response_json
        "ALTER TABLE verification_history ADD COLUMN IF NOT EXISTS response_json TEXT",
        "CREATE TABLE IF NOT EXISTS billing_requests (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, plan VARCHAR(30) NOT NULL, amount_cents INTEGER NOT NULL, status VARCHAR(30) DEFAULT 'pending', provider VARCHAR(30) DEFAULT 'manual_pix', reference_code VARCHAR(80) UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW())",
        "ALTER TABLE billing_requests DROP CONSTRAINT IF EXISTS billing_requests_user_id_fkey",
        "ALTER TABLE billing_requests ADD CONSTRAINT billing_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE",
        "CREATE INDEX IF NOT EXISTS idx_billing_requests_user_id ON billing_requests(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_billing_requests_reference_code ON billing_requests(reference_code)",
        # Fase 4 — Gestão Institucional
        "CREATE TABLE IF NOT EXISTS institutions (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, admin_user_id INTEGER REFERENCES users(id), created_at TIMESTAMP DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS institution_members (id SERIAL PRIMARY KEY, institution_id INTEGER REFERENCES institutions(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, role VARCHAR(20) DEFAULT 'membro', joined_at TIMESTAMP DEFAULT NOW())",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_inst_members_unique ON institution_members(institution_id, user_id)",
        "CREATE TABLE IF NOT EXISTS api_keys (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, key_hash VARCHAR(64) NOT NULL, label VARCHAR(100), is_active BOOLEAN DEFAULT TRUE, usage_count INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT NOW(), last_used_at TIMESTAMP)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)",
        # Coluna de verificação de e-mail
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE",
        "UPDATE users SET email_verified = TRUE WHERE lower(email) = 'mateuscirineo@gmail.com'",
        # Tabela de tokens de redefinição de senha
        "CREATE TABLE IF NOT EXISTS password_reset_tokens (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, token_hash VARCHAR(64) UNIQUE NOT NULL, expires_at TIMESTAMP NOT NULL, used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS idx_prt_token_hash ON password_reset_tokens(token_hash)",
        "CREATE INDEX IF NOT EXISTS idx_prt_user_id ON password_reset_tokens(user_id)",
        # Tabela de tokens de verificação de e-mail
        "CREATE TABLE IF NOT EXISTS email_verification_tokens (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE, token_hash VARCHAR(64) UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS idx_evt_token_hash ON email_verification_tokens(token_hash)",
        # Tabela de uso de busca diária
        "CREATE TABLE IF NOT EXISTS search_usage (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, usage_date DATE NOT NULL, count INTEGER DEFAULT 0)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_search_usage_user_date ON search_usage(user_id, usage_date)",
        "CREATE INDEX IF NOT EXISTS idx_search_usage_date ON search_usage(usage_date)",
        # First-party aggregate analytics. The random browser token itself is
        # never stored; only its one-way hash is retained. IP and user-agent
        # are deliberately excluded from the schema.
        "CREATE TABLE IF NOT EXISTS site_visitors (id SERIAL PRIMARY KEY, visitor_hash VARCHAR(64) UNIQUE NOT NULL, first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(), last_seen_at TIMESTAMP NOT NULL DEFAULT NOW(), view_count INTEGER NOT NULL DEFAULT 0, last_path VARCHAR(255))",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_site_visitors_hash ON site_visitors(visitor_hash)",
        "CREATE INDEX IF NOT EXISTS idx_site_visitors_first_seen ON site_visitors(first_seen_at)",
        "CREATE INDEX IF NOT EXISTS idx_site_visitors_last_seen ON site_visitors(last_seen_at)",
        "CREATE TABLE IF NOT EXISTS site_page_views (id SERIAL PRIMARY KEY, visitor_id INTEGER NOT NULL REFERENCES site_visitors(id) ON DELETE CASCADE, path VARCHAR(255) NOT NULL, viewed_at TIMESTAMP NOT NULL DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS idx_site_page_views_visitor ON site_page_views(visitor_id)",
        "CREATE INDEX IF NOT EXISTS idx_site_page_views_path ON site_page_views(path)",
        "CREATE INDEX IF NOT EXISTS idx_site_page_views_viewed_at ON site_page_views(viewed_at)",
        # Literal page transcriptions are the only OCR-derived text allowed to
        # claim source fidelity in public citation paths.
        "CREATE TABLE IF NOT EXISTS verified_passages (id SERIAL PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE, book_file_id INTEGER REFERENCES book_files(id) ON DELETE CASCADE, pdf_page INTEGER NOT NULL, text TEXT NOT NULL, text_sha256 VARCHAR(64) NOT NULL, language VARCHAR(30), verification_method VARCHAR(50) DEFAULT 'visual_pdf', evidence_ref VARCHAR(500), created_at TIMESTAMP DEFAULT NOW())",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_verified_passage_source ON verified_passages(book_id, pdf_page, text_sha256)",
        "CREATE INDEX IF NOT EXISTS idx_verified_passage_lookup ON verified_passages(book_id, pdf_page)",
        # Full-page reviews retain enough evidence to prove exactly which PDF,
        # rendered pixels and transcription were approved. Independent OCR
        # consensus is intentionally not accepted as visual review.
        "CREATE TABLE IF NOT EXISTS verified_page_reviews (id SERIAL PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE, book_file_id INTEGER NOT NULL REFERENCES book_files(id) ON DELETE CASCADE, pdf_page INTEGER NOT NULL, text TEXT NOT NULL, text_sha256 VARCHAR(64) NOT NULL, pdf_sha256 VARCHAR(64) NOT NULL, render_pixel_sha256 VARCHAR(64) NOT NULL, render_dpi INTEGER NOT NULL, language VARCHAR(30) NOT NULL, reviewer VARCHAR(255) NOT NULL, reviewed_at TIMESTAMP NOT NULL, verification_method VARCHAR(50) DEFAULT 'visual_pdf', evidence_ref VARCHAR(500) NOT NULL, manifest_sha256 VARCHAR(64) NOT NULL, created_at TIMESTAMP DEFAULT NOW())",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_verified_page_review_evidence ON verified_page_reviews(book_id, pdf_page, text_sha256, pdf_sha256, render_pixel_sha256)",
        "CREATE INDEX IF NOT EXISTS idx_verified_page_review_lookup ON verified_page_reviews(book_id, pdf_page)",
    ]
    with engine.begin() as conn:
        for sql in migrations:
            conn.execute(__import__("sqlalchemy").text(sql))


def _backfill_legacy_billing_subscriptions() -> None:
    """Copy the legacy single-provider projection into the provider ledger once.

    This is intentionally additive: existing user access is never reduced by
    startup migration. Future provider reconciliation updates these rows.
    """

    paid_plans = {"catequista", "apologeta", "patristico", "magisterio"}
    now = datetime.datetime.utcnow()
    with SessionLocal() as db:
        changed = False
        for user in db.query(User).all():
            if user.billing_status == "owner":
                continue
            # A provider ledger is authoritative once it exists. In particular,
            # a paid Google Play projection must never be converted into a
            # permanent legacy entitlement merely because ``user.plan`` is paid.
            if (
                db.query(BillingSubscription.id)
                .filter(BillingSubscription.user_id == user.id)
                .first()
                is not None
            ):
                continue

            provider = (user.billing_provider or "").strip().lower()
            external_id = (user.billing_subscription_id or "").strip()
            if not provider and user.plan not in paid_plans:
                continue
            if not provider:
                provider = "legacy_manual"
            if not external_id:
                external_id = f"legacy-user-{user.id}"

            existing = (
                db.query(BillingSubscription)
                .filter(
                    BillingSubscription.provider == provider,
                    BillingSubscription.external_subscription_id == external_id,
                )
                .first()
            )
            if existing:
                continue

            status_value = (user.billing_status or "").strip().lower()
            if provider == "legacy_manual" and user.plan in paid_plans:
                entitlement_state = "legacy_active"
            elif status_value in {"active", "trialing"}:
                entitlement_state = "entitled"
            elif status_value == "past_due":
                entitlement_state = "grace"
            elif (
                status_value == "canceled"
                and user.billing_current_period_end is not None
                and user.billing_current_period_end > now
            ):
                entitlement_state = "canceled_valid"
            elif status_value in {"pending_payment", "incomplete"}:
                entitlement_state = "pending"
            else:
                entitlement_state = "inactive"

            subscription = BillingSubscription(
                user_id=user.id,
                provider=provider,
                package_name="",
                provider_customer_id=user.billing_customer_id,
                external_subscription_id=external_id,
                provider_status=status_value or "legacy",
                entitlement_state=entitlement_state,
                current_period_end=user.billing_current_period_end,
                cancel_at_period_end=bool(user.billing_cancel_at_period_end),
                last_verified_at=now,
            )
            if user.plan in paid_plans:
                subscription.items.append(
                    BillingSubscriptionItem(
                        item_key=f"legacy:{user.plan}",
                        product_id=f"legacy:{user.plan}",
                        plan=user.plan,
                        expiry_time=user.billing_current_period_end,
                        auto_renew_enabled=not bool(user.billing_cancel_at_period_end),
                        entitled=entitlement_state
                        in {"entitled", "grace", "canceled_valid", "legacy_active"},
                    )
                )
            db.add(subscription)
            changed = True
        if changed:
            db.commit()
