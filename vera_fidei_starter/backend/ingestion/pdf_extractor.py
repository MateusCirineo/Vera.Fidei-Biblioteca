import pdfplumber
import pdf2image
import pytesseract

DIGITAL_THRESHOLD = 50
TESSERACT_LANG = "lat+grc+por+eng"


class PDFExtractor:
    def extract(self, pdf_path: str) -> list[dict]:
        if self._is_digital(pdf_path):
            return self._extract_digital(pdf_path)
        return self._extract_ocr(pdf_path)

    def _is_digital(self, pdf_path: str) -> bool:
        with pdfplumber.open(pdf_path) as pdf:
            sample = pdf.pages[0].extract_text() or ""
            return len(sample.strip()) > DIGITAL_THRESHOLD

    def _extract_digital(self, pdf_path: str) -> list[dict]:
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                pages.append({"page_number": i, "text": page.extract_text() or ""})
        return pages

    def _extract_ocr(self, pdf_path: str) -> list[dict]:
        images = pdf2image.convert_from_path(pdf_path, dpi=300)
        pages = []
        for i, image in enumerate(images, start=1):
            text = pytesseract.image_to_string(image, lang=TESSERACT_LANG)
            pages.append({"page_number": i, "text": text})
        return pages
