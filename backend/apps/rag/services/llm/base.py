from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Sequence

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class LLMMessage:
    role: Role
    content: str


class LLMError(Exception):
    """Any failure talking to the LLM provider (network, quota, safety block, ...)."""


class LLMProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def generate(self, system_prompt: str, messages: Sequence[LLMMessage]) -> str:
        """Return the assistant's answer text for the given conversation."""
