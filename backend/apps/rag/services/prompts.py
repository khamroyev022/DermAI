"""Prompt templates for document-grounded answering."""

from __future__ import annotations

from typing import Sequence

SYSTEM_PROMPT = """You are a document-grounded AI assistant.

Answer the user's question using ONLY the DOCUMENT CONTEXT supplied below.

Do not use outside knowledge to add factual information.

Do not invent information.

If the answer cannot be supported by the supplied context, respond that the information was not found in the uploaded document.

Answer in the same language as the user's question.

Preserve important technical terminology.

Do not reproduce unnecessarily long copyrighted passages.

Summarize where appropriate.

Do not invent page numbers.

Page numbers and sources are managed by the backend."""


def format_context(document_title: str, sources: Sequence[dict]) -> str:
    """
    sources: [{"page_start": int, "page_end": int, "text": str}, ...]
    """
    blocks: list[str] = []
    for index, source in enumerate(sources, start=1):
        pages = (
            str(source["page_start"])
            if source["page_start"] == source["page_end"]
            else f"{source['page_start']}-{source['page_end']}"
        )
        blocks.append(
            f"SOURCE {index}\n\nDocument:\n{document_title}\n\nPages:\n{pages}\n\nContent:\n{source['text']}"
        )
    return "\n\n\n".join(blocks)


def build_user_prompt(document_title: str, sources: Sequence[dict], question: str) -> str:
    context = format_context(document_title, sources)
    return f"DOCUMENT CONTEXT:\n\n{context}\n\n\nUSER QUESTION:\n\n{question}"
