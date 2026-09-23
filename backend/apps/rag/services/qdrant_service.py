"""
Qdrant vector store service.

Qdrant holds ONLY embeddings + a small payload (chunk_id, document_id, user_id,
page_start, page_end). All text/metadata lives in MySQL and is joined back by
`chunk_id`. Every search is filtered by `document_id`, so chunks from other
books can never leak into a conversation.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

logger = logging.getLogger(__name__)


class VectorStoreError(Exception):
    """Raised when Qdrant is unreachable or returns an error."""


@dataclass(frozen=True)
class ChunkVector:
    point_id: str
    vector: list[float]
    chunk_id: int
    document_id: int
    user_id: int
    page_start: int
    page_end: int

    def to_point(self) -> qm.PointStruct:
        return qm.PointStruct(
            id=self.point_id,
            vector=self.vector,
            payload={
                "chunk_id": self.chunk_id,
                "document_id": self.document_id,
                "user_id": self.user_id,
                "page_start": self.page_start,
                "page_end": self.page_end,
            },
        )


@dataclass(frozen=True)
class SearchHit:
    chunk_id: int
    score: float
    page_start: int
    page_end: int
    point_id: str


def new_point_id() -> str:
    return str(uuid.uuid4())


class QdrantService:
    def __init__(self, client: QdrantClient | None = None, collection: str | None = None):
        self._client = client
        self.collection = collection or settings.QDRANT_COLLECTION

    # -- client ------------------------------------------------------------

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=30,
            )
        return self._client

    # -- collection --------------------------------------------------------

    def create_collection_if_not_exists(self, vector_size: int) -> None:
        """Create the collection sized to the embedding model, plus payload indexes."""
        try:
            if self.client.collection_exists(self.collection):
                info = self.client.get_collection(self.collection)
                existing = info.config.params.vectors
                existing_size = existing.size if isinstance(existing, qm.VectorParams) else None
                if existing_size is not None and existing_size != vector_size:
                    raise VectorStoreError(
                        f"Qdrant collection '{self.collection}' has vector size {existing_size}, "
                        f"but the embedding model produces {vector_size}. "
                        "Change QDRANT_COLLECTION or recreate the collection."
                    )
                return
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
            )
            for field in ("document_id", "user_id", "chunk_id"):
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field,
                    field_schema=qm.PayloadSchemaType.INTEGER,
                )
            logger.info("Created Qdrant collection %s (size=%s, cosine)", self.collection, vector_size)
        except VectorStoreError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Could not ensure Qdrant collection: {exc}") from exc

    # -- writes ------------------------------------------------------------

    def upsert_chunk(self, chunk: ChunkVector) -> None:
        self.upsert_chunks([chunk])

    def upsert_chunks(self, chunks: Iterable[ChunkVector], batch_size: int = 128) -> int:
        points = [c.to_point() for c in chunks]
        try:
            for start in range(0, len(points), batch_size):
                self.client.upsert(
                    collection_name=self.collection,
                    points=points[start : start + batch_size],
                    wait=True,
                )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Qdrant upsert failed: {exc}") from exc
        return len(points)

    def delete_document_vectors(self, document_id: int) -> None:
        """Delete every point whose payload.document_id matches."""
        try:
            if not self.client.collection_exists(self.collection):
                return
            self.client.delete(
                collection_name=self.collection,
                points_selector=qm.FilterSelector(filter=_document_filter(document_id)),
                wait=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Qdrant delete failed for document {document_id}: {exc}") from exc

    # -- reads -------------------------------------------------------------

    def search(
        self,
        query_vector: Sequence[float],
        document_id: int,
        top_k: int,
        score_threshold: float | None = None,
    ) -> list[SearchHit]:
        """Cosine similarity search restricted to ONE document."""
        try:
            response = self.client.query_points(
                collection_name=self.collection,
                query=list(query_vector),
                query_filter=_document_filter(document_id),
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Qdrant search failed: {exc}") from exc

        hits: list[SearchHit] = []
        for point in response.points:
            payload = point.payload or {}
            if int(payload.get("document_id", -1)) != int(document_id):
                continue  # defensive: never return another document's chunk
            hits.append(
                SearchHit(
                    chunk_id=int(payload["chunk_id"]),
                    score=float(point.score),
                    page_start=int(payload.get("page_start", 0)),
                    page_end=int(payload.get("page_end", 0)),
                    point_id=str(point.id),
                )
            )
        return hits

    def count_document_vectors(self, document_id: int) -> int:
        try:
            result = self.client.count(
                collection_name=self.collection,
                count_filter=_document_filter(document_id),
                exact=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(f"Qdrant count failed: {exc}") from exc
        return int(result.count)


def _document_filter(document_id: int) -> qm.Filter:
    return qm.Filter(must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=int(document_id)))])


@lru_cache(maxsize=1)
def get_qdrant_service() -> QdrantService:
    return QdrantService()


# Module-level convenience functions (thin wrappers around the singleton).


def create_collection_if_not_exists(vector_size: int) -> None:
    get_qdrant_service().create_collection_if_not_exists(vector_size)


def upsert_chunk(chunk: ChunkVector) -> None:
    get_qdrant_service().upsert_chunk(chunk)


def search(query_vector: Sequence[float], document_id: int, top_k: int, score_threshold: float | None = None):
    return get_qdrant_service().search(query_vector, document_id, top_k, score_threshold)


def delete_document_vectors(document_id: int) -> None:
    get_qdrant_service().delete_document_vectors(document_id)
