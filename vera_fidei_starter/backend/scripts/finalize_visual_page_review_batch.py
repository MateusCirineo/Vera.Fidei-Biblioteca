"""Finalize several visually inspected pages as one batch import manifest.

The existing single-page finalizer remains the source of all hash and visible-
pixel checks. This wrapper combines its reviewed entries so
``import_verified_pages`` resolves and hashes a large PDF only once per batch.

Run inside the backend container from ``/app``::

    python -m scripts.finalize_visual_page_review_batch \
      /app/pdfs/.visual_page_reviews/pending/book_1742/pack/manifest.draft.json \
      --page 16 --page 17 --reviewer visual-reviewer \
      --confirmation-token INSPECTED_VISIBLE_PDF_PIXELS
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.finalize_visual_page_review import finalize_page


def finalize_batch(
    draft_path: Path,
    *,
    pages: list[int],
    reviewer: str,
    confirmation_token: str,
    review_note: str,
    blank_pages: set[int],
) -> Path:
    unique_pages = sorted(set(pages))
    if not unique_pages or min(unique_pages) < 1:
        raise ValueError("at least one positive page is required")
    unexpected_blank_pages = blank_pages.difference(unique_pages)
    if unexpected_blank_pages:
        raise ValueError(
            "blank pages must also be listed with --page: "
            + ", ".join(str(page) for page in sorted(unexpected_blank_pages))
        )

    entries = []
    for page in unique_pages:
        reviewed_path = finalize_page(
            draft_path,
            page=page,
            reviewer=reviewer,
            confirmation_token=confirmation_token,
            review_note=review_note,
            blank_page=page in blank_pages,
        )
        reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))
        page_entries = reviewed.get("entries") if isinstance(reviewed, dict) else None
        if not isinstance(page_entries, list) or len(page_entries) != 1:
            raise ValueError(f"single-page finalizer returned invalid page {page} manifest")
        entries.append(page_entries[0])

    stamp = datetime.now(timezone.utc).isoformat()
    page_label = "_".join(f"{page:04d}" for page in unique_pages)
    output = draft_path.parent / f"manifest.pages_{page_label}.reviewed.json"
    temporary = output.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "visually_reviewed",
                "source_draft": draft_path.name,
                "created_at": stamp,
                "public_promotion": False,
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("--page", action="append", type=int, required=True)
    parser.add_argument("--blank-page", action="append", type=int, default=[])
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--confirmation-token", required=True)
    parser.add_argument("--review-note", default="")
    args = parser.parse_args()
    try:
        output = finalize_batch(
            args.draft,
            pages=args.page,
            reviewer=args.reviewer,
            confirmation_token=args.confirmation_token,
            review_note=args.review_note,
            blank_pages=set(args.blank_page),
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), flush=True)
        return 1
    print(
        json.dumps(
            {
                "status": "visually_reviewed",
                "pages": len(set(args.page)),
                "manifest": str(output),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
