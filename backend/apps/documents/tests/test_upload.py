from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.documents.models import Document

from .utils import TempMediaMixin, make_pdf_bytes, make_upload

User = get_user_model()


@mock.patch("apps.documents.views.process_document.delay")
class DocumentUploadTests(TempMediaMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="Str0ngPassw0rd!")
        self.client.force_authenticate(self.user)
        self.url = reverse("documents:document-list")

    def test_upload_valid_pdf_creates_uploaded_document_and_enqueues_task(self, delay):
        upload = make_upload("skin.pdf", pages=["Vitiligo page one.", "Second page."])
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["status"], Document.Status.UPLOADED)
        self.assertEqual(response.data["page_count"], 2)
        self.assertEqual(response.data["original_filename"], "skin.pdf")
        self.assertEqual(response.data["title"], "skin")
        self.assertEqual(len(response.data["sha256"]), 64)

        document = Document.objects.get(pk=response.data["id"])
        self.assertEqual(document.user, self.user)
        self.assertTrue(document.file.name.startswith(f"documents/{self.user.id}/"))
        self.assertTrue(document.file.storage.exists(document.file.name))
        delay.assert_called_once_with(document.id)

    def test_title_from_pdf_metadata(self, delay):
        data = make_pdf_bytes(["Some text"], title="Andrews' Diseases of the Skin")
        response = self.client.post(self.url, {"file": make_upload("x.pdf", data=data)}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Andrews' Diseases of the Skin")

    def test_rejects_non_pdf_extension(self, delay):
        upload = make_upload("notes.txt")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        delay.assert_not_called()

    def test_rejects_wrong_mime_type(self, delay):
        upload = make_upload("book.pdf", content_type="image/png")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_corrupted_pdf(self, delay):
        upload = make_upload("broken.pdf", data=b"%PDF-1.7 this is not really a pdf body")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 0)

    def test_rejects_bad_signature(self, delay):
        upload = make_upload("fake.pdf", data=b"GIF89a....")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_empty_file(self, delay):
        upload = make_upload("empty.pdf", data=b"")
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_pdf_without_pages(self, delay):
        import pymupdf as fitz

        pdf = fitz.open()
        data = pdf.tobytes() if pdf.page_count else b"%PDF-1.4\n%%EOF\n"
        pdf.close()
        upload = make_upload("nopages.pdf", data=data)
        response = self.client.post(self.url, {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_oversized_file(self, delay):
        with self.settings(MAX_PDF_SIZE_MB=0):
            response = self.client.post(self.url, {"file": make_upload()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_duplicate_for_same_user(self, delay):
        data = make_pdf_bytes(["same content"])
        first = self.client.post(self.url, {"file": make_upload("a.pdf", data=data)}, format="multipart")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(self.url, {"file": make_upload("b.pdf", data=data)}, format="multipart")
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", second.data)

    def test_same_pdf_allowed_for_different_users(self, delay):
        data = make_pdf_bytes(["same content"])
        self.client.post(self.url, {"file": make_upload("a.pdf", data=data)}, format="multipart")
        other = User.objects.create_user(username="bob", email="bob@example.com", password="Str0ngPassw0rd!")
        self.client.force_authenticate(other)
        response = self.client.post(self.url, {"file": make_upload("a.pdf", data=data)}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_requires_authentication(self, delay):
        self.client.force_authenticate(None)
        response = self.client.post(self.url, {"file": make_upload()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DocumentOwnershipTests(TempMediaMixin, APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="alice@example.com", password="Str0ngPassw0rd!")
        self.bob = User.objects.create_user(username="bob", email="bob@example.com", password="Str0ngPassw0rd!")
        self.alice_doc = Document.objects.create(
            user=self.alice, title="Alice's book", original_filename="a.pdf", sha256="a" * 64
        )
        self.bob_doc = Document.objects.create(user=self.bob, title="Bob's book", original_filename="b.pdf", sha256="b" * 64)

    def test_list_only_shows_own_documents(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(reverse("documents:document-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [d["id"] for d in response.data["results"]]
        self.assertEqual(ids, [self.alice_doc.id])

    def test_cannot_retrieve_other_users_document(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(reverse("documents:document-detail", args=[self.bob_doc.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_other_users_document(self):
        self.client.force_authenticate(self.alice)
        with mock.patch("apps.documents.services.deletion.get_qdrant_service") as qs:
            response = self.client.delete(reverse("documents:document-detail", args=[self.bob_doc.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Document.objects.filter(pk=self.bob_doc.id).exists())
        qs.return_value.delete_document_vectors.assert_not_called()

    def test_retrieve_own_document(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(reverse("documents:document-detail", args=[self.alice_doc.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Alice's book")
