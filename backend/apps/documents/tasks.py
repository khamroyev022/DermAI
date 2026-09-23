import logging

from celery import shared_task

from .models import Document
from .services.processing import process_document as run_processing

logger = logging.getLogger(__name__)


@shared_task(
    name="documents.process_document",
    bind=True,
    autoretry_for=(),
    max_retries=0,
    soft_time_limit=60 * 60,
    time_limit=60 * 60 + 60,
)
def process_document(self, document_id: int) -> dict:
    """Extract, chunk, embed and index a document. Sets FAILED + error on any failure."""
    try:
        run_processing(document_id)
    except Document.DoesNotExist:
        logger.warning("process_document: document %s no longer exists", document_id)
        return {"document_id": document_id, "status": "missing"}
    except Exception as exc:  # noqa: BLE001 — status already set to FAILED in the service
        return {"document_id": document_id, "status": "FAILED", "error": str(exc)[:500]}
    return {"document_id": document_id, "status": "READY"}
