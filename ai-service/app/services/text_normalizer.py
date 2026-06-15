"""Small text helpers for Vietnamese chatbot matching."""
from __future__ import annotations

import unicodedata


def strip_vietnamese_accents(value: str) -> str:
    """Return lowercase-ish search text without Vietnamese tone marks."""
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(
        char for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    return without_marks.replace("đ", "d").replace("Đ", "D")


def search_variants(value: str) -> tuple[str, ...]:
    """Return original normalized text plus an accent-folded variant."""
    original = unicodedata.normalize("NFC", value or "").lower()
    folded = strip_vietnamese_accents(original).lower()
    if folded == original:
        return (original,)
    return (original, folded)


def lookup_text(value: str) -> str:
    """Join variants for regex checks that only need intent/entity signals."""
    variants = search_variants(value)
    return " ".join(variants)
