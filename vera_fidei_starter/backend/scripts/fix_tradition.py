"""
Corrige metadados dos livros 7-10 (Patrística Paulus em PT):
- patristic_tradition: "grega" → "portuguesa"
- collection: "PG" → "PT"
- author e canonical_author alinhados (especialmente para coletâneas)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.database import SessionLocal, Book

corrections = {
    7: {
        "patristic_tradition": "portuguesa",
        "collection": "PT",
        "author": "Padres Apologistas",
        "canonical_author": "Padres Apologistas",
    },
    8: {
        "patristic_tradition": "portuguesa",
        "collection": "PT",
        "author": "Santo Irineu de Lião",
        "canonical_author": "Santo Irineu de Lião",
        "canonical_title": "Contra as Heresias",
    },
    9: {
        "patristic_tradition": "portuguesa",
        "collection": "PT",
        "author": "Padres Apostólicos",
        "canonical_author": "Padres Apostólicos",
    },
    10: {
        "patristic_tradition": "portuguesa",
        "collection": "PT",
        "author": "São Justino Mártir",
        "canonical_author": "São Justino Mártir",
        "canonical_title": "I e II Apologias; Diálogo com Trifão",
    },
}

with SessionLocal() as db:
    for book_id, fields in corrections.items():
        book = db.get(Book, book_id)
        if book is None:
            print(f"AVISO: book_id={book_id} não encontrado, pulando.")
            continue
        before = {k: getattr(book, k) for k in fields}
        for k, v in fields.items():
            setattr(book, k, v)
        print(f"id={book_id}: {before} -> {fields}")
    db.commit()
    print("\nMetadados corrigidos com sucesso.")
