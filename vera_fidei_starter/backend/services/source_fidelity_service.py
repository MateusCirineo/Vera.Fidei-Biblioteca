from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


PUBLIC_SOURCE_FIDELITIES = frozenset({"source_text", "verified"})


@dataclass(frozen=True)
class VerifiedPassageCandidate:
    text: str
    language: str | None = None
    method: str = "visual_pdf"


def normalize_literal(value: str | None) -> str:
    """Normalize transport/layout only; never silently correct source words."""
    text = unicodedata.normalize("NFC", value or "")
    text = text.replace("\u00ad", "")
    return re.sub(r"\s+", " ", text).strip()


def _comparison_key(value: str | None) -> str:
    return normalize_literal(value).casefold().strip("… ")


def select_verified_passage(
    displayed_text: str | None,
    query: str | None,
    passages: Iterable[VerifiedPassageCandidate],
) -> VerifiedPassageCandidate | None:
    """Return a page transcription only when it actually supports the hit.

    The returned text is always the stored, visually checked transcription;
    OCR text is used only to locate the candidate and is never returned as the
    authoritative wording.
    """
    candidate_key = _comparison_key(displayed_text)
    query_key = _comparison_key(query)
    for passage in passages:
        verified_key = _comparison_key(passage.text)
        if not verified_key:
            continue
        # When the caller supplied a query, the verified wording must support
        # that query itself. A large OCR chunk can contain one checked passage
        # plus unrelated corrupted words from the same page; those unrelated
        # words must never inherit the passage's approval.
        if query_key:
            if query_key in verified_key:
                return passage
            continue
        if candidate_key and (candidate_key in verified_key or verified_key in candidate_key):
            return passage
    return None
