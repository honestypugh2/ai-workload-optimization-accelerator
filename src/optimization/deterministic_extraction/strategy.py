"""Deterministic-first extraction strategy.

Runs a deterministic (regex/normalization) extractor before any LLM call. When
the deterministic result is high confidence, the expensive LLM extraction task
is skipped entirely; otherwise it falls back to the model. This directly models
the assessment's "deterministic extraction before LLM calls" recommendation.
"""

from __future__ import annotations

from typing import ClassVar

from optimization._engine import call_task
from optimization.base import (
    ModelCall,
    OptimizationStrategy,
    StrategyContext,
    TranscriptOutcome,
)
from optimization.chunking import Chunk, get_chunker
from optimization.preprocessing import TranscriptPreprocessor
from registry.strategy_registry import strategy_registry
from shared.types import Transcript

_HIGH_CONFIDENCE_THRESHOLD = 0.75


@strategy_registry.register("deterministic_first")
class DeterministicFirstStrategy(OptimizationStrategy):
    """Deterministic extraction first; LLM fallback only when needed."""

    name: ClassVar[str] = "deterministic_first"
    # Analytic tasks that run on every (map) chunk; a reduce chunk consolidates.
    _ANALYTIC_TASKS: ClassVar[tuple[str, ...]] = ("sentiment", "escalation", "summary", "evidence")

    def process(self, transcript: Transcript, ctx: StrategyContext) -> TranscriptOutcome:
        pre = TranscriptPreprocessor(selective_context=True).run(transcript, ctx.token_counter)
        clean = pre.transcript

        extraction = ctx.extractor.extract(clean) if ctx.extractor else None
        deterministic_hit = bool(
            extraction
            and extraction.member_id is not None
            and extraction.confidence >= _HIGH_CONFIDENCE_THRESHOLD
        )

        calls: list[ModelCall] = []
        # Honour the configured chunker: with no chunker this is a single full
        # chunk (identical to the unchunked path); a chunker fans the LLM tasks
        # out per segment, so the chunker choice drives call count, time and cost.
        for chunk in self._chunks(ctx, clean):
            tasks = ("summary", "evidence") if chunk.is_reduce else self._ANALYTIC_TASKS
            for task in tasks:
                calls.append(call_task(ctx, task, chunk.text, ctx.prompts.optimized))
            # LLM extraction fallback searches each map chunk when deterministic
            # extraction was not confident.
            if not deterministic_hit and not chunk.is_reduce:
                calls.append(
                    call_task(ctx, "extraction", chunk.text, ctx.prompts.member_id_extraction)
                )

        return TranscriptOutcome(
            transcript_id=transcript.transcript_id,
            calls=calls,
            extraction=extraction,
            deterministic_hit=deterministic_hit,
        )

    @staticmethod
    def _chunks(ctx: StrategyContext, transcript: Transcript) -> list[Chunk]:
        if not ctx.chunker_name:
            return [Chunk(index=0, text=transcript.text)]
        return get_chunker(ctx.chunker_name).split(transcript, ctx.token_counter)
