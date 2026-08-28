"""Tests for shared chat-message assembly."""

from __future__ import annotations

from foundry.adapters._messages import build_chat_messages
from shared.types import ModelRequest


def test_user_only_message_when_no_system_prompt() -> None:
    request = ModelRequest(prompt="analyze this", task="summary")

    messages = build_chat_messages(request)

    assert messages == [{"role": "user", "content": "analyze this"}]


def test_system_message_prepended_when_present() -> None:
    request = ModelRequest(
        prompt="analyze this",
        task="summary",
        system_prompt="You are a post-call analytics assistant.",
    )

    messages = build_chat_messages(request)

    assert messages == [
        {"role": "system", "content": "You are a post-call analytics assistant."},
        {"role": "user", "content": "analyze this"},
    ]


def test_empty_system_prompt_is_omitted() -> None:
    request = ModelRequest(prompt="analyze this", task="summary", system_prompt="")

    messages = build_chat_messages(request)

    assert messages == [{"role": "user", "content": "analyze this"}]
