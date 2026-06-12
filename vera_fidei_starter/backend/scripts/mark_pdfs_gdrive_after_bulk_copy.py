from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.database import BookFile, SessionLocal
from storage.pdf_storage import PDF_DIR, get_pdf_storage


def _normalize_key(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def _is_remote(stored_path: str | None) -> bool:
    normalized = (stored_path or "").replace("\\", "/")
    return normalized.startswith(("s3://", "r2://", "gdrive://"))


def _remote_path_for(local_path: str) -> str:
    storage = get_pdf_storage()
    resolved = Path(local_path).resolve()
    pdf_root = PDF_DIR.resolve()
    try:
        rel = resolved.relative_to(pdf_root).as_posix()
    except ValueError as exc:
        raise RuntimeError(f"local PDF is outside PDF_DIR: {local_path}") from exc
    key = _normalize_key(f"{storage.gdrive_prefix}/{rel}")
    return f"gdrive://{key}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "After an rclone bulk copy of PDF_DIR to GDRIVE_PREFIX, update local "
            "BookFile stored_path values to gdrive:// paths."
        )
    )
    parser.add_argument("--apply", action="store_true", help="Update database rows.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum local rows to inspect.")
    parser.add_argument(
        "--start-after-file-id",
        type=int,
        default=0,
        help="Resume after this BookFile id.",
    )
    args = parser.parse_args()

    storage = get_pdf_storage()
    if storage.backend != "gdrive":
        print("ERROR: set PDF_STORAGE=gdrive before running this script.")
        return 2

    inspected = 0
    updated = 0
    skipped_remote = 0
    missing = 0

    with SessionLocal() as db:
        query = db.query(BookFile).order_by(BookFile.id.asc())
        if args.start_after_file_id:
            query = query.filter(BookFile.id > args.start_after_file_id)

        for book_file in query.all():
            if args.limit and inspected >= args.limit:
                break

            if _is_remote(book_file.stored_path):
                skipped_remote += 1
                continue

            inspected += 1
            local_path = storage.resolve_local_path(book_file.stored_path)
            if not local_path:
                missing += 1
                print(f"[MISSING] file_id={book_file.id} stored_path={book_file.stored_path!r}")
                continue

            remote_path = _remote_path_for(local_path)
            print(f"[READY] file_id={book_file.id} {book_file.stored_path!r} -> {remote_path!r}")
            if args.apply:
                book_file.stored_path = remote_path
                db.commit()
                updated += 1

    print(
        "Summary: "
        f"inspected_local={inspected} updated={updated} skipped_remote={skipped_remote} "
        f"missing={missing} mode={'apply' if args.apply else 'dry-run'}"
    )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
