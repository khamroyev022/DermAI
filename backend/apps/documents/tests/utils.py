"""Helpers for document tests: generate small real PDFs with PyMuPDF, isolate media."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pymupdf as fitz
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings


def make_pdf_bytes(pages: list[str], title: str | None = None) -> bytes:
    pdf = fitz.open()
    for text in pages:
        page = pdf.new_page()
        if text:
            page.insert_text((72, 72), text, fontsize=11)
    if title:
        pdf.set_metadata({"title": title})
    data = pdf.tobytes()
    pdf.close()
    return data


def make_upload(name: str = "book.pdf", pages: list[str] | None = None, content_type: str = "application/pdf", data: bytes | None = None):
    if data is None:
        data = make_pdf_bytes(pages or ["Vitiligo is a chronic skin disorder."])
    return SimpleUploadedFile(name, data, content_type=content_type)


class TempMediaMixin:
    """Give every test class its own MEDIA_ROOT that is removed afterwards."""

    @classmethod
    def setUpClass(cls):
        cls._media_dir = Path(tempfile.mkdtemp(prefix="bookai-media-"))
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
