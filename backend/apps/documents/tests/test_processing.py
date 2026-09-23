from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from apps.documents.models import Document, DocumentChunk, DocumentPage
from apps.documents.services.processing import process_document
from apps.documents.tasks import process_document as process_document_task
from apps.rag.tests.fakes import FakeEmbeddingProvider, InMemoryQdrant

from .utils import TempMediaMixin, make_pdf_bytes

User = get_user_model()


@override_settings(CHUNK_SIZE=120, CHUNK_OVERLAP=30, EMBEDDING_BATCH_SIZE=1)
class ProcessingTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="Str0ngPassw0rd!")
        self.embedder = FakeEmbeddingProvider()
        self.qdrant = InMemoryQdrant()
        for target in (
            "apps.documents.services.processing.get_embedding_provider",
            "apps.rag.services.retrieval.get_embedding_provider",
        ):
            p = mock.patch(target, return_value=self.embedder)
            p.start()
            self.addCleanup(p.stop)
        for target in (
            "apps.documents.services.processing.get_qdrant_service",
            "apps.rag.services.retrieval.get_qdrant_service",
        ):
            p = mock.patch(target, return_value=self.qdrant)
            p.start()
            self.addCleanup(p.stop)

    def _create_document(self, pages, title=None, filename="book.pdf"):
        data = make_pdf_bytes(pages, title=title)
        document = Document(
            user=self.user,
            title=filename.rsplit(".", 1)[0],
            original_filename=filename,
            sha256="c" * 64,
            file_size=len(data),
            page_count=len(pages),
        )
        document.file.save(filename, ContentFile(data), save=True)
        return document

    def test_full_pipeline_marks_ready(self):
        document = self._create_document(
            [
                "Vitiligo is a chronic skin disorder that causes loss of pigment. It appears as white patches.",
                "Treatment of vitiligo includes topical corticosteroids and phototherapy sessions.",
                "",  # page without text
            ],
            title="Andrews' Diseases of the Skin",
        )
        process_document(document.id)
        document.refresh_from_db()

        self.assertEqual(document.status, Document.Status.READY)
        self.assertEqual(document.processing_progress, 100)
        self.assertEqual(document.processing_error, "")
        self.assertEqual(document.page_count, 3)
        self.assertEqual(document.title, "Andrews' Diseases of the Skin")

        pages = list(DocumentPage.objects.filter(document=document).order_by("page_number"))
        self.assertEqual([p.page_number for p in pages], [1, 2, 3])
        self.assertEqual([p.has_text for p in pages], [True, True, False])
        self.assertIn("Vitiligo", pages[0].text)

        chunks = list(DocumentChunk.objects.filter(document=document).order_by("chunk_index"))
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(c.qdrant_point_id for c in chunks))
        self.assertEqual(chunks[0].page_start, 1)
        self.assertEqual(chunks[-1].page_end, 2)

        # Every chunk has exactly one vector in Qdrant with the right payload.
        self.assertEqual(self.qdrant.count_document_vectors(document.id), len(chunks))
        self.assertEqual(self.qdrant.collection_size, self.embedder.dimension)
        point = self.qdrant.points[chunks[0].qdrant_point_id]
        self.assertEqual(point.chunk_id, chunks[0].id)
        self.assertEqual(point.user_id, self.user.id)
        self.assertEqual((point.page_start, point.page_end), (chunks[0].page_start, chunks[0].page_end))
        # Batch size 1 -> one embedding call per chunk.
        self.assertGreater(len(self.embedder.document_calls), 1)

    def test_pdf_without_text_fails(self):
        document = self._create_document(["", ""])
        with self.assertRaises(Exception):
            process_document(document.id)
        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.FAILED)
        self.assertIn("No extractable text", document.processing_error)
        self.assertEqual(DocumentChunk.objects.filter(document=document).count(), 0)

    def test_missing_file_fails(self):
        document = self._create_document(["Some text here for the page."])
        document.file.storage.delete(document.file.name)
        with self.assertRaises(Exception):
            process_document(document.id)
        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.FAILED)
        self.assertIn("missing", document.processing_error)

    def test_reprocessing_is_idempotent(self):
        document = self._create_document(["Vitiligo is a chronic skin disorder that causes loss of pigment."])
        process_document(document.id)
        first_chunks = DocumentChunk.objects.filter(document=document).count()
        process_document(document.id)
        self.assertEqual(DocumentChunk.objects.filter(document=document).count(), first_chunks)
        self.assertEqual(DocumentPage.objects.filter(document=document).count(), 1)
        self.assertEqual(self.qdrant.count_document_vectors(document.id), first_chunks)

    def test_celery_task_swallows_failure_and_reports_status(self):
        document = self._create_document(["", ""])
        result = process_document_task.apply(args=(document.id,)).get()
        self.assertEqual(result["status"], "FAILED")
        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.FAILED)

    def test_celery_task_success(self):
        document = self._create_document(["Vitiligo is a chronic skin disorder that causes loss of pigment."])
        result = process_document_task.apply(args=(document.id,)).get()
        self.assertEqual(result["status"], "READY")

    def test_celery_task_missing_document(self):
        result = process_document_task.apply(args=(999999,)).get()
        self.assertEqual(result["status"], "missing")
