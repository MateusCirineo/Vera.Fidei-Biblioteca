from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

from services.source_fidelity_service import normalize_literal


@dataclass(frozen=True)
class PageComparison:
    status: str
    exact: bool
    agreement_ratio: float
    candidate_sha256: str
    verifier_sha256: str
    candidate_chars: int
    verifier_chars: int
    differences: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def text_sha256(text: str | None) -> str:
    literal = normalize_literal(text)
    return hashlib.sha256(literal.encode("utf-8")).hexdigest()


def compare_page_transcriptions(
    candidate: str | None,
    verifier: str | None,
    *,
    max_differences: int = 20,
) -> PageComparison:
    """Compare two image-derived readings without silently changing words.

    Whitespace and soft hyphens are transport/layout details and are the only
    normalization allowed here. Ligatures, accents, punctuation and spelling
    remain significant because the public claim is literal source fidelity.
    """
    left = normalize_literal(candidate)
    right = normalize_literal(verifier)
    exact = bool(left) and left == right
    matcher = SequenceMatcher(None, left, right, autojunk=False)
    differences: list[dict[str, object]] = []
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        differences.append({
            "operation": tag,
            "candidate": left[left_start:left_end],
            "verifier": right[right_start:right_end],
            "candidate_offset": [left_start, left_end],
            "verifier_offset": [right_start, right_end],
        })
        if len(differences) >= max(0, max_differences):
            break

    if not left or not right:
        status = "missing_reading"
    elif exact:
        status = "independent_ocr_consensus"
    else:
        status = "needs_visual_review"

    return PageComparison(
        status=status,
        exact=exact,
        agreement_ratio=round(matcher.ratio(), 6),
        candidate_sha256=text_sha256(left),
        verifier_sha256=text_sha256(right),
        candidate_chars=len(left),
        verifier_chars=len(right),
        differences=tuple(differences),
    )
