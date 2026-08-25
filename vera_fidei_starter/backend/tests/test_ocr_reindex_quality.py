import unittest
from unittest.mock import patch

from PIL import Image

from scripts.ocr_reindex_books import (
    _apply_verified_source_passages,
    _chunk_pages,
    _normalize_ocr_text,
    _ocr_image,
    _validate_pages,
)


class OcrTextNormalizationTests(unittest.TestCase):
    def test_joins_only_words_hyphenated_across_a_line(self) -> None:
        text = "inquie-\nbat, sanctum de Maria\nCAPUT VII."
        self.assertEqual(
            _normalize_ocr_text(text),
            "inquiebat, sanctum de Maria\nCAPUT VII.",
        )

    def test_columns_are_recognized_independently_and_kept_in_reading_order(self) -> None:
        image = Image.new("L", (100, 120), color=255)
        with patch("scripts.ocr_reindex_books.Image.open") as open_image, patch(
            "scripts.ocr_reindex_books._recognize",
            side_effect=("left column", "right column"),
        ) as recognize:
            open_image.return_value.__enter__.return_value.copy.return_value = image
            text = _ocr_image("page.png", "lat+eng", 120, "columns")

        self.assertEqual(text, "left column\n\nright column")
        self.assertEqual(recognize.call_count, 2)
        self.assertTrue(all(call.args[3] == 6 for call in recognize.call_args_list))


class OcrQualityGateTests(unittest.TestCase):
    def test_source_anchors_must_exist_before_swap(self) -> None:
        pages = [
            {
                "page_number": number,
                "text": (
                    "sanctum de Maria Virgine genitum esse fateantur. "
                    "Petrum dicitur. " + "litterae latinae " * 30
                ),
            }
            for number in range(1, 6)
        ]
        report = _validate_pages(
            pages,
            ("sanctum de Maria Virgine genitum esse fateantur", "Petrum dicitur"),
        )
        self.assertEqual(report["missing_anchors"], [])

        with self.assertRaisesRegex(RuntimeError, "missing source anchors"):
            _validate_pages(pages, ("textus qui in fonte non est",))

    def test_verified_pg001_passage_and_page_mapping(self) -> None:
        pages = [
            {"page_number": 11, "text": "prior page " * 600},
            {
                "page_number": 12,
                "text": (
                    "prefix Utrum vero ipsis broken OCR words et Origenes. "
                    + "remaining page " * 600
                ),
            },
        ]
        corrected = _apply_verified_source_passages(32, pages)
        self.assertIn("simplicem illum hominem asseverent", corrected[1]["text"])
        self.assertIn("Justinus philosophus et martyr", corrected[1]["text"])

        from ingestion.chunker import Chunker

        chunks = _chunk_pages(Chunker(), corrected)
        passage_chunks = [chunk for chunk in chunks if "Maria Virgine" in chunk["text"]]
        self.assertTrue(passage_chunks)
        self.assertTrue(all(chunk["pdf_page"] == 12 for chunk in passage_chunks))


if __name__ == "__main__":
    unittest.main()
