from __future__ import annotations

import datetime

from sqlalchemy import create_engine, String, Integer, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from core.config import settings


class Base(DeclarativeBase):
    pass


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
    ]
    with engine.begin() as conn:
        for sql in migrations:
            conn.execute(__import__("sqlalchemy").text(sql))
