"""
Direct ingest for all file_only books with 0 chunks.
Bypasses HTTP, calls IngestionService directly.
Skips files that take too long (per-file timeout via threading).
Run inside the backend container from /app:
  python -m scripts.direct_ingest_pending
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, "/app")

from sqlalchemy import text
from models.database import SessionLocal
from services.ingestion_service import IngestionService

PDF_ROOT = Path("/app/pdfs")
FILE_TIMEOUT = 300  # 5 minutes per file max

# Language suffixes to skip (Arabic, Vietnamese — tend to hang or have corrupt encoding)
SKIP_LANG_SUFFIXES = ("- AR.pdf", "- VI.pdf", "-AR.pdf", "-VI.pdf")


def find_pdf(original_filename: str) -> Path | None:
    for match in PDF_ROOT.rglob(original_filename):
        return match
    return None


def ingest_with_timeout(service, book_id, pdf_bytes, original_filename):
    result = {"chunks": 0, "error": None}

    def _run():
        try:
            _, chunks = service.ingest(
                book_id=book_id,
                pdf_bytes=pdf_bytes,
                original_filename=original_filename,
                volume_number=None,
            )
            result["chunks"] = chunks
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=FILE_TIMEOUT)
    if t.is_alive():
        return None, "TIMEOUT"
    if result["error"]:
        return None, result["error"]
    return result["chunks"], None


def main():
    with SessionLocal() as db:
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

    service = IngestionService()
    ok = 0
    err = 0

    for row in rows:
        book_id, title, author, lang, doc_type = row
        print(f"[{book_id}] {doc_type} | {author} — {title} [{lang}]", flush=True)

        with SessionLocal() as db:
            files = db.execute(text(
                "SELECT id, original_filename FROM book_files WHERE book_id = :bid ORDER BY id"
            ), {"bid": book_id}).fetchall()

        if not files:
            print("  SKIP: no book_files")
            continue

        total_chunks = 0
        for file_id, original_filename in files:
            # Skip known-problematic language PDFs
            if any(original_filename.endswith(s) for s in SKIP_LANG_SUFFIXES):
                print(f"  SKIP (lang): {original_filename}", flush=True)
                continue

            pdf_path = find_pdf(original_filename)
            if pdf_path is None:
                print(f"  NOT FOUND: {original_filename}", flush=True)
                continue

            print(f"  -> {original_filename}", end=" ... ", flush=True)
            try:
                pdf_bytes = pdf_path.read_bytes()
                chunks, error = ingest_with_timeout(service, book_id, pdf_bytes, original_filename)
                if error:
                    print(f"SKIP ({error})", flush=True)
                else:
                    print(f"OK ({chunks} chunks)", flush=True)
                    total_chunks += chunks
            except Exception as e:
                print(f"ERROR: {e}", flush=True)

        if total_chunks > 0:
            with SessionLocal() as db:
                db.execute(text(
                    "UPDATE books SET ingest_status='done' WHERE id=:bid"
                ), {"bid": book_id})
                db.commit()
            print(f"  STATUS -> done ({total_chunks} chunks)", flush=True)
            ok += 1
        else:
            print(f"  SKIP: no chunks indexed", flush=True)
            err += 1

        print(flush=True)

    print("=" * 50)
    print(f"Done   : {ok}")
    print(f"Errors : {err}")


if __name__ == "__main__":
    main()
