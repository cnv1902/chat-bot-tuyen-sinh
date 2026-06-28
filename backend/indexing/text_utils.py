"""
Small text-normalization helpers for the indexing pipeline.

The OCR/LLM path occasionally returns UTF-8 text that has already been decoded
through a Windows/Latin code page once or twice. Repair it before chunking and
embedding so Qdrant stores/searches real Vietnamese text instead of mojibake.
"""

from __future__ import annotations

import unicodedata
from typing import Any


_TRANSCODE_ENCODINGS: tuple[str, ...] = ("latin1", "cp1252", "cp1258")

_MOJIBAKE_MARKERS: tuple[str, ...] = (
    "\u00c3",      # Ã
    "\u00c2",      # Â
    "\u00c4",      # Ä
    "\u00c5",      # Å
    "\u00c6",      # Æ
    "\u0102",      # Ă
    "\u00e1\u00ba",  # áº
    "\u00e1\u00bb",  # á»
    "\ufffd",      # replacement char
)


def repair_mojibake(value: str) -> str:
    """
    Best-effort repair for common UTF-8 mojibake.

    Examples this is designed to fix include:
    - "SÃ†Â° phÃ¡ÂºÂ¡m" -> "Sư phạm"
    - "SÆ° pháº¡m" -> "Sư phạm"

    Correct Vietnamese text is returned unchanged.
    """
    if not value:
        return value

    original = unicodedata.normalize("NFC", value)
    if not _looks_like_mojibake(original):
        return original

    candidates: set[str] = {original}
    frontier: set[str] = {original}

    # Up to three passes handles the double-encoded payloads seen in Qdrant
    # without spending noticeable time on normal text.
    for _ in range(3):
        next_frontier: set[str] = set()
        for text in frontier:
            for encoding in _TRANSCODE_ENCODINGS:
                try:
                    candidate = text.encode(encoding).decode("utf-8")
                except (LookupError, UnicodeError):
                    continue

                candidate = unicodedata.normalize("NFC", candidate)
                if candidate and candidate not in candidates:
                    candidates.add(candidate)
                    next_frontier.add(candidate)

        if not next_frontier:
            break
        frontier = next_frontier

    return min(
        candidates,
        key=lambda item: (_mojibake_score(item), abs(len(item) - len(original))),
    )


def repair_text_tree(value: Any) -> Any:
    """Recursively repair strings inside dict/list structures."""
    if isinstance(value, str):
        return repair_mojibake(value)
    if isinstance(value, list):
        return [repair_text_tree(item) for item in value]
    if isinstance(value, dict):
        return {
            repair_mojibake(key) if isinstance(key, str) else key: repair_text_tree(item)
            for key, item in value.items()
        }
    return value


def normalize_scope(value: Any) -> str:
    """
    Normalize document scope metadata.

    School-wide/ministry documents should use "all". Only keep a concrete value
    when the document clearly belongs to a specific faculty/institute/unit.
    """
    text = repair_mojibake(str(value or "all")).strip()
    if not text or text.lower() in {"none", "null"}:
        return "all"

    folded = _fold_vietnamese(text)
    school_wide_markers = (
        "all",
        "truong dai hoc vinh",
        "dai hoc vinh",
        "bo giao duc",
        "bo gd",
        "bo giao duc va dao tao",
    )
    if any(marker in folded for marker in school_wide_markers):
        return "all"

    return text


def _looks_like_mojibake(text: str) -> bool:
    return any(marker in text for marker in _MOJIBAKE_MARKERS)


def _mojibake_score(text: str) -> int:
    score = 0
    for marker in _MOJIBAKE_MARKERS:
        score += text.count(marker) * 10
    score += sum(1 for char in text if unicodedata.category(char) == "Cc") * 20
    return score


def _fold_vietnamese(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    without_marks = "".join(
        char for char in normalized
        if unicodedata.category(char) != "Mn"
    )
    return without_marks.replace("\u0111", "d")
