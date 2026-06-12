"""
Trigger ingestion for all books with file_only status and 0 chunks.
Finds PDFs by searching /app/pdfs/ recursively for each book_file's original_filename.
Runs inside the backend container: python -m scripts.trigger_ingest_all_pending
"""

import os
import sys
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from models.database import SessionLocal

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "")
PDF_ROOT = Path(os.environ.get("PDF_ROOT", "/app/pdfs"))

headers = {"X-API-Key": API_KEY} if API_KEY else {}


def find_pdf(original_filename: str) -> Path | None:
    for match in PDF_ROOT.rglob(original_filename):
        return match
    return None


def ingest_file(book_id: int, file_path: Path, original_filename: str) -> bool:
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/books/{book_id}/ingest-pdf",
            headers=headers,
            files={"file": (original_filename, f, "application/pdf")},
            timeout=600,
        )
    if resp.status_code in (200, 201):
        return True
    print(f"    ERROR {resp.status_code}: {resp.text[:200]}")
    return False


def main():
    with SessionLocal() as db:
        # Get all books with file_only status and 0 chunks
        rows = db.execute(text("""
            SELECT DISTINCT b.id, b.title, b.author, b.language, b.document_type
            FROM books b
            LEFT JOIN chunks c ON c.book_id = b.id
            WHERE b.ingest_status = 'file_only'
            GROUP BY b.id, b.title, b.author, b.language, b.document_type
            HAVING COUNT(c.id) = 0
            ORDER BY b.id
        """)).fetchall()

    print(f"Books to index: {len(rows)}")
    print()

    ok_books = 0
    err_books = 0
    skip_books = 0

    for row in rows:
        book_id, title, author, lang, doc_type = row
        print(f"[{book_id}] {doc_type} | {author} — {title} [{lang}]")

        with SessionLocal() as db:
            files = db.execute(text(
                "SELECT id, original_filename FROM book_files WHERE book_id = :bid ORDER BY id"
            ), {"bid": book_id}).fetchall()

        if not files:
            print(f"  SKIP: no book_files registered")
            skip_books += 1
            continue

        book_ok = True
        indexed_count = 0
        for file_id, original_filename in files:
            pdf_path = find_pdf(original_filename)
            if pdf_path is None:
                print(f"  NOT FOUND: {original_filename}")
                book_ok = False
                continue

            print(f"  -> {original_filename}", end=" ... ", flush=True)
            success = ingest_file(book_id, pdf_path, original_filename)
            if success:
                print("OK")
                indexed_count += 1
            else:
                book_ok = False

            time.sleep(0.5)

        if book_ok and indexed_count > 0:
            ok_books += 1
        elif indexed_count > 0:
            ok_books += 1
            print(f"  PARTIAL: {indexed_count}/{len(files)} files indexed")
        else:
            err_books += 1

        print()

    print("=" * 50)
    print(f"Done   : {ok_books}")
    print(f"Errors : {err_books}")
    print(f"Skipped: {skip_books}")


if __name__ == "__main__":
    main()
