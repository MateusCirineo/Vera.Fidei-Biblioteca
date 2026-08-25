"""Finalize one review pack page after direct inspection of rendered pixels.

This command never performs the import. It only creates the reviewed manifest
that ``import_verified_pages`` can validate independently.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

sys.path.insert(0, "/app")

from scripts.import_verified_pages import rendered_page_fingerprint, transcription_sha256
from services.source_fidelity_service import normalize_literal


CONFIRMATION_TOKEN = "INSPECTED_VISIBLE_PDF_PIXELS"


def _inside(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError("review evidence path must be relative")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved_root not in resolved.parents:
        raise ValueError("review evidence path escapes the review pack")
    return resolved


def finalize_page(
    draft_path: Path,
    *,
    page: int,
    reviewer: str,
    confirmation_token: str,
    review_note: str,
    blank_page: bool,
) -> Path:
    if confirmation_token != CONFIRMATION_TOKEN:
        raise ValueError("explicit visible-pixel inspection confirmation is required")
    if not reviewer.strip() or reviewer.strip().casefold() in {"pending", "automatic", "ocr"}:
        raise ValueError("reviewer must identify the visual reviewer")

    payload = json.loads(draft_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    selected = [entry for entry in entries or [] if int(entry.get("pdf_page") or 0) == page]
    if len(selected) != 1:
        raise ValueError(f"draft must contain exactly one entry for page {page}")
    entry = dict(selected[0])
    root = draft_path.parent
    image_path = _inside(root, str(entry.get("review_image") or ""))
    transcription_path = _inside(root, str(entry.get("transcription_file") or ""))
    if not image_path.is_file() or not transcription_path.is_file():
        raise ValueError("review image and transcription file must exist")

    with Image.open(image_path) as image:
        actual_render = rendered_page_fingerprint(image)
    if actual_render != entry.get("render_pixel_sha256"):
        raise ValueError("review image pixels no longer match the prepared PDF render")

    text = transcription_path.read_text(encoding="utf-8")
    is_empty = not bool(normalize_literal(text))
    if blank_page != is_empty:
        raise ValueError("blank-page declaration does not match the transcription")

    entry.update({
        "reviewer": reviewer.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "transcription_sha256": transcription_sha256(text),
        "verification_method": "visual_pdf",
        "visual_confirmation": True,
        "blank_page": blank_page,
        "review_note": review_note.strip() or None,
    })
    reviewed = {
        "schema_version": 1,
        "status": "visually_reviewed",
        "source_draft": draft_path.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "public_promotion": False,
        "entries": [entry],
    }
    output = root / f"manifest.page_{page:04d}.reviewed.json"
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(reviewed, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--confirmation-token", required=True)
    parser.add_argument("--review-note", default="")
    parser.add_argument("--blank-page", action="store_true")
    args = parser.parse_args()
    try:
        output = finalize_page(
            args.draft,
            page=args.page,
            reviewer=args.reviewer,
            confirmation_token=args.confirmation_token,
            review_note=args.review_note,
            blank_page=args.blank_page,
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), flush=True)
        return 1
    print(json.dumps({"status": "visually_reviewed", "manifest": str(output)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
