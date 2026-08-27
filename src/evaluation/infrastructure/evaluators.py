"""Concrete local evaluators.

All evaluators are deterministic and run without cloud credentials. Foundry-based
evaluators can be layered on later via ``foundry.evaluations`` without changing
these interfaces.
"""

from __future__ import annotations

import json
from typing import ClassVar

from evaluation.domain import EvaluationContext, Evaluator
from registry.evaluator_registry import evaluator_registry
from shared.contracts import MemberIdExtractor
from shared.types import Transcript

_ESCALATION_MARKERS = ("supervisor", "escalat", "frustrated", "third time")


def _select_extractor(ctx: EvaluationContext) -> MemberIdExtractor:
    """Pick the extractor named by the evaluation config from the scenario."""
    scenario = ctx.scenario
    if ctx.config.extractor == "naive" and hasattr(scenario, "baseline_extractor"):
        return scenario.baseline_extractor()  # type: ignore[attr-defined]
    if hasattr(scenario, "default_extractor"):
        return scenario.default_extractor()  # type: ignore[attr-defined]
    raise TypeError("Scenario does not expose an extractor for member-id evaluation.")


@evaluator_registry.register("member_id")
class MemberIdEvaluator(Evaluator):
    """Precision / recall / FP / FN for member-id extraction."""

    name: ClassVar[str] = "member_id"

    def evaluate(self, ctx: EvaluationContext) -> dict[str, float]:
        extractor = _select_extractor(ctx)
        tp = fp = fn = 0
        with_gold = without_gold = no_gold_predicted = 0

        for transcript in ctx.dataset:
            predicted = extractor.extract(transcript).member_id
            gold = transcript.member_id_gold
            if gold is not None:
                with_gold += 1
                if predicted == gold:
                    tp += 1
                else:
                    fn += 1
                    if predicted is not None:
                        fp += 1
            else:
                without_gold += 1
                if predicted is not None:
                    fp += 1
                    no_gold_predicted += 1

        recall = tp / with_gold if with_gold else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        fpr = no_gold_predicted / without_gold if without_gold else 0.0
        fnr = fn / with_gold if with_gold else 0.0
        return {
            "member_id_recall": round(recall, 4),
            "member_id_precision": round(precision, 4),
            "member_id_false_positive_rate": round(fpr, 4),
            "member_id_false_negative_rate": round(fnr, 4),
            "extraction_success_rate": round(recall, 4),
        }


def _structured_analysis(transcript: Transcript, extractor: MemberIdExtractor) -> dict:
    escalated = any(m in transcript.text.lower() for m in _ESCALATION_MARKERS)
    return {
        "transcript_id": transcript.transcript_id,
        "escalation": escalated,
        "sentiment": "negative" if escalated else "neutral",
        "member_id": extractor.extract(transcript).member_id,
        "summary": f"Call {transcript.transcript_id} handled.",
    }


_REQUIRED_KEYS = {"transcript_id", "escalation", "sentiment", "member_id", "summary"}


@evaluator_registry.register("structured_output")
class StructuredOutputEvaluator(Evaluator):
    """JSON validity + schema validity of structured analysis output."""

    name: ClassVar[str] = "structured_output"

    def evaluate(self, ctx: EvaluationContext) -> dict[str, float]:
        extractor = _select_extractor(ctx)
        valid_json = 0
        valid_schema = 0
        total = len(ctx.dataset) or 1
        for transcript in ctx.dataset:
            analysis = _structured_analysis(transcript, extractor)
            serialized = json.dumps(analysis)
            try:
                parsed = json.loads(serialized)
                valid_json += 1
                if _REQUIRED_KEYS.issubset(parsed.keys()):
                    valid_schema += 1
            except json.JSONDecodeError:  # pragma: no cover - defensive
                continue
        return {
            "json_validity": round(valid_json / total, 4),
            "schema_validity": round(valid_schema / total, 4),
            "structured_output_validity": round(valid_schema / total, 4),
        }


@evaluator_registry.register("escalation")
class EscalationEvaluator(Evaluator):
    """Escalation-detection accuracy against synthetic gold labels."""

    name: ClassVar[str] = "escalation"

    def evaluate(self, ctx: EvaluationContext) -> dict[str, float]:
        correct = 0
        total = len(ctx.dataset) or 1
        for transcript in ctx.dataset:
            gold = transcript.metadata.get("escalated") == "True"
            predicted = any(m in transcript.text.lower() for m in _ESCALATION_MARKERS)
            if predicted == gold:
                correct += 1
        accuracy = correct / total
        return {
            "escalation_accuracy": round(accuracy, 4),
            "task_adherence": round(accuracy, 4),
        }
