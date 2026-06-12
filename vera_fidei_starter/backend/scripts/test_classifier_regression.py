from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidence.classifier import DeterministicClassifier


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def main() -> int:
    classifier = DeterministicClassifier()

    similar_not_exact = classifier.classify(
        combined_score=0.86,
        exact_match=False,
        author_match=True,
        lexical_anchor=0.35,
    )
    assert_equal(similar_not_exact.code, "NAO_ENCONTRADA", "similar non-exact code")
    assert_equal(similar_not_exact.confidence, "Nenhuma", "similar non-exact confidence")

    exact = classifier.classify(
        combined_score=0.20,
        exact_match=True,
        author_match=True,
        lexical_anchor=0.35,
    )
    assert_equal(exact.code, "CONFIRMADA_EXATA", "exact code")
    assert_equal(exact.confidence, "Alta", "exact confidence")

    wrong_author_exact = classifier.classify(
        combined_score=0.10,
        exact_match=True,
        author_match=False,
        lexical_anchor=0.35,
    )
    assert_equal(wrong_author_exact.code, "ATRIBUICAO_DUVIDOSA", "wrong author exact code")
    assert_equal(wrong_author_exact.confidence, "Baixa", "wrong author exact confidence")

    print("classifier regression ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
