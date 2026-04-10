from __future__ import annotations

from sqlalchemy import create_engine, String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from core.config import settings


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(50))
    edition_label: Mapped[str] = mapped_column(String(255), default="")
    source_label: Mapped[str] = mapped_column(String(255), default="")
    is_primary_source: Mapped[bool] = mapped_column(Boolean, default=True)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    chapter_or_section: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(Text)

    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_offset_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_offset_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_anchor: Mapped[str] = mapped_column(String(100), default="")

    book: Mapped["Book"] = relationship(back_populates="chunks")


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)