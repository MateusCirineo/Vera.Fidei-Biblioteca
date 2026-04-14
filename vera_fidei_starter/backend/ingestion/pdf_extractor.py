import os

import pdfplumber
import pdf2image
import pytesseract

DIGITAL_THRESHOLD = 50
TESSERACT_LANG = "lat+grc+por+eng"

# Caminhos resolvidos relativos à raiz do repositório — sem depender do PATH do sistema
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))

POPPLER_PATH = os.path.join(_PROJECT_ROOT, "poppler-25.12.0", "Library", "bin")
TESSDATA_DIR = os.path.join(_BACKEND_DIR, "tessdata")

# Apontar para o executável do Tesseract instalado
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class PDFExtractor:
    def extract(self, pdf_path: str) -> list[dict]:
        if self._is_digital(pdf_path):
            return self._extract_digital(pdf_path)
        # Tenta OCR — se Poppler/Tesseract não estiver disponível, usa pdfplumber como fallback
        try:
            return self._extract_ocr(pdf_path)
        except Exception:
            return self._extract_digital(pdf_path)

    def _is_digital(self, pdf_path: str) -> bool:
        with pdfplumber.open(pdf_path) as pdf:
            # Verifica as primeiras 8 páginas — capas e índices iniciais podem estar vazios
            for page in pdf.pages[:8]:
                sample = page.extract_text() or ""
                if len(sample.strip()) > DIGITAL_THRESHOLD:
                    return True
        return False

    def _extract_digital(self, pdf_path: str) -> list[dict]:
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                pages.append({"page_number": i, "text": page.extract_text() or ""})
        return pages

    def _extract_ocr(self, pdf_path: str) -> list[dict]:
        images = pdf2image.convert_from_path(pdf_path, dpi=150, poppler_path=POPPLER_PATH)
        pages = []
        tessdata_config = f'--tessdata-dir "{TESSDATA_DIR}"'
        for i, image in enumerate(images, start=1):
            text = pytesseract.image_to_string(image, lang=TESSERACT_LANG, config=tessdata_config)
            pages.append({"page_number": i, "text": text})
        return pages
