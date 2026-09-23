"""
Document processing pipeline (runs inside the Celery task):

    PDF -> PyMuPDF extraction -> DocumentPage rows -> clean text -> chunks
        -> embeddings -> Qdrant upsert -> status READY

Progress milestones:
    5 validation, 15 opening PDF, 20 extracting, 50 chunking,
    60 embedding, 90 Qdrant upload, 100 READY.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction

from apps.rag.services.embeddings import get_embedding_provider
from apps.rag.services.qdrant_service import ChunkVector, get_qdrant_service, new_point_id

from ..models import Document, DocumentChunk, DocumentPage
from .chunking import PageText, chunk_pages
from .pdf_extractor import PdfExtractionError, iter_pages, open_pdf, read_metadata_title

logger = logging.getLogger(__name__)

PAGE_BATCH = 200
CHUNK_BATCH = 500


class ProcessingError(Exception):
    pass


def _reset_previous_artifacts(document: Document) -> None:
    """Make processing idempotent (safe on retries)."""
    get_qdrant_service().delete_document_vectors(document.id)
    DocumentChunk.objects.filter(document=document).delete()
    DocumentPage.objects.filter(document=document).delete()


def process_document(document_id: int) -> None:
    document = Document.objects.select_related("user").get(pk=document_id)
    document.processing_error = ""
    document.set_progress(5, Document.Status.PROCESSING)

    try:
        _reset_previous_artifacts(document)

        # -- open ----------------------------------------------------------
        if not document.file or not document.file.storage.exists(document.file.name):
            raise ProcessingError("PDF file is missing from storage.")
        pdf = open_pdf(document.file.path)
        document.set_progress(15)

        try:
            metadata_title = read_metadata_title(pdf)
            if metadata_title and document.title == document.original_filename.rsplit(".", 1)[0]:
                document.title = metadata_title
            document.page_count = pdf.page_count
            document.save(update_fields=["title", "page_count", "updated_at"])

            # -- extract --------------------------------------------------
            document.set_progress(20)
            page_texts: list[PageText] = []
            batch: list[DocumentPage] = []
            pages_with_text = 0
            for extracted in iter_pages(pdf):
                batch.append(
                    DocumentPage(
                        document=document,
                        page_number=extracted.page_number,
                        text=extracted.text,
                        has_text=extracted.has_text,
                    )
                )
                if extracted.has_text:
                    pages_with_text += 1
                    page_texts.append(PageText(page_number=extracted.page_number, text=extracted.text))
                if len(batch) >= PAGE_BATCH:
                    DocumentPage.objects.bulk_create(batch)
                    batch = []
                    progress = 20 + int(30 * extracted.page_number / max(1, pdf.page_count))
                    document.set_progress(min(progress, 49))
            if batch:
                DocumentPage.objects.bulk_create(batch)
        finally:
            pdf.close()

        if pages_with_text == 0:
            raise ProcessingError("No extractable text found in the PDF (scanned images are not supported).")

        # -- chunk ---------------------------------------------------------
        document.set_progress(50)
        chunks = chunk_pages(page_texts, chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
        if not chunks:
            raise ProcessingError("Text could not be split into chunks.")

        chunk_rows: list[DocumentChunk] = []
        for chunk in chunks:
            chunk_rows.append(
                DocumentChunk(
                    document=document,
                    chunk_index=chunk.chunk_index,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    text=chunk.text,
                    qdrant_point_id=new_point_id(),
                )
            )
        with transaction.atomic():
            for start in range(0, len(chunk_rows), CHUNK_BATCH):
                DocumentChunk.objects.bulk_create(chunk_rows[start : start + CHUNK_BATCH])
        # bulk_create on MySQL does not populate ids reliably -> reload.
        stored = list(DocumentChunk.objects.filter(document=document).order_by("chunk_index"))

        # -- embed + upload ------------------------------------------------
        document.set_progress(60)
        embedder = get_embedding_provider()
        store = get_qdrant_service()
        store.create_collection_if_not_exists(embedder.dimension)

        batch_size = max(1, settings.EMBEDDING_BATCH_SIZE)
        total = len(stored)
        for start in range(0, total, batch_size):
            batch_chunks = stored[start : start + batch_size]
            vectors = embedder.embed_documents([c.text for c in batch_chunks])
            store.upsert_chunks(
                ChunkVector(
                    point_id=c.qdrant_point_id,
                    vector=v,
                    chunk_id=c.id,
                    document_id=document.id,
                    user_id=document.user_id,
                    page_start=c.page_start,
                    page_end=c.page_end,
                )
                for c, v in zip(batch_chunks, vectors)
            )
            done = min(total, start + batch_size)
            document.set_progress(60 + int(30 * done / total))

        document.set_progress(90)

        # -- done ----------------------------------------------------------
        document.processing_error = ""
        document.set_progress(100, Document.Status.READY)
        logger.info(
            "Document %s READY: %s pages (%s with text), %s chunks",
            document.id,
            document.page_count,
            pages_with_text,
            total,
        )
    except (ProcessingError, PdfExtractionError) as exc:
        logger.warning("Document %s failed: %s", document.id, exc)
        document.mark_failed(str(exc))
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Document %s failed unexpectedly", document.id)
        document.mark_failed(f"{exc.__class__.__name__}: {exc}")
        raise
