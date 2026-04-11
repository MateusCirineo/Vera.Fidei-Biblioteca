"""
Backfill de campos canonical_author e canonical_title para livros existentes.

Uso (a partir do diretório backend/):
    python -m scripts.backfill_canonical

Roda fora do ciclo de request — seguro para acervos grandes.
Livros sem chunks ainda usam só o título para detecção.
"""

from __future__ import annotations

import sys
import os

# Garantir que o diretório backend está no path quando rodado diretamente
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import SessionLocal, Book, Chunk, init_db
from utils.author_detection import detect_author, detect_canonical_title


def _get_content_sample(db, book_id: int) -> str:
    """Reutiliza chunks já indexados para enriquecer a detecção."""
    chunks = (
        db.query(Chunk.text)
        .filter(Chunk.book_id == book_id)
        .order_by(Chunk.sequence_index)
        .limit(5)
        .all()
    )
    return " ".join(c.text for c in chunks)[:1000]


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        books = db.query(Book).filter(Book.canonical_author.is_(None)).all()
        if not books:
            print("Nenhum livro sem canonical_author. Backfill desnecessário.")
            return

        updated = 0
        skipped = 0
        for b in books:
            content_sample = _get_content_sample(db, b.id)
            detected_author, score = detect_author(b.title, content_sample)

            if detected_author:
                b.canonical_author = detected_author
                b.canonical_title = detect_canonical_title(b.title, content_sample)
                updated += 1
            else:
                # Fallback: mantém dados brutos até mapa multilíngue ou embeddings
                b.canonical_author = b.author
                b.canonical_title = b.title
                skipped += 1

        db.commit()
        print(
            f"Backfill concluído: {updated} detectados automaticamente, "
            f"{skipped} usaram fallback (author/title original)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    run()
