"""
Gemini implementation of LLMProvider (google-genai SDK).

The API key is read from settings.GEMINI_API_KEY, which itself comes only from
the GEMINI_API_KEY environment variable. It is never logged.
"""

from __future__ import annotations

import logging
from typing import Sequence

from django.conf import settings

from .base import LLMError, LLMMessage, LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None, temperature: float = 0.2):
        self._api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.temperature = temperature
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise LLMError("GEMINI_API_KEY is not configured.")
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover
                raise LLMError("google-genai package is not installed.") from exc
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    @staticmethod
    def _to_contents(messages: Sequence[LLMMessage]):
        from google.genai import types

        contents = []
        for message in messages:
            role = "model" if message.role == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=message.content)]))
        return contents

    def generate(self, system_prompt: str, messages: Sequence[LLMMessage]) -> str:
        if not messages:
            raise LLMError("No messages to send to the model.")

        client = self._get_client()
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self.temperature,
            max_output_tokens=2048,
        )
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=self._to_contents(messages),
                config=config,
            )
        except errors.APIError as exc:
            # exc.message never contains the key; log status only.
            logger.error("Gemini API error (code=%s): %s", getattr(exc, "code", "?"), getattr(exc, "message", exc))
            raise LLMError(f"Gemini API error (code={getattr(exc, 'code', '?')}).") from exc
        except Exception as exc:  # noqa: BLE001 — network / SDK errors
            logger.error("Gemini request failed: %s", exc.__class__.__name__)
            raise LLMError("Gemini request failed.") from exc

        text = _extract_text(response)
        if not text:
            feedback = getattr(response, "prompt_feedback", None)
            reason = getattr(feedback, "block_reason", None)
            logger.warning("Gemini returned no text (block_reason=%s)", reason)
            raise LLMError("Gemini returned an empty response." + (f" Blocked: {reason}." if reason else ""))
        return text.strip()


def _extract_text(response) -> str:
    text = getattr(response, "text", None)
    if text:
        return text
    # Fallback: manually concatenate candidate parts.
    parts: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(part_text)
    return "".join(parts)
