"""Build a resumable page-by-page visual verification queue.

The first OCR pass remains a candidate, never an authority. This command
renders the PDF again and reads the visible pixels with a separately selected
OCR model/configuration. Exact agreement is recorded as machine consensus;
every difference is kept in a review manifest. Neither outcome is inserted in
``verified_passages``: only a transcription actually checked against the
rendered page may become public source text.

Run inside the backend image from /app, preferably in an isolated container::

    python -m scripts.build_page_verification_queue \
      --book-id 1743 --layout columns --candidate-lang lat+grc+eng \
      --verifier-lang Latin+lat+grc+eng --workers 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from ingestion.pdf_extractor import PDFExtractor, TESSDATA_DIR
from scripts.ocr_reindex_books import (
    DEFAULT_CACHE_ROOT,
    BookTarget,
    _cache_dir,
    _cleanup_image,
    _convert_page,
    _ocr_image,
    _page_count,
    _targets,
)
from services.page_verification_service import compare_page_transcriptions
from storage.pdf_storage import get_pdf_storage


DEFAULT_OUTPUT_ROOT = Path("/app/pdfs/.page_verification")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(payload: dict[str, object]) -> None:
    print(json.dumps({"at": _now(), **payload}, ensure_ascii=False), flush=True)


def _resolve_pdf(target: BookTarget) -> str | None:
    local_path = get_pdf_storage().resolve_for_processing(target.stored_path)
    if local_path:
        return local_path
    for candidate in (
        Path("/app/pdfs") / target.filename,
        Path("/app/pdfs") / Path(target.stored_path).name,
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def _model_fingerprint(language: str) -> str:
    digest = hashlib.sha256(language.encode("utf-8"))
    tessdata = Path(TESSDATA_DIR)
    for name in sorted(part.strip() for part in language.split("+") if part.strip()):
        path = tessdata / f"{name}.traineddata"
        digest.update(name.encode("utf-8"))
        if not path.is_file():
            digest.update(b"missing")
            continue
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()[:16]


def _verification_dir(
    output_root: Path,
    target: BookTarget,
    pdf_path: str,
    dpi: int,
    language: str,
    layout: str,
) -> Path:
    stat = Path(pdf_path).stat()
    signature = hashlib.sha256(
        (
            f"v1|{target.stored_path}|{stat.st_size}|{dpi}|{language}|{layout}|"
            f"{_model_fingerprint(language)}"
        ).encode("utf-8")
    ).hexdigest()[:16]
    path = output_root / f"book_{target.book_id}" / signature
    (path / "verifier_text").mkdir(parents=True, exist_ok=True)
    (path / "pages").mkdir(parents=True, exist_ok=True)
    return path


def _read_candidate_pages(
    target: BookTarget,
    pdf_path: str,
    page_total: int,
    cache_root: Path,
    dpi: int,
    language: str,
    layout: str,
    source: str,
) -> tuple[str, dict[int, str]]:
    candidate_dir = _cache_dir(cache_root, target, pdf_path, dpi, language, layout)
    pages: dict[int, str] = {}
    if source in {"auto", "ocr_cache"}:
        for page in range(1, page_total + 1):
            path = candidate_dir / f"page_{page:04d}.txt"
            if path.is_file():
                pages[page] = path.read_text(encoding="utf-8")
        if source == "ocr_cache" or len(pages) == page_total:
            return f"ocr_cache:{candidate_dir}", pages

    extractor = PDFExtractor()
    if not extractor._is_digital(pdf_path):
        return f"ocr_cache:{candidate_dir}", pages
    extracted = extractor._extract_digital(pdf_path)
    return (
        "native_pdf_text_layer",
        {
            int(page["page_number"]): page.get("text") or ""
            for page in extracted
        },
    )


def _verify_page(
    pdf_path: str,
    page: int,
    candidate: str,
    output_dir: Path,
    dpi: int,
    language: str,
    timeout: int,
    layout: str,
) -> dict[str, object]:
    verifier_path = output_dir / "verifier_text" / f"page_{page:04d}.txt"
    if verifier_path.is_file():
        verifier = verifier_path.read_text(encoding="utf-8")
    else:
        image_path = _convert_page(pdf_path, page, dpi)
        try:
            verifier = _ocr_image(image_path, language, timeout, layout)
        finally:
            _cleanup_image(image_path)
        temporary = verifier_path.with_suffix(".tmp")
        temporary.write_text(verifier, encoding="utf-8")
        temporary.replace(verifier_path)

    comparison = compare_page_transcriptions(candidate, verifier)
    result: dict[str, object] = {
        "page": page,
        "verification_method": "independent_visible_pixel_ocr",
        **comparison.to_dict(),
    }
    page_report = output_dir / "pages" / f"page_{page:04d}.json"
    temporary_report = page_report.with_suffix(".tmp")
    temporary_report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_report.replace(page_report)
    return result


def verify_target(
    target: BookTarget,
    *,
    candidate_cache_root: Path,
    output_root: Path,
    candidate_dpi: int,
    candidate_language: str,
    candidate_source: str,
    verifier_dpi: int,
    verifier_language: str,
    workers: int,
    timeout: int,
    layout: str,
    selected_pages: set[int],
) -> dict[str, object]:
    pdf_path = _resolve_pdf(target)
    if not pdf_path:
        raise RuntimeError("PDF file not found")
    page_total = _page_count(pdf_path)
    candidate_origin, candidates = _read_candidate_pages(
        target,
        pdf_path,
        page_total,
        candidate_cache_root,
        candidate_dpi,
        candidate_language,
        layout,
        candidate_source,
    )
    output_dir = _verification_dir(
        output_root,
        target,
        pdf_path,
        verifier_dpi,
        verifier_language,
        layout,
    )
    pages = [
        page
        for page in range(1, page_total + 1)
        if (not selected_pages or page in selected_pages)
    ]
    missing = [page for page in pages if page not in candidates]
    if missing:
        raise RuntimeError(
            f"candidate OCR is incomplete: {len(missing)} page(s) missing; first={missing[:10]}"
        )

    metadata = {
        "created_at": _now(),
        "book_id": target.book_id,
        "book_file_id": target.file_id,
        "title": target.title,
        "pdf": target.filename,
        "pdf_pages": page_total,
        "selected_pages": pages,
        "candidate": {
            "source": candidate_origin,
            "dpi": candidate_dpi,
            "language": candidate_language,
            "layout": layout,
        },
        "verifier": {
            "output_dir": str(output_dir),
            "dpi": verifier_dpi,
            "language": verifier_language,
            "layout": layout,
            "model_fingerprint": _model_fingerprint(verifier_language),
        },
        "public_promotion": False,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    totals: Counter[str] = Counter()
    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                _verify_page,
                pdf_path,
                page,
                candidates[page],
                output_dir,
                verifier_dpi,
                verifier_language,
                timeout,
                layout,
            ): page
            for page in pages
        }
        for future in as_completed(futures):
            result = future.result()
            totals[str(result["status"])] += 1
            completed += 1
            if completed == 1 or completed % 10 == 0 or completed == len(pages):
                _log({
                    "event": "verification_progress",
                    "book_id": target.book_id,
                    "completed": completed,
                    "total": len(pages),
                    "last_page": result["page"],
                    "totals": dict(totals),
                })

    summary = {
        "status": "verification_queue_built",
        "book_id": target.book_id,
        "pages": len(pages),
        "totals": dict(totals),
        "output_dir": str(output_dir),
        "public_promotion": False,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", type=int, action="append", required=True)
    parser.add_argument("--page", type=int, action="append", default=[])
    parser.add_argument("--layout", choices=("auto", "columns"), default="columns")
    parser.add_argument("--candidate-cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument(
        "--candidate-source",
        choices=("auto", "ocr_cache", "pdf_text"),
        default="auto",
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--candidate-dpi", type=int, default=220)
    parser.add_argument("--candidate-lang", default="lat+grc+eng")
    parser.add_argument("--verifier-dpi", type=int, default=300)
    parser.add_argument("--verifier-lang", default="Latin+lat+grc+eng")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--page-timeout", type=int, default=180)
    args = parser.parse_args()

    targets = _targets(args.book_id)
    missing = sorted(set(args.book_id) - {target.book_id for target in targets})
    if missing:
        _log({"event": "missing_books", "book_ids": missing})
        return 1

    failed = 0
    for target in targets:
        _log({"event": "verification_start", "book_id": target.book_id, "title": target.title})
        try:
            summary = verify_target(
                target,
                candidate_cache_root=args.candidate_cache_root,
                output_root=args.output_root,
                candidate_dpi=args.candidate_dpi,
                candidate_language=args.candidate_lang,
                candidate_source=args.candidate_source,
                verifier_dpi=args.verifier_dpi,
                verifier_language=args.verifier_lang,
                workers=args.workers,
                timeout=args.page_timeout,
                layout=args.layout,
                selected_pages={page for page in args.page if page > 0},
            )
            _log({"event": "verification_done", **summary})
        except Exception as exc:
            failed += 1
            _log({
                "event": "verification_error",
                "book_id": target.book_id,
                "error": f"{type(exc).__name__}: {exc}",
            })
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
