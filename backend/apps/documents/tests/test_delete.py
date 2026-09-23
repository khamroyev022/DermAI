from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chats.models import ChatMessage, ChatSession
from apps.documents.models import Document, DocumentChunk, DocumentPage
from apps.rag.services.qdrant_service import ChunkVector, VectorStoreError, new_point_id
from apps.rag.tests.fakes import InMemoryQdrant

from .utils import TempMediaMixin, make_pdf_bytes

User = get_user_model()


class DeleteDocumentTests(TempMediaMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="Str0ngPassw0rd!")
        self.client.force_authenticate(self.user)
        self.qdrant = InMemoryQdrant()
        patcher = mock.patch("apps.documents.services.deletion.get_qdrant_service", return_value=self.qdrant)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.document = Document(
            user=self.user, title="Book", original_filename="book.pdf", sha256="d" * 64, status=Document.Status.READY
        )
        self.document.file.save("book.pdf", ContentFile(make_pdf_bytes(["hello"])), save=True)
        self.file_name = self.document.file.name

        DocumentPage.objects.create(document=self.document, page_number=1, text="hello", has_text=True)
        chunk = DocumentChunk.objects.create(
            document=self.document, chunk_index=0, page_start=1, page_end=1, text="hello", qdrant_point_id=new_point_id()
        )
        self.qdrant.upsert_chunk(ChunkVector(chunk.qdrant_point_id, [1.0], chunk.id, self.document.id, self.user.id, 1, 1))

        chat = ChatSession.objects.create(user=self.user, document=self.document, title="chat")
        ChatMessage.objects.create(chat=chat, role=ChatMessage.Role.USER, content="hi")
        ChatMessage.objects.create(chat=chat, role=ChatMessage.Role.ASSISTANT, content="hello", sources=[])

        # Another document that must survive.
        self.other = Document.objects.create(user=self.user, title="Other", original_filename="o.pdf", sha256="e" * 64)
        self.qdrant.upsert_chunk(ChunkVector(new_point_id(), [1.0], 999, self.other.id, self.user.id, 1, 1))

    def test_delete_removes_everything(self):
        url = reverse("documents:document-detail", args=[self.document.id])
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Document.objects.filter(pk=self.document.id).exists())
        self.assertEqual(DocumentPage.objects.filter(document_id=self.document.id).count(), 0)
        self.assertEqual(DocumentChunk.objects.filter(document_id=self.document.id).count(), 0)
        self.assertEqual(ChatSession.objects.filter(document_id=self.document.id).count(), 0)
        self.assertEqual(ChatMessage.objects.filter(chat__document_id=self.document.id).count(), 0)
        self.assertEqual(self.qdrant.count_document_vectors(self.document.id), 0)
        self.assertIn(self.document.id, self.qdrant.deleted_documents)
        self.assertFalse(Document._meta.get_field("file").storage.exists(self.file_name))

        # Unrelated data untouched.
        self.assertTrue(Document.objects.filter(pk=self.other.id).exists())
        self.assertEqual(self.qdrant.count_document_vectors(self.other.id), 1)

    def test_delete_aborts_when_vector_store_is_down(self):
        with mock.patch.object(self.qdrant, "delete_document_vectors", side_effect=VectorStoreError("down")):
            response = self.client.delete(reverse("documents:document-detail", args=[self.document.id]))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertTrue(Document.objects.filter(pk=self.document.id).exists())
        self.assertEqual(DocumentChunk.objects.filter(document_id=self.document.id).count(), 1)
