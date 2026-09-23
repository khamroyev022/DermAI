"""
Full document deletion:

    1. Qdrant vectors (filter document_id)
    2. ChatMessages
    3. ChatSessions
    4. DocumentChunks
    5. DocumentPages
    6. PDF media file
    7. Document row

If Qdrant is unreachable we abort BEFORE touching MySQL so the user can retry
and no orphan vectors are left behind.
"""

from __future__ import annotations

import logging

from django.db import transaction

from apps.chats.models import ChatMessage, ChatSession
from apps.rag.services.qdrant_service import VectorStoreError, get_qdrant_service

from ..models import Document, DocumentChunk, DocumentPage

logger = logging.getLogger(__name__)


def delete_document(document: Document) -> None:
    document_id = document.id
    get_qdrant_service().delete_document_vectors(document_id)  # may raise VectorStoreError

    file_name = document.file.name if document.file else None
    storage = document.file.storage if document.file else None

    with transaction.atomic():
        ChatMessage.objects.filter(chat__document=document).delete()
        ChatSession.objects.filter(document=document).delete()
        DocumentChunk.objects.filter(document=document).delete()
        DocumentPage.objects.filter(document=document).delete()
        document.delete()

        if file_name and storage:

            def _remove_file():
                try:
                    if storage.exists(file_name):
                        storage.delete(file_name)
                except Exception:  # noqa: BLE001
                    logger.exception("Could not delete media file %s for document %s", file_name, document_id)

            transaction.on_commit(_remove_file)

    logger.info("Deleted document %s and all related data", document_id)


__all__ = ["delete_document", "VectorStoreError"]
