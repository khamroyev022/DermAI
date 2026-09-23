from unittest import mock

from django.test import SimpleTestCase

from apps.rag.services.embeddings import SentenceTransformerEmbeddingProvider


class _FakeSentenceTransformer:
    def __init__(self, name, device="cpu"):
        self.name = name
        self.max_seq_length = 0
        self.calls = []

    def get_embedding_dimension(self):
        return 4

    def encode(self, texts, batch_size, normalize_embeddings, convert_to_numpy, show_progress_bar):
        self.calls.append(list(texts))
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class SentenceTransformerProviderTests(SimpleTestCase):
    def _provider(self):
        provider = SentenceTransformerEmbeddingProvider(model_name="intfloat/multilingual-e5-base", batch_size=8)
        fake_module = mock.MagicMock()
        fake_module.SentenceTransformer = _FakeSentenceTransformer
        return provider, fake_module

    def test_model_loaded_once_and_dimension_detected(self):
        provider, fake_module = self._provider()
        with mock.patch.dict("sys.modules", {"sentence_transformers": fake_module}):
            provider.embed_query("hello")
            provider.embed_documents(["a", "b"])
            self.assertEqual(provider.dimension, 4)
            self.assertIs(provider._model, provider._load())  # same instance, no reload

    def test_e5_prefixes_applied(self):
        provider, fake_module = self._provider()
        with mock.patch.dict("sys.modules", {"sentence_transformers": fake_module}):
            provider.embed_query("what is vitiligo")
            provider.embed_documents(["passage text"])
            calls = provider._model.calls
        self.assertEqual(calls[0], ["query: what is vitiligo"])
        self.assertEqual(calls[1], ["passage: passage text"])

    def test_non_e5_models_get_no_prefix(self):
        provider = SentenceTransformerEmbeddingProvider(model_name="some/other-model", batch_size=8)
        fake_module = mock.MagicMock()
        fake_module.SentenceTransformer = _FakeSentenceTransformer
        with mock.patch.dict("sys.modules", {"sentence_transformers": fake_module}):
            provider.embed_query("hello")
            self.assertEqual(provider._model.calls[0], ["hello"])

    def test_empty_input_returns_empty_without_loading(self):
        provider, _ = self._provider()
        self.assertEqual(provider.embed_documents([]), [])
        self.assertIsNone(provider._model)
