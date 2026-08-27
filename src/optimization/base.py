"""Optimization strategy base types and shared domain objects.

A strategy consumes a transcript and produces a :class:`TranscriptOutcome`
describing the model calls it made (tokens, latency, cache hits) and any
extraction result. The benchmark harness aggregates these outcomes into
run-level metrics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from threading import Lock
from typing import ClassVar

from optimization.caching import CacheBundle
from shared.configuration import ModelMapping
from shared.contracts import (
    MemberIdExtractor,
    ModelRouter,
    TokenCounter,
)
from shared.types import ExtractionResult, Transcript


@dataclass(frozen=True, slots=True)
class ModelCall:
    """Record of a single model interaction performed by a strategy."""

    task: str
    deployment: str
    prompt_tokens: int
    output_tokens: int
    latency_ms: float
    from_cache: bool = False


@dataclass(slots=True)
class TranscriptOutcome:
    """The result of processing one transcript with a strategy."""

    transcript_id: str
    calls: list[ModelCall] = field(default_factory=list)
    extraction: ExtractionResult | None = None
    deterministic_hit: bool = False

    @property
    def prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls if not c.from_cache)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls if not c.from_cache)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.output_tokens

    @property
    def cache_hits(self) -> int:
        return sum(1 for c in self.calls if c.from_cache)


@dataclass(slots=True)
class PromptBundle:
    """Prompt templates available to a strategy."""

    baseline: str = "Analyze the following call transcript.\n\n{transcript}"
    optimized: str = "Extract structured insights.\n\n{transcript}"
    member_id_extraction: str = "Extract the member id from the transcript.\n\n{transcript}"
    compact: str = "Return only these fields as JSON: {fields}.\n{transcript}"


@dataclass(slots=True)
class StrategyContext:
    """Everything a strategy needs, injected via dependency inversion."""

    router: ModelRouter
    token_counter: TokenCounter
    mapping: ModelMapping
    caches: CacheBundle
    prompts: PromptBundle
    extractor: MemberIdExtractor | None = None
    chunker_name: str | None = None
    tasks: tuple[str, ...] = (
        "sentiment",
        "escalation",
        "summary",
        "evidence",
        "extraction",
    )
    # Guards shared cache and router bookkeeping when transcripts are
    # processed concurrently. Uncontended (a no-op) in sequential runs.
    lock: Lock = field(default_factory=Lock)


class OptimizationStrategy(ABC):
    """Base class for all optimization strategies."""

    name: ClassVar[str]

    @abstractmethod
    def process(self, transcript: Transcript, ctx: StrategyContext) -> TranscriptOutcome:
        """Process ``transcript`` and return its outcome."""
        raise NotImplementedError
