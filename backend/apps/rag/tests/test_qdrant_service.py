from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from qdrant_client.http import models as qm

from apps.rag.services.qdrant_service import ChunkVector, QdrantService, VectorStoreError


def _hit(point_id, score, payload):
    return SimpleNamespace(id=point_id, score=score, payload=payload)


class QdrantServiceTests(SimpleTestCase):
    def setUp(self):
        self.client = mock.MagicMock()
        self.service = QdrantService(client=self.client, collection="test_chunks")

    def test_create_collection_when_missing(self):
        self.client.collection_exists.return_value = False
        self.service.create_collection_if_not_exists(768)
        _, kwargs = self.client.create_collection.call_args
        self.assertEqual(kwargs["collection_name"], "test_chunks")
        self.assertEqual(kwargs["vectors_config"].size, 768)
        self.assertEqual(kwargs["vectors_config"].distance, qm.Distance.COSINE)
        self.assertEqual(self.client.create_payload_index.call_count, 3)

    def test_existing_collection_with_matching_size_is_kept(self):
        self.client.collection_exists.return_value = True
        self.client.get_collection.return_value = SimpleNamespace(
            config=SimpleNamespace(params=SimpleNamespace(vectors=qm.VectorParams(size=768, distance=qm.Distance.COSINE)))
        )
        self.service.create_collection_if_not_exists(768)
        self.client.create_collection.assert_not_called()

    def test_existing_collection_with_wrong_size_raises(self):
        self.client.collection_exists.return_value = True
        self.client.get_collection.return_value = SimpleNamespace(
            config=SimpleNamespace(params=SimpleNamespace(vectors=qm.VectorParams(size=384, distance=qm.Distance.COSINE)))
        )
        with self.assertRaises(VectorStoreError):
            self.service.create_collection_if_not_exists(768)

    def test_upsert_builds_payload(self):
        chunk = ChunkVector(
            point_id="11111111-1111-1111-1111-111111111111",
            vector=[0.1, 0.2],
            chunk_id=123,
            document_id=10,
            user_id=5,
            page_start=341,
            page_end=342,
        )
        self.service.upsert_chunk(chunk)
        _, kwargs = self.client.upsert.call_args
        point = kwargs["points"][0]
        self.assertEqual(point.payload, {"chunk_id": 123, "document_id": 10, "user_id": 5, "page_start": 341, "page_end": 342})
        self.assertEqual(point.vector, [0.1, 0.2])

    def test_search_filters_by_document_and_parses_hits(self):
        self.client.query_points.return_value = SimpleNamespace(
            points=[
                _hit("a", 0.91, {"chunk_id": 1, "document_id": 10, "page_start": 3, "page_end": 3}),
                _hit("b", 0.70, {"chunk_id": 2, "document_id": 99, "page_start": 1, "page_end": 1}),  # foreign doc
            ]
        )
        hits = self.service.search([0.1, 0.2], document_id=10, top_k=6, score_threshold=0.65)
        _, kwargs = self.client.query_points.call_args
        condition = kwargs["query_filter"].must[0]
        self.assertEqual(condition.key, "document_id")
        self.assertEqual(condition.match.value, 10)
        self.assertEqual(kwargs["limit"], 6)
        self.assertEqual(kwargs["score_threshold"], 0.65)
        self.assertEqual([h.chunk_id for h in hits], [1])
        self.assertAlmostEqual(hits[0].score, 0.91)

    def test_delete_document_vectors_uses_filter_selector(self):
        self.client.collection_exists.return_value = True
        self.service.delete_document_vectors(10)
        _, kwargs = self.client.delete.call_args
        selector = kwargs["points_selector"]
        self.assertIsInstance(selector, qm.FilterSelector)
        self.assertEqual(selector.filter.must[0].match.value, 10)

    def test_client_errors_are_wrapped(self):
        self.client.query_points.side_effect = RuntimeError("connection refused")
        with self.assertRaises(VectorStoreError):
            self.service.search([0.1], document_id=1, top_k=1)
        self.client.upsert.side_effect = RuntimeError("boom")
        with self.assertRaises(VectorStoreError):
            self.service.upsert_chunks(
                [ChunkVector("11111111-1111-1111-1111-111111111111", [0.1], 1, 1, 1, 1, 1)]
            )
