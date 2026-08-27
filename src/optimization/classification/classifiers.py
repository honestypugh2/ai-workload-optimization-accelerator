"""Deterministic classifiers: intent and escalation pre-filters.

Rules/keyword classifiers that resolve call intent and escalation without a model
call, mirroring the assessment's "move deterministic work off the LLM" levers. A
confident deterministic verdict lets a strategy skip the corresponding LLM task.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from shared.types import ConfidenceTier, Transcript

HIGH_CONFIDENCE_THRESHOLD = 0.75

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "billing": ("bill", "charge", "payment", "invoice", "refund"),
    "claims": ("claim", "reimburse", "eob", "denied"),
    "eligibility": ("eligib", "coverage", "benefit", "in network", "in-network"),
    "authorization": ("authoriz", "pre-auth", "preauth", "referral"),
    "pharmacy": ("prescription", "pharmacy", "medication", "refill"),
}
_ESCALATION_KEYWORDS: tuple[str, ...] = (
    "supervisor",
    "manager",
    "complaint",
    "lawyer",
    "escalat",
    "unacceptable",
    "cancel my",
)


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Outcome of a deterministic classifier."""

    label: str
    confidence: float
    tier: ConfidenceTier
    matched: tuple[str, ...]

    @property
    def is_confident(self) -> bool:
        return self.confidence >= HIGH_CONFIDENCE_THRESHOLD


class KeywordIntentClassifier:
    """Resolves call intent by keyword scoring across intent categories."""

    name: ClassVar[str] = "keyword_intent"

    def classify(self, transcript: Transcript) -> ClassificationResult:
        lowered = transcript.text.lower()
        scores = {
            label: tuple(kw for kw in kws if kw in lowered)
            for label, kws in _INTENT_KEYWORDS.items()
        }
        best_label, matched = max(scores.items(), key=lambda kv: len(kv[1]))
        if not matched:
            return ClassificationResult("unknown", 0.0, ConfidenceTier.LOW, ())
        confidence = min(0.95, 0.6 + 0.1 * len(matched))
        tier = (
            ConfidenceTier.HIGH
            if confidence >= HIGH_CONFIDENCE_THRESHOLD
            else ConfidenceTier.MEDIUM
        )
        return ClassificationResult(best_label, confidence, tier, matched)


class EscalationRulePrefilter:
    """Deterministic escalation detector via an escalation keyword ruleset."""

    name: ClassVar[str] = "escalation_rules"

    def classify(self, transcript: Transcript) -> ClassificationResult:
        lowered = transcript.text.lower()
        matched = tuple(kw for kw in _ESCALATION_KEYWORDS if kw in lowered)
        if matched:
            confidence = min(0.95, 0.7 + 0.05 * len(matched))
            return ClassificationResult("escalated", confidence, ConfidenceTier.HIGH, matched)
        # Absence of escalation cues is a confident "not escalated" signal.
        return ClassificationResult("not_escalated", 0.8, ConfidenceTier.HIGH, ())
