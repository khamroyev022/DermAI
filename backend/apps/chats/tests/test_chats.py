from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chats.models import ChatMessage, ChatSession
from apps.documents.models import Document, DocumentChunk
from apps.rag.services.llm.base import LLMError
from apps.rag.services.qdrant_service import ChunkVector, VectorStoreError, new_point_id
from apps.rag.tests.fakes import FakeEmbeddingProvider, FakeLLM, InMemoryQdrant

User = get_user_model()


def index_chunks(document, qdrant, embedder, texts):
    chunks = []
    for index, text in enumerate(texts):
        chunks.append(
            DocumentChunk.objects.create(
                document=document,
                chunk_index=index,
                page_start=340 + index,
                page_end=340 + index,
                text=text,
                qdrant_point_id=new_point_id(),
            )
        )
    vectors = embedder.embed_documents([c.text for c in chunks])
    qdrant.upsert_chunks(
        ChunkVector(c.qdrant_point_id, v, c.id, document.id, document.user_id, c.page_start, c.page_end)
        for c, v in zip(chunks, vectors)
    )
    return chunks


@override_settings(RAG_TOP_K=6, RAG_SIMILARITY_THRESHOLD=0.3, CHAT_HISTORY_MESSAGES=6)
class ChatApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="Str0ngPassw0rd!")
        self.other = User.objects.create_user(username="bob", email="bob@example.com", password="Str0ngPassw0rd!")
        self.client.force_authenticate(self.user)

        self.document = Document.objects.create(
            user=self.user,
            title="Andrews' Diseases of the Skin",
            original_filename="andrews.pdf",
            sha256="a" * 64,
            status=Document.Status.READY,
            page_count=900,
        )
        self.not_ready = Document.objects.create(
            user=self.user, title="Pending", original_filename="p.pdf", sha256="b" * 64, status=Document.Status.PROCESSING
        )
        self.other_doc = Document.objects.create(
            user=self.other, title="Bob's", original_filename="bob.pdf", sha256="c" * 64, status=Document.Status.READY
        )

        self.embedder = FakeEmbeddingProvider()
        self.qdrant = InMemoryQdrant()
        self.llm = FakeLLM(answer="Vitiligo is an acquired loss of pigment.")
        for target, value in (
            ("apps.rag.services.retrieval.get_embedding_provider", self.embedder),
            ("apps.rag.services.retrieval.get_qdrant_service", self.qdrant),
            ("apps.chats.services.chat_service.get_llm_provider", self.llm),
        ):
            p = mock.patch(target, return_value=value)
            p.start()
            self.addCleanup(p.stop)

        self.chunks = index_chunks(
            self.document,
            self.qdrant,
            self.embedder,
            [
                "Vitiligo is an acquired disorder with loss of pigment in patches of skin.",
                "Treatment of vitiligo includes corticosteroids and narrowband UVB phototherapy.",
            ],
        )
        index_chunks(self.other_doc, self.qdrant, self.embedder, ["Vitiligo vitiligo pigment patches skin from Bob's book."])

    # -- sessions ------------------------------------------------------------

    def test_create_chat_for_ready_document(self):
        response = self.client.post(reverse("chats:chat-list"), {"document_id": self.document.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["document"]["id"], self.document.id)
        self.assertEqual(response.data["title"], self.document.title)
        self.assertEqual(ChatSession.objects.filter(user=self.user).count(), 1)

    def test_create_chat_rejects_document_not_ready(self):
        response = self.client.post(reverse("chats:chat-list"), {"document_id": self.not_ready.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_chat_rejects_other_users_document(self):
        response = self.client.post(reverse("chats:chat-list"), {"document_id": self.other_doc.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_and_retrieve_and_delete_only_own_chats(self):
        mine = ChatSession.objects.create(user=self.user, document=self.document, title="mine")
        theirs = ChatSession.objects.create(user=self.other, document=self.other_doc, title="theirs")

        listed = self.client.get(reverse("chats:chat-list"))
        self.assertEqual([c["id"] for c in listed.data["results"]], [mine.id])

        self.assertEqual(self.client.get(reverse("chats:chat-detail", args=[theirs.id])).status_code, 404)
        self.assertEqual(self.client.delete(reverse("chats:chat-detail", args=[theirs.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("chats:chat-send-message", args=[theirs.id]), {"message": "hi"}).status_code, 404)

        detail = self.client.get(reverse("chats:chat-detail", args=[mine.id]))
        self.assertEqual(detail.status_code, 200)
        self.assertIn("messages", detail.data)

        self.assertEqual(self.client.delete(reverse("chats:chat-detail", args=[mine.id])).status_code, 204)
        self.assertFalse(ChatSession.objects.filter(pk=mine.id).exists())

    def test_list_filter_by_document(self):
        ChatSession.objects.create(user=self.user, document=self.document, title="a")
        ChatSession.objects.create(user=self.user, document=self.not_ready, title="b")
        response = self.client.get(reverse("chats:chat-list"), {"document": self.document.id})
        self.assertEqual(len(response.data["results"]), 1)

    # -- messages ------------------------------------------------------------

    def _chat(self):
        return ChatSession.objects.create(user=self.user, document=self.document, title=self.document.title)

    def test_send_message_returns_grounded_answer_with_backend_sources(self):
        chat = self._chat()
        url = reverse("chats:chat-send-message", args=[chat.id])
        response = self.client.post(url, {"message": "What is vitiligo pigment patches?"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.assertEqual(response.data["answer"], self.llm.answer)
        self.assertEqual(response.data["document"], {"id": self.document.id, "title": self.document.title, "status": "READY", "page_count": 900})
        sources = response.data["sources"]
        self.assertTrue(sources)
        self.assertEqual(set(sources[0]), {"chunk_id", "page_start", "page_end", "score", "excerpt"})
        self.assertEqual(sources[0]["chunk_id"], self.chunks[0].id)
        self.assertEqual(sources[0]["page_start"], 340)
        # Chunks from Bob's book never appear.
        self.assertTrue(all(s["chunk_id"] in {c.id for c in self.chunks} for s in sources))

        # Persisted messages.
        messages = list(chat.messages.order_by("created_at", "id"))
        self.assertEqual([m.role for m in messages], ["USER", "ASSISTANT"])
        self.assertEqual(messages[1].sources, sources)
        chat.refresh_from_db()
        self.assertEqual(chat.title, "What is vitiligo pigment patches?")

        # The LLM got the system prompt and the document context, not the raw PDF.
        system_prompt, llm_messages = self.llm.calls[0]
        self.assertIn("document-grounded", system_prompt)
        self.assertIn("DOCUMENT CONTEXT", llm_messages[-1].content)
        self.assertIn("SOURCE 1", llm_messages[-1].content)
        self.assertIn(self.document.title, llm_messages[-1].content)

    def test_empty_retrieval_short_circuits_without_llm(self):
        chat = self._chat()
        with override_settings(RAG_SIMILARITY_THRESHOLD=0.99):
            response = self.client.post(
                reverse("chats:chat-send-message", args=[chat.id]), {"message": "quantum gluon lattice"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["answer"], settings.RAG_NOT_FOUND_ANSWER)
        self.assertEqual(response.data["sources"], [])
        self.assertEqual(self.llm.calls, [])
        self.assertEqual(chat.messages.count(), 2)

    def test_follow_up_receives_history_and_previous_question(self):
        chat = self._chat()
        url = reverse("chats:chat-send-message", args=[chat.id])
        self.client.post(url, {"message": "What is vitiligo pigment?"}, format="json")
        response = self.client.post(url, {"message": "How is it treated?"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        _, llm_messages = self.llm.calls[-1]
        roles = [m.role for m in llm_messages]
        self.assertEqual(roles, ["user", "assistant", "user"])
        self.assertIn("What is vitiligo pigment?", llm_messages[0].content)
        # Retrieval used the previous question to disambiguate the follow-up.
        self.assertIn("What is vitiligo pigment? How is it treated?", self.embedder.query_calls)

    def test_history_is_truncated(self):
        chat = self._chat()
        for i in range(10):
            ChatMessage.objects.create(chat=chat, role=ChatMessage.Role.USER, content=f"q{i}")
            ChatMessage.objects.create(chat=chat, role=ChatMessage.Role.ASSISTANT, content=f"a{i}")
        self.client.post(reverse("chats:chat-send-message", args=[chat.id]), {"message": "vitiligo pigment"}, format="json")
        _, llm_messages = self.llm.calls[-1]
        self.assertEqual(len(llm_messages), settings.CHAT_HISTORY_MESSAGES + 1)
        self.assertEqual(llm_messages[0].content, "q7")

    def test_message_rejected_when_document_not_ready(self):
        chat = ChatSession.objects.create(user=self.user, document=self.not_ready, title="x")
        response = self.client.post(reverse("chats:chat-send-message", args=[chat.id]), {"message": "hi"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_blank_message_rejected(self):
        chat = self._chat()
        response = self.client.post(reverse("chats:chat-send-message", args=[chat.id]), {"message": "   "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_llm_failure_returns_502_and_persists_nothing(self):
        chat = self._chat()
        with mock.patch.object(self.llm, "generate", side_effect=LLMError("quota")):
            response = self.client.post(
                reverse("chats:chat-send-message", args=[chat.id]), {"message": "vitiligo pigment"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertNotIn("Traceback", str(response.data))
        self.assertEqual(chat.messages.count(), 0)

    def test_vector_store_failure_returns_503(self):
        chat = self._chat()
        with mock.patch.object(self.qdrant, "search", side_effect=VectorStoreError("down")):
            response = self.client.post(
                reverse("chats:chat-send-message", args=[chat.id]), {"message": "vitiligo"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse("chats:chat-list")).status_code, status.HTTP_401_UNAUTHORIZED)
