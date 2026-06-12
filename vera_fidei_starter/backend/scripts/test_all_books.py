#!/usr/bin/env python3
"""
Testa TODOS os livros do Vera.Fidei:
- Para cada livro com ingest_status='done' E pelo menos 1 BookFile
- Pega 3 chunks representativos (início, meio, fim por sequence_index)
- Chama VerificationService.verify() diretamente (sem HTTP)
- Verifica: status_code, author, pdf_page
- Imprime relatório com PASS / WARN / FAIL por livro
"""
import sys
import os
import multiprocessing

sys.path.insert(0, '/app')

FAIL_STATUSES = {"NAO_ENCONTRADA"}
MULTI_AUTHOR_BOOKS = {7, 9}   # Book 7 Apologistas, Book 9 Apostólicos
GENERIC_AUTHOR_NAMES = {
    "padres apostólicos", "padres apologistas", "patres apostolici",
    "escritores eclesiásticos", "diversos autores",
}


def normalize(s):
    return (s or "").lower().strip()


def get_testable_books():
    from sqlalchemy import text
    from models.database import SessionLocal
    with SessionLocal() as db:
        rows = db.execute(text("""
            SELECT DISTINCT b.id, b.author, b.title, b.collection, b.ingest_status
            FROM books b
            INNER JOIN chunks c ON c.book_id = b.id
            INNER JOIN book_files bf ON bf.book_id = b.id
            WHERE b.ingest_status IN ('done', 'file_only') OR
                  (b.ingest_status IS NULL AND EXISTS (
                      SELECT 1 FROM chunks WHERE book_id = b.id
                  ))
            ORDER BY b.id
        """)).fetchall()
    return rows


def get_sample_chunks(book_id):
    from sqlalchemy import text
    from models.database import SessionLocal
    with SessionLocal() as db:
        rows = db.execute(text("""
            SELECT id, text, chunk_author, pdf_page, sequence_index
            FROM chunks
            WHERE book_id = :bid
            ORDER BY COALESCE(sequence_index, id) ASC
        """), {"bid": book_id}).fetchall()
    if not rows:
        return []
    n = len(rows)
    indices = sorted({0, n // 2, n - 1})
    return [rows[i] for i in indices]


def check_author(book_id, book_author, got_author):
    if got_author is None:
        return "FAIL_NULL_AUTHOR"
    got = normalize(got_author)
    if got in GENERIC_AUTHOR_NAMES:
        return "FAIL_GENERIC_AUTHOR"
    if book_id in MULTI_AUTHOR_BOOKS:
        if normalize(book_author) == got:
            return "WARN_BOOK_LEVEL_AUTHOR"
    return ""


def main():
    from services.verification_service import VerificationService
    from schemas.citation import VerifyCitationRequest

    verifier = VerificationService()
    fails = []
    warns = []
    total_books = 0
    total_chunks = 0

    print("=" * 70)
    print("VERA.FIDEI — Teste de Todos os Livros")
    print("=" * 70)

    for book_id, book_author, book_title, collection, status in get_testable_books():
        total_books += 1
        chunks = get_sample_chunks(book_id)

        print(f"\n[{total_books}] Book {book_id}: {book_author} / {book_title[:60]}")

        if not chunks:
            print("  SKIP — sem chunks")
            continue

        for chunk_row in chunks:
            chunk_id, chunk_text, chunk_author, chunk_pdf_page, seq_idx = chunk_row
            if not chunk_text or len(chunk_text.strip()) < 30:
                print(f"  chunk {chunk_id}: SKIP (texto muito curto)")
                continue

            attributed_to = chunk_author or book_author
            quote = chunk_text[:300].strip()

            try:
                req = VerifyCitationRequest(quote=quote, attributed_to=attributed_to)
                resp = verifier.verify(req)
            except Exception as e:
                msg = str(e)[:120]
                print(f"  chunk {chunk_id}: ERROR — {msg}")
                fails.append((book_id, chunk_id, f"EXCEPTION: {msg}"))
                continue

            total_chunks += 1
            flag = ""
            notes = []

            # Check 1: status não deve ser NAO_ENCONTRADA para texto real do DB
            if resp.status_code in FAIL_STATUSES:
                flag = "FAIL"
                notes.append(f"status={resp.status_code}")
                fails.append((book_id, chunk_id, f"NAO_ENCONTRADA (attributed_to={attributed_to!r})"))

            # Check 2: autor retornado não pode ser genérico ou nulo
            author_flag = check_author(book_id, book_author, resp.author)
            if author_flag.startswith("FAIL"):
                flag = "FAIL"
                notes.append(author_flag)
                fails.append((book_id, chunk_id, f"{author_flag} got={resp.author!r}"))
            elif author_flag.startswith("WARN"):
                if not flag:
                    flag = "WARN"
                notes.append(author_flag)
                warns.append((book_id, chunk_id, author_flag))

            # Check 3: pdf_page deve existir se chunk tem pdf_page
            ref = resp.reference
            got_page = ref.pdf_page if ref else None
            if chunk_pdf_page is not None and got_page is None:
                if not flag:
                    flag = "WARN"
                notes.append("WARN_NO_PAGE")
                warns.append((book_id, chunk_id, f"WARN_NO_PAGE chunk_pdf_page={chunk_pdf_page}"))

            icon = "OK" if not flag else ("WARN" if flag == "WARN" else "FAIL")
            note_str = " | ".join(notes) if notes else "OK"
            print(
                f"  [{icon}] chunk {chunk_id} (seq={seq_idx}): "
                f"{resp.status_code} | author={resp.author!r} | "
                f"page={got_page} — {note_str}"
            )

        sys.stdout.flush()

    print("\n" + "=" * 70)
    print(f"RESUMO: {total_books} livros testados | {total_chunks} chunks verificados")
    print(f"\n  FALHAS ({len(fails)}):")
    for book_id, chunk_id, reason in fails:
        print(f"    [FAIL] Book {book_id}, Chunk {chunk_id}: {reason}")
    print(f"\n  ALERTAS ({len(warns)}):")
    for book_id, chunk_id, reason in warns[:30]:
        print(f"    [WARN] Book {book_id}, Chunk {chunk_id}: {reason}")
    if len(warns) > 30:
        print(f"    ... e mais {len(warns) - 30} alertas")
    print("=" * 70)
    if not fails:
        print("\n[PASS] TODOS OS TESTES PASSARAM - zero falhas criticas.")
    else:
        print(f"\n[FAIL] {len(fails)} FALHA(S) ENCONTRADA(S) - regressoes detectadas.")


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
