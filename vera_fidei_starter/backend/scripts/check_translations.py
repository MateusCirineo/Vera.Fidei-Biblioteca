"""
Verifica quantas traduções PT estão indexadas no ChromaDB por livro.
Útil para auditar cobertura multilíngue antes de ajustar busca.

Uso:
    cd vera_fidei_starter/backend
    python scripts/check_translations.py
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import SessionLocal, Book, Chunk, Translation
from search.semantic_search import SemanticSearchClient


def main() -> None:
    sc = SemanticSearchClient()
    chroma_collection = sc.collection

    with SessionLocal() as db:
        books = db.query(Book).order_by(Book.collection, Book.volume_number).all()

        print(f"{'ID':>4}  {'Coleção':>6}  {'Vol':>3}  {'Título':<45}  {'Chunks DB':>9}  {'Trad PT DB':>10}  {'Trad PT Chroma':>14}")
        print("-" * 110)

        for book in books:
            total_chunks = db.query(Chunk).filter(Chunk.book_id == book.id).count()
            total_translations = (
                db.query(Translation)
                .join(Chunk, Chunk.id == Translation.chunk_id)
                .filter(Chunk.book_id == book.id, Translation.language.in_(["pt", "por"]))
                .count()
            )

            # Count how many PT translations are in ChromaDB
            try:
                chroma_results = chroma_collection.get(
                    where={"$and": [{"book_id": book.id}, {"is_translation": True}]},
                    include=[],
                )
                chroma_pt_count = len(chroma_results.get("ids", []))
            except Exception:
                # Fallback: try without is_translation filter (older index schema)
                try:
                    chroma_results = chroma_collection.get(
                        where={"book_id": book.id},
                        include=["metadatas"],
                    )
                    chroma_pt_count = sum(
                        1 for m in (chroma_results.get("metadatas") or [])
                        if m and m.get("is_translation")
                    )
                except Exception:
                    chroma_pt_count = -1

            title = (book.canonical_title or book.title or "")[:44]
            vol = book.volume_number or "-"
            coll = book.collection or "-"

            chroma_str = str(chroma_pt_count) if chroma_pt_count >= 0 else "erro"
            print(f"{book.id:>4}  {coll:>6}  {vol!s:>3}  {title:<45}  {total_chunks:>9}  {total_translations:>10}  {chroma_str:>14}")

    print()
    print("Legenda:")
    print("  Trad PT DB     — traduções PT na tabela translations do PostgreSQL")
    print("  Trad PT Chroma — entradas marcadas como is_translation=True no ChromaDB")
    print()
    print("Se 'Trad PT Chroma' for 0 mas 'Trad PT DB' > 0, rode index_translation() para reindexar.")


if __name__ == "__main__":
    main()
