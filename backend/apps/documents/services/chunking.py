"""
Page-aware, boundary-aware text chunking.

Pages are split into sentence-like units; units are packed into chunks of at most
`chunk_size` length units (characters by default, or tokens when a `length_fn`
is supplied) with `chunk_overlap` carried over between consecutive chunks.
Chunks never cut a word in half, and each chunk remembers the page range its
units came from (page_start / page_end), so answers can cite pages.

Default `CHUNK_SIZE=800` characters ≈ 200 tokens, which fits comfortably within
the 512-token window of multilingual-e5 models.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

LengthFn = Callable[[str], int]

# Split after sentence terminators (., !, ?, …, ;) followed by whitespace,
# or on paragraph breaks. Works for Latin and Cyrillic scripts.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…;])\s+|\n{2,}")
_WORD_SPLIT = re.compile(r"\s+")


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    page_start: int
    page_end: int
    text: str


@dataclass(frozen=True)
class _Unit:
    page_number: int
    text: str
    length: int


def _split_into_units(page: PageText, chunk_size: int, length_fn: LengthFn) -> list[_Unit]:
    """Sentences, but any sentence longer than chunk_size is further split on words."""
    units: list[_Unit] = []
    for sentence in _SENTENCE_SPLIT.split(page.text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if length_fn(sentence) <= chunk_size:
            units.append(_Unit(page.page_number, sentence, length_fn(sentence)))
            continue
        # Overlong sentence (e.g. a table or a list without punctuation): pack words.
        buffer: list[str] = []
        buffer_len = 0
        for word in _WORD_SPLIT.split(sentence):
            if not word:
                continue
            word_len = length_fn(word)
            if buffer and buffer_len + 1 + word_len > chunk_size:
                joined = " ".join(buffer)
                units.append(_Unit(page.page_number, joined, length_fn(joined)))
                buffer, buffer_len = [], 0
            buffer.append(word)
            buffer_len += word_len + (1 if buffer_len else 0)
        if buffer:
            joined = " ".join(buffer)
            units.append(_Unit(page.page_number, joined, length_fn(joined)))
    return units


def _overlap_tail(units: Sequence[_Unit], overlap: int) -> list[_Unit]:
    """Return the trailing units whose combined length is <= overlap."""
    if overlap <= 0:
        return []
    tail: list[_Unit] = []
    total = 0
    for unit in reversed(units):
        if total + unit.length > overlap:
            break
        tail.insert(0, unit)
        total += unit.length + 1
    return tail


def chunk_pages(
    pages: Iterable[PageText],
    chunk_size: int = 800,
    chunk_overlap: int = 150,
    length_fn: LengthFn | None = None,
) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")
    length_fn = length_fn or len

    units: list[_Unit] = []
    for page in pages:
        if page.text and page.text.strip():
            units.extend(_split_into_units(page, chunk_size, length_fn))

    chunks: list[Chunk] = []
    current: list[_Unit] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        text = " ".join(u.text for u in current).strip()
        if text:
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    page_start=min(u.page_number for u in current),
                    page_end=max(u.page_number for u in current),
                    text=text,
                )
            )
        carried = _overlap_tail(current, chunk_overlap)
        current = list(carried)
        current_len = sum(u.length for u in carried) + max(0, len(carried) - 1)

    for unit in units:
        projected = current_len + unit.length + (1 if current else 0)
        if current and projected > chunk_size:
            flush()
            # If the overlap alone plus the new unit still overflows, drop the overlap.
            if current and current_len + unit.length + 1 > chunk_size:
                current, current_len = [], 0
        current.append(unit)
        current_len += unit.length + (1 if current_len else 0)

    if current:
        text = " ".join(u.text for u in current).strip()
        # Avoid emitting a final chunk that is purely overlap of the previous one.
        if text and (not chunks or text != chunks[-1].text and not chunks[-1].text.endswith(text)):
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    page_start=min(u.page_number for u in current),
                    page_end=max(u.page_number for u in current),
                    text=text,
                )
            )
    return chunks
