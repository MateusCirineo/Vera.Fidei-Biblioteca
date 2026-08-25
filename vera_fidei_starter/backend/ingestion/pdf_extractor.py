import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

import pdf2image
import pdfplumber
import pytesseract

DIGITAL_THRESHOLD = 50
OCR_LANG_FALLBACKS = (
    "lat+eng",
    "lat+grc+eng",
    "lat+por+eng",
    "fra+lat+eng",
    "grc+lat+eng",
    "fra+por+lat+eng",
    "fra+lat+grc+eng",
    "lat+por",
    "por+eng",
    "fra+eng",
    "fra",
    "eng",
)
OCR_DPI_FALLBACKS = (220, 180, 150)
OCR_PAGE_TIMEOUT_SECONDS = 120
OCR_GOOD_TEXT_CHARS = 80
OCR_MAX_WORKERS = 2
# PSM 3 detects columns. PSM 6 treated a full Migne page as one text block
# and interleaved the left and right columns word by word.
OCR_PSM_MODES = ("--psm 3", "--psm 4", "--psm 6", "--psm 11")
OCR_OEM_MODE = "1"
OCR_CACHE_VERSION = "layout-v2-220dpi"

# Paths resolved relative to the repository root, with Linux container fallbacks.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))

_BUNDLED_POPPLER = os.path.join(_PROJECT_ROOT, "poppler-25.12.0", "Library", "bin")
POPPLER_PATH = os.environ.get("POPPLER_PATH")
if not POPPLER_PATH and os.path.isdir(_BUNDLED_POPPLER):
    POPPLER_PATH = _BUNDLED_POPPLER

PDFTOTEXT_PATH = (
    os.environ.get("PDFTOTEXT_PATH")
    or shutil.which("pdftotext")
    or (os.path.join(POPPLER_PATH, "pdftotext.exe") if POPPLER_PATH else "")
)

TESSDATA_DIR = (
    os.environ.get("TESSDATA_DIR")
    or ("/app/tessdata" if os.path.isdir("/app/tessdata") else "")
    or os.path.join(_BACKEND_DIR, "tessdata")
)
OCR_CACHE_DIR = os.path.join(_BACKEND_DIR, ".ocr_cache")

_WINDOWS_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = (
    os.environ.get("TESSERACT_CMD")
    or shutil.which("tesseract")
    or _WINDOWS_TESSERACT
)


