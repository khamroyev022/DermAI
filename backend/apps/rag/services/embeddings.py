

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Sequence

from django.conf import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):

    model_name: str = "abstract"

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Size of the vectors produced by this provider."""

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed passages that will be stored in the vector database."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (may use a different prefix than documents)."""

    def warm_up(self) -> None:
        """Eagerly load any heavy resources. Default: no-op."""


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """
    sentence-transformers backed provider.

    E5 models expect "query: " / "passage: " prefixes; we add them automatically
    when the configured model name contains "e5".
    """

    def __init__(self, model_name: str | None = None, batch_size: int | None = None, max_seq_length: int = 512):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self.max_seq_length = max_seq_length
        self._model = None
        self._dimension: int | None = None
        self._lock = threading.Lock()
        self._uses_e5_prefixes = "e5" in self.model_name.lower()

    # -- loading -----------------------------------------------------------

    def _load(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer  # heavy import, done once

                logger.info("Loading embedding model %s ...", self.model_name)
                model = SentenceTransformer(self.model_name, device="cpu")
                model.max_seq_length = self.max_seq_length
                self._dimension = int(model.get_embedding_dimension())
                self._model = model
                logger.info("Embedding model loaded (dimension=%s)", self._dimension)
        return self._model

    def warm_up(self) -> None:
        self._load()

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._load()
        return int(self._dimension)  # type: ignore[arg-type]

    # -- encoding ----------------------------------------------------------

    def _prefix(self, texts: Sequence[str], kind: str) -> list[str]:
        if not self._uses_e5_prefixes:
            return list(texts)
        return [f"{kind}: {t}" for t in texts]

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(x) for x in row] for row in vectors]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(self._prefix(texts, "passage"))

    def embed_query(self, text: str) -> list[float]:
        return self._encode(self._prefix([text], "query"))[0]


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    """Process-wide singleton. Tests replace it via `unittest.mock.patch`."""
    return SentenceTransformerEmbeddingProvider()
