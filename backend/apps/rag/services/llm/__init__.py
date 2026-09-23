from functools import lru_cache

from django.conf import settings

from .base import LLMError, LLMMessage, LLMProvider


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """Factory for the configured provider (only Gemini is implemented)."""
    provider = (settings.LLM_PROVIDER or "gemini").lower()
    if provider == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider()
    raise LLMError(f"Unsupported LLM_PROVIDER '{provider}'.")


__all__ = ["LLMError", "LLMMessage", "LLMProvider", "get_llm_provider"]
