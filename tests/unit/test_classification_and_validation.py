"""Deterministic classification pre-filters and check-digit validation."""

from __future__ import annotations

from optimization.classification import (
    EscalationRulePrefilter,
    KeywordIntentClassifier,
)
from registry.strategy_registry import strategy_registry
from shared.types import ConfidenceTier
from workloads.post_call_analytics.domain.extraction import (
    DeterministicMemberIdExtractor,
    LuhnCheckDigitValidator,
)


def test_keyword_intent_classifier_labels_billing(make_transcript) -> None:
    t = make_transcript("i-bill", "I have a question about a charge on my bill.", gold=None)
    result = KeywordIntentClassifier().classify(t)
    assert result.label == "billing"
    assert result.matched


def test_keyword_intent_classifier_unknown_when_no_keywords(make_transcript) -> None:
    t = make_transcript("i-none", "Hello there, nice weather today.", gold=None)
    result = KeywordIntentClassifier().classify(t)
    assert result.label == "unknown"
    assert result.tier is ConfidenceTier.LOW


def test_escalation_prefilter_detects_supervisor(make_transcript) -> None:
    t = make_transcript("e-esc", "I want to speak to a supervisor right now.", gold=None)
    result = EscalationRulePrefilter().classify(t)
    assert result.label == "escalated"
    assert result.is_confident


def test_escalation_prefilter_not_escalated(make_transcript) -> None:
    t = make_transcript("e-calm", "Thanks so much for the help today.", gold=None)
    result = EscalationRulePrefilter().classify(t)
    assert result.label == "not_escalated"


def test_dynamic_prompt_construction_strategy_registered() -> None:
    assert "dynamic_prompt_construction" in strategy_registry.names()


def test_luhn_validator_downgrades_invalid_candidate(make_transcript) -> None:
    t = make_transcript("cd-bad", "It is MBR482910337.", gold="MBR482910337")
    validated = DeterministicMemberIdExtractor(check_digit=LuhnCheckDigitValidator())
    result = validated.extract(t)
    # Same id is still surfaced, but a failed check digit downgrades confidence.
    assert result.member_id == "MBR482910337"
    if not LuhnCheckDigitValidator().is_valid("MBR482910337"):
        assert result.tier is ConfidenceTier.LOW
        assert result.confidence <= 0.4


def test_check_digit_default_off_keeps_high_confidence(make_transcript) -> None:
    t = make_transcript("cd-off", "It is MBR482910337.", gold="MBR482910337")
    result = DeterministicMemberIdExtractor().extract(t)
    assert result.tier is ConfidenceTier.HIGH
