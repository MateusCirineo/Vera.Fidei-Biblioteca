#!/usr/bin/env python3
"""
Normaliza o campo `pope` (e `author`/`canonical_author`) dos livros
de documentos papais para usar formato canônico: "Papa [Nome Acentuado]".

Problema: ingestões diferentes geraram variantes como:
  - "Francisco" em vez de "Papa Francisco"
  - "Papa Joao Paulo II" em vez de "Papa João Paulo II"  (sem acento)
  - "João Paulo II" em vez de "Papa João Paulo II"       (sem prefixo)
"""
import sys
sys.path.insert(0, '/app')

from models.database import SessionLocal, Book
from sqlalchemy import text

# Mapeamento canônico: valor_atual → valor_correto
POPE_CANONICAL: dict[str, str] = {
    # Francisco
    "Francisco":               "Papa Francisco",
    "Papa Francisco":          "Papa Francisco",
    # Bento XVI
    "Bento XVI":               "Papa Bento XVI",
    "Papa Bento XVI":          "Papa Bento XVI",
    # João Paulo II — 3 variantes
    "João Paulo II":           "Papa João Paulo II",
    "Papa Joao Paulo II":      "Papa João Paulo II",
    "Papa João Paulo II":      "Papa João Paulo II",
    # Paulo VI
    "Paulo VI":                "Papa Paulo VI",
    "Papa Paulo VI":           "Papa Paulo VI",
    # João XXIII — 2 variantes
    "João XXIII":              "Papa João XXIII",
    "Papa Joao XXIII":         "Papa João XXIII",
    "Papa João XXIII":         "Papa João XXIII",
    # Pio XII
    "Pio XII":                 "Papa Pio XII",
    "Papa Pio XII":            "Papa Pio XII",
    # Pio XI
    "Pio XI":                  "Papa Pio XI",
    "Papa Pio XI":             "Papa Pio XI",
    # Pio X
    "Pio X":                   "Papa Pio X",
    "Papa Pio X":              "Papa Pio X",
    # Bento XV
    "Bento XV":                "Papa Bento XV",
    "Papa Bento XV":           "Papa Bento XV",
    # Leão XIII — 3 variantes
    "Leão XIII":               "Papa Leão XIII",
    "Papa Leao XIII":          "Papa Leão XIII",
    "Papa Leão XIII":          "Papa Leão XIII",
}

# author também precisa ser normalizado (mesmas variantes aparecem em author/canonical_author)
AUTHOR_CANONICAL = POPE_CANONICAL.copy()

updated = 0
with SessionLocal() as db:
    books = db.query(Book).filter(Book.library_section == 'documentos').all()
    for book in books:
        changed = False

        # Normaliza pope
        if book.pope and book.pope in POPE_CANONICAL:
            new_pope = POPE_CANONICAL[book.pope]
            if new_pope != book.pope:
                print(f"  Book {book.id}: pope {book.pope!r} → {new_pope!r}")
                book.pope = new_pope
                changed = True

        # Normaliza author
        if book.author and book.author in AUTHOR_CANONICAL:
            new_author = AUTHOR_CANONICAL[book.author]
            if new_author != book.author:
                print(f"  Book {book.id}: author {book.author!r} → {new_author!r}")
                book.author = new_author
                changed = True

        # Normaliza canonical_author
        if book.canonical_author and book.canonical_author in AUTHOR_CANONICAL:
            new_ca = AUTHOR_CANONICAL[book.canonical_author]
            if new_ca != book.canonical_author:
                print(f"  Book {book.id}: canonical_author {book.canonical_author!r} → {new_ca!r}")
                book.canonical_author = new_ca
                changed = True

        if changed:
            updated += 1

    db.commit()

print(f"\nTotal livros atualizados: {updated}")

# Verificar resultado
print("\n--- Estado final ---")
with SessionLocal() as db:
    rows = db.execute(text(
        "SELECT pope, COUNT(*) as n FROM books WHERE library_section='documentos' "
        "AND pope IS NOT NULL GROUP BY pope ORDER BY pope"
    )).fetchall()
    for r in rows:
        print(f"  {r.pope!r}: {r.n}")
