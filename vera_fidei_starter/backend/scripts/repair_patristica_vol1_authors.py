from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.database import Book, Chunk, SessionLocal


AUTHOR_RANGES = (
    (41, 76, "Santo Inácio de Antioquia"),
    (77, 91, "São Policarpo de Esmirna"),
    (92, 176, "Hermas"),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Corrige chunk_author da coletânea Patrística Vol. 1 — Padres Apostólicos."
    )
    parser.add_argument("--apply", action="store_true", help="Grava as correções no banco.")
    args = parser.parse_args()

    with SessionLocal() as db:
        book = (
            db.query(Book)
            .filter(Book.title == "Patrística Vol. 1 — Padres Apostólicos")
            .first()
        )
        if not book:
            raise SystemExit("Livro não encontrado: Patrística Vol. 1 — Padres Apostólicos")

        total = 0
        for start, end, author in AUTHOR_RANGES:
            chunks = (
                db.query(Chunk)
                .filter(
                    Chunk.book_id == book.id,
                    Chunk.sequence_index >= start,
                    Chunk.sequence_index <= end,
                    Chunk.chunk_author != author,
                )
                .order_by(Chunk.sequence_index, Chunk.id)
                .all()
            )
            total += len(chunks)
            print(f"{author}: {len(chunks)} trecho(s) para corrigir")
            for chunk in chunks[:12]:
                print(
                    f"  id={chunk.id} seq={chunk.sequence_index} "
                    f"page={chunk.pdf_page} from={chunk.chunk_author!r}"
                )
            if len(chunks) > 12:
                print(f"  ... +{len(chunks) - 12}")
            if args.apply:
                for chunk in chunks:
                    chunk.chunk_author = author

        if args.apply:
            db.commit()
            print(f"Correções aplicadas: {total}")
        else:
            print(f"Prévia concluída: {total} trecho(s). Use --apply para gravar.")


if __name__ == "__main__":
    main()
