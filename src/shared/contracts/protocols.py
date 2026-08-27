"""Structural contracts (Protocols) enabling dependency inversion.

Concrete adapters (Azure, filesystem, mock) implement these Protocols. Core
business logic depends only on the Protocols, never on concrete providers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from shared.types import (
    ExtractionResult,
    ModelRequest,
    ModelResponse,
    Transcript,
)


@runtime_checkable
class TokenCounter(Protocol):
    """Estimates token counts for prompts and completions."""

    def count(self, text: str) -> int:
        """Return an approximate token count for ``text``."""
        ...


@runtime_checkable
class ModelProvider(Protocol):
    """A source of model completions (mock, Azure OpenAI, Foundry, ...)."""

    @property
    def deployment(self) -> str:
        """The logical deployment name backing this provider."""
        ...

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Execute a completion request and return the response."""
        ...


@runtime_checkable
class ModelRouter(Protocol):
    """Routes a request to one of several backing deployments."""

    def route(self, request: ModelRequest) -> ModelProvider:
        """Select a provider for ``request``."""
        ...


@runtime_checkable
class MemberIdExtractor(Protocol):
    """Extracts a member identifier from a transcript."""

    @property
    def name(self) -> str: ...

    def extract(self, transcript: Transcript) -> ExtractionResult:
        """Attempt to extract a member id from ``transcript``."""
        ...


@runtime_checkable
class ResultStore(Protocol):
    """Persists structured JSON results."""

    def save(self, key: str, payload: dict) -> str:
        """Persist ``payload`` under ``key`` and return the resolved location."""
        ...

    def load(self, key: str) -> dict:
        """Load a previously persisted payload."""
        ...
