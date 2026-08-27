"""Dynamic-prompt-construction strategy driven by deterministic classifiers.

Uses the intent/escalation classifiers plus deterministic member-id extraction to
build the *minimal* set of LLM tasks per transcript (dynamic prompt construction)
with a compact, schema-reduced prompt (JSON schema reduction).
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
from optimization.classification.classifiers import (
    HIGH_CONFIDENCE_THRESHOLD,
    EscalationRulePrefilter,
    KeywordIntentClassifier,
)
from optimization.preprocessing import TranscriptPreprocessor
from registry.strategy_registry import strategy_registry
from shared.types import Transcript


@strategy_registry.register("dynamic_prompt_construction")
class DynamicPromptConstructionStrategy(OptimizationStrategy):
    """Build the minimal LLM task set per transcript using deterministic signals.

    Runs deterministic member-id extraction plus intent/escalation classifiers,
    then only calls the model for tasks that were *not* resolved deterministically,
    using a compact schema-reduced prompt. Models the assessment's "dynamic prompt
    construction", "JSON schema reduction", and deterministic classification levers.
    """

    name: ClassVar[str] = "dynamic_prompt_construction"

    def __init__(self) -> None:
        self._intent = KeywordIntentClassifier()
        self._escalation = EscalationRulePrefilter()

    def process(self, transcript: Transcript, ctx: StrategyContext) -> TranscriptOutcome:
        pre = TranscriptPreprocessor(selective_context=True).run(transcript, ctx.token_counter)
        clean = pre.transcript

        extraction = ctx.extractor.extract(clean) if ctx.extractor else None
        deterministic_hit = bool(
            extraction
            and extraction.member_id is not None
            and extraction.confidence >= HIGH_CONFIDENCE_THRESHOLD
        )
        escalation_verdict = self._escalation.classify(clean)

        # Dynamically assemble only the tasks that still need a model.
        tasks: list[str] = ["sentiment", "summary", "evidence"]
        if not escalation_verdict.is_confident:
            tasks.append("escalation")
        if not deterministic_hit:
            tasks.append("extraction")

        fields = ",".join(tasks)
        template = ctx.prompts.compact.replace("{fields}", fields)
        calls: list[ModelCall] = [call_task(ctx, task, clean.text, template) for task in tasks]
        return TranscriptOutcome(
            transcript_id=transcript.transcript_id,
            calls=calls,
            extraction=extraction,
            deterministic_hit=deterministic_hit,
        )
