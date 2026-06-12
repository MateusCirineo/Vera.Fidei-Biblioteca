from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.database import BookFile, SessionLocal
from storage.pdf_storage import get_pdf_storage


def is_remote(stored_path: str) -> bool:
    normalized = (stored_path or "").replace("\\", "/")
    return normalized.startswith(("s3://", "r2://", "gdrive://"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate Vera.Fidei BookFile PDFs from local disk to remote storage."
    )
    parser.add_argument("--apply", action="store_true", help="Actually upload and update the database.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of files to process.")
    parser.add_argument("--book-id", type=int, default=0, help="Only migrate files from one book.")
    parser.add_argument("--start-after-file-id", type=int, default=0, help="Resume after this BookFile id.")
    parser.add_argument("--preflight", action="store_true", help="Check remote write permissions and exit.")
    parser.add_argument("--no-verify", action="store_true", help="Skip remote head_object size verification.")
    parser.add_argument(
        "--delete-local",
        action="store_true",
        help="Delete local PDF after successful DB update. Use only after testing.",
    )
    args = parser.parse_args()

    storage = get_pdf_storage()
    if not storage.is_remote:
        print("ERROR: set PDF_STORAGE=s3/r2/gdrive and matching env vars before running this script.")
        return 2
    print(
        "Storage: "
        f"backend={storage.backend!r} bucket={storage.bucket!r} s3_prefix={storage.prefix!r} "
        f"gdrive_remote={storage.gdrive_remote!r} gdrive_prefix={storage.gdrive_prefix!r} "
        f"endpoint={storage.endpoint_url!r} region={storage.region!r}"
    )

    if args.preflight:
        storage.check_remote_write()
        print("Preflight OK: remote storage accepted put/head/delete.")
        return 0

    processed = 0
    uploaded = 0
    skipped = 0
    missing = 0
    failed = 0
    started_at = monotonic()

    with SessionLocal() as db:
        query = db.query(BookFile).order_by(BookFile.id.asc())
        if args.book_id:
            query = query.filter(BookFile.book_id == args.book_id)
        if args.start_after_file_id:
            query = query.filter(BookFile.id > args.start_after_file_id)
        rows = query.all()

        for book_file in rows:
            if args.limit and processed >= args.limit:
                break
            processed += 1

            if is_remote(book_file.stored_path):
                skipped += 1
                print(f"[SKIP remote] file_id={book_file.id} {book_file.original_filename}")
                continue

            local_path = storage.resolve_local_path(book_file.stored_path)
            if not local_path:
                missing += 1
                print(f"[MISSING] file_id={book_file.id} stored_path={book_file.stored_path!r}")
                continue

            print(f"[READY] file_id={book_file.id} book_id={book_file.book_id} -> {local_path}")
            if not args.apply:
                continue

            stored = storage.upload_existing_pdf(
                book_id=book_file.book_id,
                file_id=book_file.id,
                original_filename=book_file.original_filename,
                local_path=local_path,
            )
            if not args.no_verify:
                local_size = os.path.getsize(local_path)
                uploaded_size = storage.remote_size(stored.stored_path)
                if uploaded_size != local_size:
                    failed += 1
                    print(
                        "[VERIFY FAILED] "
                        f"file_id={book_file.id} local_size={local_size} remote_size={uploaded_size}"
                    )
                    continue

            old_path = book_file.stored_path
            book_file.stored_path = stored.stored_path
            db.commit()
            uploaded += 1
            print(f"[OK] file_id={book_file.id} {old_path!r} -> {stored.stored_path!r}")

            if args.delete_local:
                try:
                    os.remove(local_path)
                    print(f"[DELETE local] {local_path}")
                except OSError as exc:
                    print(f"[WARN delete] {local_path}: {exc}")

    print(
        "Summary: "
        f"processed={processed} uploaded={uploaded} skipped={skipped} missing={missing} failed={failed} "
        f"elapsed_s={monotonic() - started_at:.1f} mode={'apply' if args.apply else 'dry-run'}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
