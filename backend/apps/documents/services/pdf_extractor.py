"""
Page-by-page text extraction with PyMuPDF.

Only used during document processing (Celery). Chat requests never touch the
PDF again — they work from MySQL chunks + Qdrant vectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pymupdf as fitz

from .text_cleaning import clean_text, has_meaningful_text


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int  # 1-based
    text: str
    has_text: bool


class PdfExtractionError(Exception):
    pass


def open_pdf(path: str | Path) -> fitz.Document:
    try:
        pdf = fitz.open(str(path))
    except Exception as exc:  # noqa: BLE001
        raise PdfExtractionError(f"Could not open PDF: {exc}") from exc
    if pdf.is_encrypted and not pdf.authenticate(""):
        pdf.close()
        raise PdfExtractionError("PDF is encrypted.")
    if pdf.page_count == 0:
        pdf.close()
        raise PdfExtractionError("PDF has no pages.")
    return pdf


def iter_pages(pdf: fitz.Document) -> Iterator[ExtractedPage]:
    for index in range(pdf.page_count):
        try:
            page = pdf.load_page(index)
            raw = page.get_text("text") or ""
        except Exception:  # noqa: BLE001 — a single bad page should not kill the whole document
            raw = ""
        cleaned = clean_text(raw)
        yield ExtractedPage(page_number=index + 1, text=cleaned, has_text=has_meaningful_text(cleaned))


def extract_pages(path: str | Path) -> list[ExtractedPage]:
    with open_pdf(path) as pdf:
        return list(iter_pages(pdf))


def read_metadata_title(pdf: fitz.Document) -> str:
    title = ((pdf.metadata or {}).get("title") or "").strip()
    return title if 0 < len(title) <= 200 else ""
