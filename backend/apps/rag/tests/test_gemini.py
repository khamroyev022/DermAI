from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.rag.services.llm.base import LLMError, LLMMessage
from apps.rag.services.llm.gemini import GeminiProvider


class GeminiProviderTests(SimpleTestCase):
    """The real Gemini API is never called: `genai.Client` is mocked."""

    def _provider_with_client(self, response=None, side_effect=None):
        provider = GeminiProvider(api_key="test-key-not-real", model="gemini-test")
        client = mock.MagicMock()
        if side_effect is not None:
            client.models.generate_content.side_effect = side_effect
        else:
            client.models.generate_content.return_value = response
        provider._client = client
        return provider, client

    def test_generate_maps_roles_and_returns_text(self):
        provider, client = self._provider_with_client(response=SimpleNamespace(text="  Vitiligo is ...  "))
        answer = provider.generate(
            "SYSTEM",
            [LLMMessage("user", "Hi"), LLMMessage("assistant", "Hello"), LLMMessage("user", "What is vitiligo?")],
        )
        self.assertEqual(answer, "Vitiligo is ...")
        _, kwargs = client.models.generate_content.call_args
        self.assertEqual(kwargs["model"], "gemini-test")
        self.assertEqual([c.role for c in kwargs["contents"]], ["user", "model", "user"])
        self.assertEqual(kwargs["config"].system_instruction, "SYSTEM")

    def test_missing_api_key_raises_llm_error(self):
        provider = GeminiProvider(api_key="", model="gemini-test")
        with self.assertRaises(LLMError):
            provider.generate("SYSTEM", [LLMMessage("user", "hi")])

    def test_api_error_is_wrapped_without_leaking_key(self):
        from google.genai import errors

        api_error = errors.APIError(429, {"error": {"message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}})
        provider, _ = self._provider_with_client(side_effect=api_error)
        with self.assertRaises(LLMError) as ctx:
            provider.generate("SYSTEM", [LLMMessage("user", "hi")])
        self.assertNotIn("test-key-not-real", str(ctx.exception))

    def test_empty_response_raises(self):
        response = SimpleNamespace(text="", candidates=[], prompt_feedback=SimpleNamespace(block_reason="SAFETY"))
        provider, _ = self._provider_with_client(response=response)
        with self.assertRaises(LLMError):
            provider.generate("SYSTEM", [LLMMessage("user", "hi")])

    def test_fallback_to_candidate_parts(self):
        response = SimpleNamespace(
            text=None,
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text="part A "), SimpleNamespace(text="part B")]))],
        )
        provider, _ = self._provider_with_client(response=response)
        self.assertEqual(provider.generate("SYSTEM", [LLMMessage("user", "hi")]), "part A part B")
