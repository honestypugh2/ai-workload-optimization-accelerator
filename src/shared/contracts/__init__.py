"""Structural protocols shared across the accelerator (dependency inversion seams)."""

from __future__ import annotations

from shared.contracts.protocols import (
    MemberIdExtractor,
    ModelProvider,
    ModelRouter,
    ResultStore,
    TokenCounter,
)

__all__ = [
    "MemberIdExtractor",
    "ModelProvider",
    "ModelRouter",
    "ResultStore",
    "TokenCounter",
]
