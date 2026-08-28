"""Shared chat-message assembly for OpenAI-compatible providers."""

from __future__ import annotations

from shared.types import ModelRequest


def build_chat_messages(request: ModelRequest) -> list[dict[str, str]]:
    """Build the Chat Completions ``messages`` list for a request.

    Prepends a system message when the request carries one so live runs can
    exercise production-style system + user prompting.
    """
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    return messages