class PDFExtractor:
    def extract(self, pdf_path: str) -> list[dict]:
        if self._is_digital(pdf_path):
            return self._extract_digital(pdf_path)

        # For scanned PDFs, never hide an OCR failure behind an empty digital
        # fallback. If digital fallback has text, use it; otherwise surface the
        # OCR error so ingest status becomes actionable.
        try:
            return self._extract_ocr(pdf_path)
        except Exception as exc:
            fallback_pages = self._extract_digital(pdf_path)
            if any((page.get("text") or "").strip() for page in fallback_pages):
                return fallback_pages
            raise RuntimeError(f"OCR failed and digital fallback extracted no text: {exc}") from exc

    def _is_digital(self, pdf_path: str) -> bool:
        with pdfplumber.open(pdf_path) as pdf:
            if self._looks_scanned(pdf.pages[:8]):
                return False
            # Check the first pages; covers and indexes can be empty.
            for page in pdf.pages[:8]:
                sample = page.extract_text() or ""
                if self._has_usable_digital_text(sample):
                    return True
        return self._has_poppler_sample_text(pdf_path)

    def _looks_scanned(self, pages) -> bool:
        """Conservatively detect full-page scans, including hidden OCR layers.

        A searchable OCR overlay is still OCR; it must not be promoted to
        source text merely because ``extract_text`` returns many characters.
        """
        sampled = 0
        full_page_images = 0
        for page in pages:
            width = float(getattr(page, "width", 0) or 0)
            height = float(getattr(page, "height", 0) or 0)
            page_area = width * height
            if page_area <= 0:
                continue
            sampled += 1
            for image in getattr(page, "images", ()) or ():
                x0 = float(image.get("x0", 0) or 0)
                x1 = float(image.get("x1", x0) or x0)
                top = float(image.get("top", 0) or 0)
                bottom = float(image.get("bottom", top) or top)
                image_area = max(0.0, x1 - x0) * max(0.0, bottom - top)
                if image_area / page_area >= 0.55:
                    full_page_images += 1
                    break
        if sampled < 2:
            return False
        return full_page_images >= max(2, math.ceil(sampled * 0.40))

    def _has_usable_digital_text(self, sample: str) -> bool:
        text = (sample or "").strip()
        if len(text) <= DIGITAL_THRESHOLD:
            return False

        compact = "".join(ch for ch in text if not ch.isspace())
        if not compact:
            return False

        letters = sum(1 for ch in compact if ch.isalpha())
        punctuation = sum(1 for ch in compact if not ch.isalnum())
        replacement = text.count("\ufffd")
        words = re.findall(r"[^\W\d_]{3,}", text, flags=re.UNICODE)

        if replacement / max(len(text), 1) > 0.02:
            return False
        if letters / max(len(compact), 1) < 0.45:
            return False
        if punctuation / max(len(compact), 1) > 0.22:
            return False
        return len(words) >= 8

    def _has_poppler_sample_text(self, pdf_path: str) -> bool:
        if not PDFTOTEXT_PATH or not os.path.exists(PDFTOTEXT_PATH):
            return False

        try:
            result = subprocess.run(
                [PDFTOTEXT_PATH, "-f", "1", "-l", "20", "-layout", "-enc", "UTF-8", pdf_path, "-"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        except Exception as exc:
            print(f"[pdf] pdftotext sample failed for {pdf_path}: {exc}")
            return False

        return result.returncode in (0, 1) and self._has_usable_digital_text(result.stdout or "")

    def _extract_digital(self, pdf_path: str) -> list[dict]:
        poppler_pages = self._extract_digital_poppler(pdf_path)
        if poppler_pages and any((page.get("text") or "").strip() for page in poppler_pages):
            return poppler_pages

        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                pages.append({
                    "page_number": i,
                    "text": page.extract_text() or "",
                    "extraction_method": "digital_text",
                    "source_fidelity": "source_text",
                })
        return pages

    def _extract_digital_poppler(self, pdf_path: str) -> list[dict]:
        if not PDFTOTEXT_PATH or not os.path.exists(PDFTOTEXT_PATH):
            return []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
        except Exception:
            total_pages = 0

        try:
            result = subprocess.run(
                [PDFTOTEXT_PATH, "-layout", "-enc", "UTF-8", pdf_path, "-"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                check=False,
            )
        except Exception as exc:
            print(f"[pdf] pdftotext failed for {pdf_path}: {exc}")
            return []

        if result.returncode not in (0, 1) or not result.stdout:
            return []

        parts = result.stdout.split("\f")
        if parts and not parts[-1].strip():
            parts = parts[:-1]
        if total_pages <= 0:
            total_pages = len(parts)

        return [
            {
                "page_number": page_num,
                "text": parts[page_num - 1] if page_num <= len(parts) else "",
                "extraction_method": "digital_text",
                "source_fidelity": "source_text",
            }
            for page_num in range(1, total_pages + 1)
        ]

    def _extract_ocr(self, pdf_path: str) -> list[dict]:
        # Process one page at a time. PG001 is hundreds of scanned pages; a
        # single native Tesseract/Poppler failure must not discard the volume.
        with pdfplumber.open(pdf_path) as _pdf:
            total_pages = len(_pdf.pages)

        cache_dir = self._cache_dir(pdf_path)
        os.makedirs(cache_dir, exist_ok=True)

        page_texts: dict[int, str] = {}
        pending_pages: list[int] = []

        for page_num in range(1, total_pages + 1):
            cached = self._read_cached_page(cache_dir, page_num)
            if cached is None:
                pending_pages.append(page_num)
            else:
                page_texts[page_num] = cached

        if pending_pages:
            print(
                f"[ocr] {len(page_texts)}/{total_pages} pages loaded from cache; "
                f"{len(pending_pages)} pages pending"
            )

        completed = len(page_texts)
        with ThreadPoolExecutor(max_workers=OCR_MAX_WORKERS) as executor:
            future_map = {
                executor.submit(self._extract_and_cache_page, pdf_path, cache_dir, page_num): page_num
                for page_num in pending_pages
            }
            for future in as_completed(future_map):
                page_num = future_map[future]
                try:
                    text = future.result()
                except Exception as exc:
                    print(f"[ocr] page={page_num} unexpected failure: {exc}")
                    text = ""
                    self._write_cached_page(cache_dir, page_num, text)
                page_texts[page_num] = text
                completed += 1
                if completed == 1 or completed % 25 == 0 or completed == total_pages:
                    print(
                        f"[ocr] completed {completed}/{total_pages}; "
                        f"last_page={page_num} chars={len(text.strip())}"
                    )

        return [
            {
                "page_number": page_num,
                "text": page_texts.get(page_num, ""),
                "extraction_method": "ocr",
                # OCR output remains an internal discovery aid until a human
                # or an authoritative transcription verifies it against the
                # rendered page. It must not become a public quotation.
                "source_fidelity": "unverified_ocr",
            }
            for page_num in range(1, total_pages + 1)
        ]

    def _extract_and_cache_page(self, pdf_path: str, cache_dir: str, page_num: int) -> str:
        text = self._extract_page_ocr(pdf_path, page_num)
        self._write_cached_page(cache_dir, page_num, text)
        return text

    def _extract_page_ocr(self, pdf_path: str, page_num: int) -> str:
        best_text = ""
        errors = []

        for dpi in OCR_DPI_FALLBACKS:
            for use_cairo in (False, True):
                image_path = self._convert_page_to_image_path(
                    pdf_path,
                    page_num,
                    dpi=dpi,
                    use_cairo=use_cairo,
                )
                if image_path is None:
                    continue

                try:
                    text = self._ocr_image_path(image_path, page_num)
                    if len(text.strip()) > len(best_text.strip()):
                        best_text = text
                    if len(text.strip()) >= OCR_GOOD_TEXT_CHARS:
                        return text
                except Exception as exc:
                    errors.append(str(exc))
                finally:
                    self._cleanup_image_path(image_path)

        if not best_text.strip():
            joined = " | ".join(errors[-3:])
            print(f"[ocr] page={page_num} produced no text after all fallbacks: {joined}")
        return best_text

    def _convert_page_to_image_path(
        self,
        pdf_path: str,
        page_num: int,
        dpi: int,
        use_cairo: bool,
    ) -> str | None:
        temp_dir = tempfile.mkdtemp(prefix=f"vf_ocr_{page_num}_")
        try:
            paths = pdf2image.convert_from_path(
                pdf_path,
                dpi=dpi,
                poppler_path=POPPLER_PATH,
                first_page=page_num,
                last_page=page_num,
                grayscale=True,
                thread_count=1,
                paths_only=True,
                output_folder=temp_dir,
                fmt="png",
                single_file=True,
                use_pdftocairo=use_cairo,
            )
            return paths[0] if paths else None
        except Exception as exc:
            print(
                f"[ocr] page conversion failed page={page_num} "
                f"dpi={dpi} cairo={use_cairo}: {exc}"
            )
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass
            return None

    def _ocr_image_path(self, image_path: str, page_num: int) -> str:
        base_config = "--oem 1" if OCR_OEM_MODE else ""
        if os.path.isdir(TESSDATA_DIR):
            base_config = f"{base_config} --tessdata-dir \"{TESSDATA_DIR}\""
        best_text = ""
        last_error: Exception | None = None
        for lang in OCR_LANG_FALLBACKS:
            for mode in OCR_PSM_MODES:
                try:
                    text = pytesseract.image_to_string(
                        image_path,
                        lang=lang,
                        config=f"{base_config} {mode}".strip(),
                        timeout=OCR_PAGE_TIMEOUT_SECONDS,
                    )
                    if len(text.strip()) > len(best_text.strip()):
                        best_text = text
                    if len(text.strip()) >= OCR_GOOD_TEXT_CHARS:
                        return text
                except Exception as exc:
                    last_error = exc
                    print(f"[ocr] page={page_num} failed lang={lang} mode={mode}: {exc}")

        if best_text.strip():
            return best_text
        if last_error is not None:
            raise last_error
        return ""

    def _cleanup_image_path(self, image_path: str) -> None:
        temp_dir = os.path.dirname(image_path)
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _cache_dir(self, pdf_path: str) -> str:
        return os.path.join(OCR_CACHE_DIR, self._pdf_cache_key(pdf_path))

    def _pdf_cache_key(self, pdf_path: str) -> str:
        # SHA-1 is sufficient for a non-security OCR cache key.  Mark that
        # intent explicitly so security tooling cannot mistake it for signing.
        hasher = hashlib.sha1(usedforsecurity=False)
        hasher.update(OCR_CACHE_VERSION.encode("ascii"))
        with open(pdf_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _cache_file(self, cache_dir: str, page_num: int) -> str:
        return os.path.join(cache_dir, f"page_{page_num:04d}.txt")

    def _read_cached_page(self, cache_dir: str, page_num: int) -> str | None:
        path = self._cache_file(cache_dir, page_num)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _write_cached_page(self, cache_dir: str, page_num: int, text: str) -> None:
        path = self._cache_file(cache_dir, page_num)
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(temp_path, path)
