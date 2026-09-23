"""
Chat orchestration:

    user question
      -> RAG retrieval (Qdrant filtered by the chat's document, then MySQL chunks)
      -> below threshold?  answer "not found", no LLM call
      -> else Gemini with system prompt + last N messages + context
      -> persist USER + ASSISTANT messages (sources built by the backend, not by the LLM)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction

from apps.rag.services.llm import LLMError, LLMMessage, get_llm_provider
from apps.rag.services.prompts import SYSTEM_PROMPT, build_user_prompt
from apps.rag.services.qdrant_service import VectorStoreError
from apps.rag.services.retrieval import RetrievedChunk, retrieve

from ..models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


@dataclass
class ChatAnswer:
    answer: str
    sources: list[dict] = field(default_factory=list)
    user_message: ChatMessage | None = None
    assistant_message: ChatMessage | None = None


class ChatServiceError(Exception):
    pass


def _recent_history(chat: ChatSession, limit: int) -> list[ChatMessage]:
    """Last `limit` messages (oldest first), used as conversational memory."""
    if limit <= 0:
        return []
    recent = list(chat.messages.order_by("-created_at", "-id")[:limit])
    recent.reverse()
    return recent


def _previous_user_question(history: list[ChatMessage]) -> str | None:
    for message in reversed(history):
        if message.role == ChatMessage.Role.USER:
            return message.content
    return None


def _build_llm_messages(history: list[ChatMessage], chat: ChatSession, retrieved: list[RetrievedChunk], question: str):
    messages: list[LLMMessage] = []
    for item in history:
        role = "assistant" if item.role == ChatMessage.Role.ASSISTANT else "user"
        messages.append(LLMMessage(role=role, content=item.content))
    sources = [{"page_start": r.chunk.page_start, "page_end": r.chunk.page_end, "text": r.chunk.text} for r in retrieved]
    messages.append(LLMMessage(role="user", content=build_user_prompt(chat.document.title, sources, question)))
    return messages


def answer_question(chat: ChatSession, question: str) -> ChatAnswer:
    """Run RAG for `question` in `chat` and persist both messages."""
    question = question.strip()
    if not question:
        raise ChatServiceError("Empty question.")

    history = _recent_history(chat, settings.CHAT_HISTORY_MESSAGES)

    try:
        retrieved = retrieve(
            chat.document,
            question,
            previous_user_question=_previous_user_question(history),
        )
    except VectorStoreError as exc:
        logger.error("Retrieval failed for chat %s: %s", chat.id, exc)
        raise

    if not retrieved:
        answer_text = settings.RAG_NOT_FOUND_ANSWER
        sources: list[dict] = []
    else:
        llm = get_llm_provider()
        llm_messages = _build_llm_messages(history, chat, retrieved, question)
        try:
            answer_text = llm.generate(SYSTEM_PROMPT, llm_messages)
        except LLMError:
            logger.error("LLM generation failed for chat %s", chat.id)
            raise
        # Sources come from retrieval, never from the model's output.
        sources = [r.to_source() for r in retrieved]

    with transaction.atomic():
        user_message = ChatMessage.objects.create(chat=chat, role=ChatMessage.Role.USER, content=question)
        assistant_message = ChatMessage.objects.create(
            chat=chat, role=ChatMessage.Role.ASSISTANT, content=answer_text, sources=sources
        )
        update_fields = ["updated_at"]
        if not chat.title or chat.title == chat.document.title:
            chat.title = question[:255]
            update_fields.append("title")
        chat.save(update_fields=update_fields)

    return ChatAnswer(
        answer=answer_text,
        sources=sources,
        user_message=user_message,
        assistant_message=assistant_message,
    )
