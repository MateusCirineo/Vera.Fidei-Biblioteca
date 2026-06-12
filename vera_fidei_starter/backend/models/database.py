from __future__ import annotations

import datetime

from sqlalchemy import create_engine, String, Integer, Boolean, ForeignKey, Text, DateTime
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
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    verifications: Mapped[list["VerificationHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


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

    book: Mapped["Book"] = relationship(back_populates="chunks")
    source_file: Mapped["BookFile | None"] = relationship(back_populates="chunks")
    translations: Mapped[list["Translation"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )


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


def init_db(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _migrate_add_library_columns()


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
        "CREATE INDEX IF NOT EXISTS idx_books_canonical_author ON books(canonical_author)",
        "CREATE INDEX IF NOT EXISTS idx_books_library_section ON books(library_section)",
        # Tabela de usuários
        "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, name VARCHAR(255) NOT NULL, password_hash VARCHAR(255) NOT NULL, plan VARCHAR(30) DEFAULT 'fiel', is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        # Tabela de histórico de verificações
        "CREATE TABLE IF NOT EXISTS verification_history (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, citation_text TEXT NOT NULL, attributed_to VARCHAR(255), status_code VARCHAR(50), label VARCHAR(100), confidence VARCHAR(20), author VARCHAR(255), work VARCHAR(255), reference_json TEXT, matched_excerpt TEXT, explanation TEXT, response_json TEXT, created_at TIMESTAMP DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS idx_vhist_user_id ON verification_history(user_id)",
        # Para ambientes onde a tabela já existe sem response_json
        "ALTER TABLE verification_history ADD COLUMN IF NOT EXISTS response_json TEXT",
        # Fase 4 — Gestão Institucional
        "CREATE TABLE IF NOT EXISTS institutions (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, admin_user_id INTEGER REFERENCES users(id), created_at TIMESTAMP DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS institution_members (id SERIAL PRIMARY KEY, institution_id INTEGER REFERENCES institutions(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, role VARCHAR(20) DEFAULT 'membro', joined_at TIMESTAMP DEFAULT NOW())",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_inst_members_unique ON institution_members(institution_id, user_id)",
        "CREATE TABLE IF NOT EXISTS api_keys (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, key_hash VARCHAR(64) NOT NULL, label VARCHAR(100), is_active BOOLEAN DEFAULT TRUE, usage_count INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT NOW(), last_used_at TIMESTAMP)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)",
    ]
    with engine.begin() as conn:
        for sql in migrations:
            conn.execute(__import__("sqlalchemy").text(sql))
