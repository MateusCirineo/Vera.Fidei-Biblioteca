#!/usr/bin/env python3
"""
Corrige os metadados do Código de Direito Canônico (book_id=1827)
que foi ingerido com author='Desconhecido' e library_section='patristica'.
"""
import sys
sys.path.insert(0, '/app')

from models.database import SessionLocal, Book

FIXES = {
    1827: {
        "author":             "Santa Sé",
        "canonical_author":   "Santa Sé",
        "collection":         "CDC",
        "document_type":      "direito_canonico",
        "library_section":    "documentos",
        "patristic_tradition": None,
        "canonical_title":    "Código de Direito Canônico",
        "edition_label":      "Código de Direito Canônico — 1983",
    },
}

with SessionLocal() as db:
    for book_id, fields in FIXES.items():
        book = db.get(Book, book_id)
        if book is None:
            print(f"Book {book_id} não encontrado — pulando.")
            continue
        for k, v in fields.items():
            setattr(book, k, v)
        db.commit()
        print(f"Book {book_id} atualizado: '{book.title}'")
        for k, v in fields.items():
            print(f"  {k}: {v!r}")
