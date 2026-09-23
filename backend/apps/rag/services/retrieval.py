"""
RAG retrieval: question -> embedding -> Qdrant (filtered by document) -> MySQL chunks.

The PDF is never re-read here. Only pre-computed chunks/vectors are used.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from django.conf import settings

from apps.documents.models import Document, DocumentChunk

from .embeddings import get_embedding_provider
from .qdrant_service import SearchHit, get_qdrant_service

logger = logging.getLogger(__name__)

EXCERPT_MAX_CHARS = 500


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    score: float

    def to_source(self) -> dict:
        return {
            "chunk_id": self.chunk.id,
            "page_start": self.chunk.page_start,
            "page_end": self.chunk.page_end,
            "score": round(self.score, 4),
            "excerpt": make_excerpt(self.chunk.text),
        }


def make_excerpt(text: str, limit: int = EXCERPT_MAX_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return f"{cut}…"


def build_retrieval_queries(question: str, previous_user_question: str | None) -> list[str]:
    """
    Follow-up questions ("Uni davolash qanday?") are often meaningless on their
    own, so in addition to the raw question we also search with the previous
    user question prepended. Results are merged by chunk_id (max score).
    """
    queries = [question.strip()]
    if previous_user_question:
        combined = f"{previous_user_question.strip()} {question.strip()}"
        if combined != queries[0]:
            queries.append(combined)
    return queries


def _merge_hits(hit_lists: Sequence[Sequence[SearchHit]]) -> list[SearchHit]:
    best: dict[int, SearchHit] = {}
    for hits in hit_lists:
        for hit in hits:
            current = best.get(hit.chunk_id)
            if current is None or hit.score > current.score:
                best[hit.chunk_id] = hit
    return sorted(best.values(), key=lambda h: h.score, reverse=True)


def retrieve(
    document: Document,
    question: str,
    previous_user_question: str | None = None,
    top_k: int | None = None,
    threshold: float | None = None,
) -> list[RetrievedChunk]:
    """Return relevant chunks of `document` for `question`, best first."""
    top_k = top_k or settings.RAG_TOP_K
    threshold = settings.RAG_SIMILARITY_THRESHOLD if threshold is None else threshold

    embedder = get_embedding_provider()
    store = get_qdrant_service()

    hit_lists = []
    for query in build_retrieval_queries(question, previous_user_question):
        vector = embedder.embed_query(query)
        hit_lists.append(store.search(vector, document_id=document.id, top_k=top_k, score_threshold=threshold))

    hits = [h for h in _merge_hits(hit_lists) if h.score >= threshold][:top_k]
    if not hits:
        logger.info("No chunks above threshold %.2f for document %s", threshold, document.id)
        return []

    chunk_ids = [h.chunk_id for h in hits]
    chunks_by_id = {c.id: c for c in DocumentChunk.objects.filter(document=document, id__in=chunk_ids)}

    results: list[RetrievedChunk] = []
    for hit in hits:
        chunk = chunks_by_id.get(hit.chunk_id)
        if chunk is None:
            logger.warning("Qdrant hit chunk %s missing from MySQL for document %s", hit.chunk_id, document.id)
            continue
        results.append(RetrievedChunk(chunk=chunk, score=hit.score))
    return results
