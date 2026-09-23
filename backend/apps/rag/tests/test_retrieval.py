from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.documents.models import Document, DocumentChunk
from apps.rag.services.qdrant_service import ChunkVector, new_point_id
from apps.rag.services.retrieval import build_retrieval_queries, make_excerpt, retrieve

from .fakes import FakeEmbeddingProvider, InMemoryQdrant

User = get_user_model()


def index_document(document: Document, qdrant: InMemoryQdrant, embedder: FakeEmbeddingProvider, texts: list[str]):
    chunks = []
    for index, text in enumerate(texts):
        chunk = DocumentChunk.objects.create(
            document=document,
            chunk_index=index,
            page_start=index + 1,
            page_end=index + 1,
            text=text,
            qdrant_point_id=new_point_id(),
        )
        chunks.append(chunk)
    vectors = embedder.embed_documents([c.text for c in chunks])
    qdrant.upsert_chunks(
        ChunkVector(c.qdrant_point_id, v, c.id, document.id, document.user_id, c.page_start, c.page_end)
        for c, v in zip(chunks, vectors)
    )
    return chunks


@override_settings(RAG_TOP_K=6, RAG_SIMILARITY_THRESHOLD=0.3)
class RetrievalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", email="u@example.com", password="Str0ngPassw0rd!")
        self.doc_a = Document.objects.create(
            user=self.user, title="Skin Book", original_filename="a.pdf", sha256="a" * 64, status=Document.Status.READY
        )
        self.doc_b = Document.objects.create(
            user=self.user, title="Other Book", original_filename="b.pdf", sha256="b" * 64, status=Document.Status.READY
        )
        self.embedder = FakeEmbeddingProvider()
        self.qdrant = InMemoryQdrant()
        self.patches = [
            mock.patch("apps.rag.services.retrieval.get_embedding_provider", return_value=self.embedder),
            mock.patch("apps.rag.services.retrieval.get_qdrant_service", return_value=self.qdrant),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

        index_document(
            self.doc_a,
            self.qdrant,
            self.embedder,
            [
                "Vitiligo is a chronic skin disorder that causes loss of pigment in patches.",
                "Psoriasis is an immune mediated disease with scaly plaques.",
                "Treatment of vitiligo includes topical corticosteroids and phototherapy.",
            ],
        )
        index_document(self.doc_b, self.qdrant, self.embedder, ["Vitiligo vitiligo vitiligo pigment patches skin disorder."])

    def test_returns_relevant_chunks_only_from_selected_document(self):
        results = retrieve(self.doc_a, "What is vitiligo skin disorder pigment?")
        self.assertTrue(results)
        self.assertTrue(all(r.chunk.document_id == self.doc_a.id for r in results))
        self.assertIn("Vitiligo is a chronic", results[0].chunk.text)
        self.assertGreaterEqual(results[0].score, results[-1].score)

    def test_empty_when_nothing_above_threshold(self):
        results = retrieve(self.doc_a, "quantum chromodynamics gluon lattice", threshold=0.9)
        self.assertEqual(results, [])

    def test_follow_up_uses_previous_question(self):
        results = retrieve(self.doc_a, "treatment?", previous_user_question="What is vitiligo?")
        self.assertEqual(self.embedder.query_calls[-2:], ["treatment?", "What is vitiligo? treatment?"])
        self.assertTrue(any("Treatment of vitiligo" in r.chunk.text for r in results))

    def test_source_dict_shape(self):
        results = retrieve(self.doc_a, "vitiligo pigment")
        source = results[0].to_source()
        self.assertEqual(set(source), {"chunk_id", "page_start", "page_end", "score", "excerpt"})

    def test_missing_mysql_chunk_is_skipped(self):
        DocumentChunk.objects.filter(document=self.doc_a).delete()  # vectors remain in the fake store
        self.assertEqual(retrieve(self.doc_a, "vitiligo pigment"), [])


class HelperTests(TestCase):
    def test_build_retrieval_queries(self):
        self.assertEqual(build_retrieval_queries("Uni davolash qanday?", None), ["Uni davolash qanday?"])
        self.assertEqual(
            build_retrieval_queries("Uni davolash qanday?", "Vitiligo nima?"),
            ["Uni davolash qanday?", "Vitiligo nima? Uni davolash qanday?"],
        )

    def test_make_excerpt_truncates_on_word_boundary(self):
        text = "word " * 200
        excerpt = make_excerpt(text, limit=50)
        self.assertLessEqual(len(excerpt), 52)
        self.assertTrue(excerpt.endswith("…"))
        self.assertEqual(make_excerpt("short text"), "short text")
