"""
Conservative text normalisation for PDF-extracted text.

Goals: remove layout noise (stray whitespace, hard line breaks inside sentences,
hyphenation at line ends) without changing the meaning or the vocabulary.
No summarisation, no AI rewriting.
"""

from __future__ import annotations

import re
import unicodedata

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SOFT_HYPHEN = "­"
_MULTI_SPACE = re.compile(r"[ \t  -​  　]+")
_HYPHEN_LINEBREAK = re.compile(r"(\w)-\n(?=[a-zа-яёЀ-ӿ])", re.IGNORECASE)
_SINGLE_LINEBREAK = re.compile(r"(?<!\n)\n(?!\n)")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_SPACE_BEFORE_PUNCT = re.compile(r" +([,.;:!?%)\]])")


def clean_text(raw: str) -> str:
    """Return cleaned text; an empty string if nothing meaningful remains."""
    if not raw:
        return ""

    text = unicodedata.normalize("NFKC", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(_SOFT_HYPHEN, "")
    text = _CONTROL_CHARS.sub("", text)

    # Trim trailing whitespace on each line.
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Re-join words hyphenated across a line break: "derma-\ntology" -> "dermatology".
    text = _HYPHEN_LINEBREAK.sub(r"\1", text)

    # Collapse 3+ newlines to a paragraph break, and single newlines to spaces
    # (PDF extractors emit a newline at every visual line end).
    text = _MULTI_NEWLINE.sub("\n\n", text)
    text = _SINGLE_LINEBREAK.sub(" ", text)

    text = _MULTI_SPACE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)

    # Clean each paragraph's edges.
    paragraphs = [p.strip() for p in text.split("\n\n")]
    text = "\n\n".join(p for p in paragraphs if p)

    return text.strip()


def has_meaningful_text(text: str, minimum_alnum: int = 20) -> bool:
    """True when the page has enough letters/digits to be worth indexing."""
    return sum(ch.isalnum() for ch in text) >= minimum_alnum
