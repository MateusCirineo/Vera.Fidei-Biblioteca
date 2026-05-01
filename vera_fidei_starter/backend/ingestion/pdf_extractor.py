import hashlib
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pdf2image
import pdfplumber
import pytesseract

DIGITAL_THRESHOLD = 50
OCR_LANG_FALLBACKS = (
    "lat+grc+por+eng",
    "lat+eng",
    "lat+por+eng",
    "eng",
)
OCR_DPI_FALLBACKS = (150, 125, 100)
OCR_PAGE_TIMEOUT_SECONDS = 120
OCR_GOOD_TEXT_CHARS = 80
OCR_MAX_WORKERS = 2

# Paths resolved relative to the repository root, without relying on PATH.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))

POPPLER_PATH = os.path.join(_PROJECT_ROOT, "poppler-25.12.0", "Library", "bin")
PDFTOTEXT_PATH = os.path.join(POPPLER_PATH, "pdftotext.exe")
TESSDATA_DIR = os.path.join(_BACKEND_DIR, "tessdata")
OCR_CACHE_DIR = os.path.join(_BACKEND_DIR, ".ocr_cache")

# Installed Tesseract executable.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


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
            # Check the first pages; covers and indexes can be empty.
            for page in pdf.pages[:8]:
                sample = page.extract_text() or ""
                if len(sample.strip()) > DIGITAL_THRESHOLD:
                    return True
        return self._has_poppler_sample_text(pdf_path)

    def _has_poppler_sample_text(self, pdf_path: str) -> bool:
        if not os.path.exists(PDFTOTEXT_PATH):
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

        return result.returncode in (0, 1) and len((result.stdout or "").strip()) > DIGITAL_THRESHOLD

    def _extract_digital(self, pdf_path: str) -> list[dict]:
        poppler_pages = self._extract_digital_poppler(pdf_path)
        if poppler_pages and any((page.get("text") or "").strip() for page in poppler_pages):
            return poppler_pages

        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                pages.append({"page_number": i, "text": page.extract_text() or ""})
        return pages

    def _extract_digital_poppler(self, pdf_path: str) -> list[dict]:
        if not os.path.exists(PDFTOTEXT_PATH):
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
            {"page_number": page_num, "text": parts[page_num - 1] if page_num <= len(parts) else ""}
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
            {"page_number": page_num, "text": page_texts.get(page_num, "")}
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
        tessdata_config = f'--tessdata-dir "{TESSDATA_DIR}"'
        best_text = ""
        last_error: Exception | None = None

        for lang in OCR_LANG_FALLBACKS:
            try:
                text = pytesseract.image_to_string(
                    image_path,
                    lang=lang,
                    config=tessdata_config,
                    timeout=OCR_PAGE_TIMEOUT_SECONDS,
                )
                if len(text.strip()) > len(best_text.strip()):
                    best_text = text
                if len(text.strip()) >= OCR_GOOD_TEXT_CHARS:
                    return text
            except Exception as exc:
                last_error = exc
                print(f"[ocr] page={page_num} failed lang={lang}: {exc}")

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
        hasher = hashlib.sha1()
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
