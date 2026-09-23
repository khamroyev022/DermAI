"""
Test doubles shared across apps.

- FakeEmbeddingProvider: deterministic, cheap, no model download.
- InMemoryQdrant: exact cosine search over an in-memory dict, honours the
  document_id filter and score_threshold like the real service.
- FakeLLM: records calls and returns a canned answer.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Sequence

_WORD = re.compile(r"[\w']+", re.UNICODE)

from apps.rag.services.embeddings import EmbeddingProvider
from apps.rag.services.llm.base import LLMMessage, LLMProvider
from apps.rag.services.qdrant_service import ChunkVector, SearchHit

DIM = 16


def _text_vector(text: str, dim: int = DIM) -> list[float]:
    """Bag-of-words hashed into `dim` buckets, L2-normalised. Similar texts -> similar vectors."""
    vec = [0.0] * dim
    for word in _WORD.findall(text.lower().replace("query:", "").replace("passage:", "")):
        bucket = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % dim
        vec[bucket] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class FakeEmbeddingProvider(EmbeddingProvider):
    model_name = "fake"

    def __init__(self, dim: int = DIM):
        self._dim = dim
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [_text_vector(t, self._dim) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return _text_vector(text, self._dim)


class InMemoryQdrant:
    """Drop-in replacement for QdrantService used in tests."""

    def __init__(self):
        self.points: dict[str, ChunkVector] = {}
        self.collection_size: int | None = None
        self.deleted_documents: list[int] = []

    def create_collection_if_not_exists(self, vector_size: int) -> None:
        if self.collection_size is None:
            self.collection_size = vector_size

    def upsert_chunk(self, chunk: ChunkVector) -> None:
        self.points[chunk.point_id] = chunk

    def upsert_chunks(self, chunks, batch_size: int = 128) -> int:
        count = 0
        for chunk in chunks:
            self.upsert_chunk(chunk)
            count += 1
        return count

    def delete_document_vectors(self, document_id: int) -> None:
        self.deleted_documents.append(document_id)
        self.points = {k: v for k, v in self.points.items() if v.document_id != document_id}

    def search(self, query_vector, document_id: int, top_k: int, score_threshold: float | None = None):
        hits: list[SearchHit] = []
        for point in self.points.values():
            if point.document_id != document_id:
                continue
            score = sum(a * b for a, b in zip(query_vector, point.vector))
            if score_threshold is not None and score < score_threshold:
                continue
            hits.append(
                SearchHit(
                    chunk_id=point.chunk_id,
                    score=score,
                    page_start=point.page_start,
                    page_end=point.page_end,
                    point_id=point.point_id,
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    def count_document_vectors(self, document_id: int) -> int:
        return sum(1 for p in self.points.values() if p.document_id == document_id)


class FakeLLM(LLMProvider):
    name = "fake"

    def __init__(self, answer: str = "Fake grounded answer."):
        self.answer = answer
        self.calls: list[tuple[str, list[LLMMessage]]] = []

    def generate(self, system_prompt: str, messages: Sequence[LLMMessage]) -> str:
        self.calls.append((system_prompt, list(messages)))
        return self.answer
