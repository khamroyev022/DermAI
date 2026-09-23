"""
Upload-time PDF validation: extension, MIME/magic bytes, size, corruption, emptiness.

Runs synchronously in the upload request so the user gets immediate feedback.
Heavy work (text extraction, embeddings) is deferred to Celery.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pymupdf as fitz
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from rest_framework import serializers

ALLOWED_MIME_TYPES = {"application/pdf", "application/x-pdf"}
PDF_MAGIC = b"%PDF-"


@dataclass(frozen=True)
class PdfInspection:
    sha256: str
    size: int
    page_count: int
    title: str


def _iter_chunks(uploaded: UploadedFile, chunk_size: int = 1024 * 1024):
    uploaded.seek(0)
    while True:
        data = uploaded.read(chunk_size)
        if not data:
            break
        yield data
    uploaded.seek(0)


def compute_sha256(uploaded: UploadedFile) -> str:
    digest = hashlib.sha256()
    for block in _iter_chunks(uploaded):
        digest.update(block)
    return digest.hexdigest()


def validate_pdf_upload(uploaded: UploadedFile) -> PdfInspection:
    """Raise serializers.ValidationError on any problem, else return inspection data."""
    name = (uploaded.name or "").strip()
    if not name.lower().endswith(".pdf"):
        raise serializers.ValidationError("Only .pdf files are accepted.")

    content_type = (uploaded.content_type or "").lower()
    if content_type and content_type not in ALLOWED_MIME_TYPES and content_type != "application/octet-stream":
        raise serializers.ValidationError(f"Unsupported content type '{content_type}'. Expected application/pdf.")

    max_bytes = settings.MAX_PDF_SIZE_MB * 1024 * 1024
    size = uploaded.size or 0
    if size <= 0:
        raise serializers.ValidationError("The uploaded file is empty.")
    if size > max_bytes:
        raise serializers.ValidationError(f"File is too large. Maximum size is {settings.MAX_PDF_SIZE_MB} MB.")

    uploaded.seek(0)
    head = uploaded.read(len(PDF_MAGIC) + 3)
    uploaded.seek(0)
    if not head.startswith(PDF_MAGIC):
        raise serializers.ValidationError("The file is not a valid PDF (bad signature).")

    sha256 = compute_sha256(uploaded)

    # Open with PyMuPDF to detect corruption / encryption / empty documents.
    try:
        data = uploaded.read()
        uploaded.seek(0)
        with fitz.open(stream=data, filetype="pdf") as pdf:
            if pdf.is_encrypted and not pdf.authenticate(""):
                raise serializers.ValidationError("Encrypted PDFs are not supported.")
            page_count = pdf.page_count
            metadata_title = (pdf.metadata or {}).get("title") or ""
    except serializers.ValidationError:
        raise
    except Exception:  # noqa: BLE001 — PyMuPDF raises various error types for corrupt files
        raise serializers.ValidationError("The PDF appears to be corrupted and could not be opened.")

    if page_count == 0:
        raise serializers.ValidationError("The PDF has no pages.")

    title = metadata_title.strip()
    if not title or len(title) > 200:
        title = name[:-4].strip() or "Untitled document"

    return PdfInspection(sha256=sha256, size=size, page_count=page_count, title=title[:255])
