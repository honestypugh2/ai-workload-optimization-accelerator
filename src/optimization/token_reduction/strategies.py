"""Token-reduction strategies.

Contains the reference baseline (full-transcript prompting) and a family of
token-reduction strategies: prompt optimization, context minimization,
selective extraction, and summarize-before-analyze. Each is registered as a
plugin so the benchmark harness can select it by name without branching logic.
"""

from __future__ import annotations

from typing import ClassVar

from optimization._engine import call_task, process_over_chunks
from optimization.base import (
    ModelCall,
    OptimizationStrategy,
    StrategyContext,
    TranscriptOutcome,
)
from optimization.preprocessing import TranscriptPreprocessor
from registry.strategy_registry import strategy_registry
from shared.types import ExtractionResult, Transcript


def _extract(ctx: StrategyContext, transcript: Transcript) -> ExtractionResult | None:
    if ctx.extractor is None:
        return None
    return ctx.extractor.extract(transcript)


@strategy_registry.register("baseline_full_transcript")
class BaselineFullTranscriptStrategy(OptimizationStrategy):
    """Reference current-state: full transcript sent to every task, no caching."""

    name: ClassVar[str] = "baseline_full_transcript"

    def process(self, transcript: Transcript, ctx: StrategyContext) -> TranscriptOutcome:
        calls: list[ModelCall] = []
        for task in ctx.tasks:
            calls.append(call_task(ctx, task, transcript.text, ctx.prompts.baseline))
        return TranscriptOutcome(
            transcript_id=transcript.transcript_id,
            calls=calls,
            extraction=_extract(ctx, transcript),
        )


class _PreprocessedStrategy(OptimizationStrategy):
    """Base for strategies that preprocess before prompting."""

    name: ClassVar[str]
    remove_boilerplate: ClassVar[bool] = True
    normalize_digits: ClassVar[bool] = True
    selective_context: ClassVar[bool] = False
    tasks_override: ClassVar[tuple[str, ...] | None] = None

    def process(self, transcript: Transcript, ctx: StrategyContext) -> TranscriptOutcome:
        pre = TranscriptPreprocessor(
            remove_boilerplate=self.remove_boilerplate,
            normalize_digits=self.normalize_digits,
            selective_context=self.selective_context,
        ).run(transcript, ctx.token_counter)
        tasks = self.tasks_override or ctx.tasks
        calls = process_over_chunks(
            ctx, pre.transcript, pre.transcript.text, tasks, ctx.prompts.optimized
        )
        return TranscriptOutcome(
            transcript_id=transcript.transcript_id,
            calls=calls,
            extraction=_extract(ctx, pre.transcript),
        )


@strategy_registry.register("prompt_optimization")
class PromptOptimizationStrategy(_PreprocessedStrategy):
    """Shorter, structured prompts with light preprocessing."""

    name = "prompt_optimization"


@strategy_registry.register("context_minimization")
class ContextMinimizationStrategy(_PreprocessedStrategy):
    """Aggressive context reduction: drop irrelevant, non-member turns."""

    name = "context_minimization"
    selective_context = True


@strategy_registry.register("selective_extraction")
class SelectiveExtractionStrategy(_PreprocessedStrategy):
    """Only run extraction and escalation tasks; skip expensive summary/evidence."""

    name = "selective_extraction"
    selective_context = True
    tasks_override = ("escalation", "extraction")


@strategy_registry.register("summarize_before_analyze")
class SummarizeBeforeAnalyzeStrategy(OptimizationStrategy):
    """Summarize once, then run cheaper analytic tasks over the summary."""

    name: ClassVar[str] = "summarize_before_analyze"

    def process(self, transcript: Transcript, ctx: StrategyContext) -> TranscriptOutcome:
        pre = TranscriptPreprocessor(selective_context=True).run(transcript, ctx.token_counter)
        summary_call = call_task(ctx, "summary", pre.transcript.text, ctx.prompts.optimized)
        # Downstream tasks operate on the (much smaller) summary content.
        summary_text = f"Summary of call {transcript.transcript_id}."
        calls = [summary_call]
        for task in ("sentiment", "escalation", "evidence"):
            calls.append(call_task(ctx, task, summary_text, ctx.prompts.optimized))
        return TranscriptOutcome(
            transcript_id=transcript.transcript_id,
            calls=calls,
            extraction=_extract(ctx, pre.transcript),
        )
