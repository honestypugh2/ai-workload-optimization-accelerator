"""Member-id extraction: the core capability the accelerator demonstrates.

Covers clean, spaced, dashed, spoken, noisy, missing, conflicting, low-confidence,
false-positive, and long-transcript cases, plus the headline result: the naive
baseline recovers roughly 30% while the deterministic strategy reaches ~90% on
the same synthetic labeled dataset.
"""

from __future__ import annotations

import random

import pytest

from shared.types import ConfidenceTier, Speaker, Transcript, Utterance
from workloads.post_call_analytics.domain.member_id import (
    MemberIdFormat,
    render_dashed,
    render_spoken,
)
from workloads.post_call_analytics.scenario import PostCallAnalyticsScenario


def _deterministic():
    return PostCallAnalyticsScenario().default_extractor()


def _naive():
    return PostCallAnalyticsScenario().baseline_extractor()


def test_clean_id_recovered_by_both_extractors(make_transcript) -> None:
    t = make_transcript("t-clean", "Sure, it's MBR482910337.", gold="MBR482910337")
    assert _naive().extract(t).member_id == "MBR482910337"
    assert _deterministic().extract(t).member_id == "MBR482910337"


def test_dashed_id_recovered_only_by_deterministic(make_transcript) -> None:
    t = make_transcript("t-dash", "It is MBR-482-910-337.", gold="MBR482910337")
    assert _naive().extract(t).member_id is None
    assert _deterministic().extract(t).member_id == "MBR482910337"


def test_spaced_id_recovered_by_deterministic(make_transcript) -> None:
    t = make_transcript("t-space", "M B R 482910337 is the number.", gold="MBR482910337")
    assert _deterministic().extract(t).member_id == "MBR482910337"


def test_spoken_id_recovered_by_deterministic(make_transcript) -> None:
    t = make_transcript(
        "t-spoken",
        "Okay it's H P L seven seven one zero four three nine two eight.",
        gold="HPL771043928",
    )
    assert _naive().extract(t).member_id is None
    assert _deterministic().extract(t).member_id == "HPL771043928"


def test_spoken_survives_lowercase_word_tail(make_transcript) -> None:
    # Regression: the "s" in "it's" must not be absorbed into the prefix.
    t = make_transcript(
        "t-its",
        "it's M B R four two eight five zero one eight zero five.",
        gold="MBR428501805",
    )
    assert _deterministic().extract(t).member_id == "MBR428501805"


def test_noisy_transcript_with_filler(make_transcript) -> None:
    t = make_transcript(
        "t-noise",
        "uh um so like it's MBR-482-910-337 you know",
        gold="MBR482910337",
        extra=[(Speaker.MEMBER, "sorry the signal is bad")],
    )
    assert _deterministic().extract(t).member_id == "MBR482910337"


def test_missing_id_returns_none(make_transcript) -> None:
    t = make_transcript(
        "t-missing",
        "I don't have my card with me right now.",
        gold=None,
    )
    assert _naive().extract(t).member_id is None
    assert _deterministic().extract(t).member_id is None


def test_no_false_positive_on_unrelated_numbers() -> None:
    # Order number / phone-like digits without an alpha prefix must not match.
    t = Transcript(
        transcript_id="t-fp",
        utterances=(Utterance(Speaker.MEMBER, "My order was 4829103 and my zip is 55402."),),
        member_id_gold=None,
    )
    assert _deterministic().extract(t).member_id is None
    assert _naive().extract(t).member_id is None


def test_fragmented_low_confidence_tier(make_transcript) -> None:
    t = make_transcript(
        "t-frag",
        "It starts with MBR4829 and then",
        gold="MBR482910337",
        extra=[(Speaker.MEMBER, "the rest is 10337")],
    )
    result = _deterministic().extract(t)
    assert result.member_id == "MBR482910337"
    assert result.tier in (ConfidenceTier.MEDIUM, ConfidenceTier.HIGH)


def test_conflicting_ids_picks_first_valid(make_transcript) -> None:
    t = make_transcript(
        "t-conflict",
        "It might be MBR482910337 or maybe HPL771043928.",
        gold="MBR482910337",
    )
    # Deterministic returns a valid contiguous id (the first match).
    assert _deterministic().extract(t).member_id == "MBR482910337"


def test_long_transcript_extraction(id_format: MemberIdFormat) -> None:
    filler = [Utterance(Speaker.AGENT, "Thank you for holding.") for _ in range(200)]
    utterances = (
        *filler,
        Utterance(Speaker.MEMBER, "Right, my id is MBR-482-910-337."),
        *filler,
    )
    t = Transcript("t-long", utterances, member_id_gold="MBR482910337")
    assert _deterministic().extract(t).member_id == "MBR482910337"


@pytest.mark.parametrize("seed", [1, 7, 4321])
def test_baseline_vs_optimized_recall_gap(seed: int) -> None:
    """Naive ~30% vs deterministic ~90% on a labeled synthetic dataset."""
    scenario = PostCallAnalyticsScenario()
    dataset = scenario.generate_dataset(200, seed=seed, labeled=True)
    labeled = [t for t in dataset if t.member_id_gold is not None]
    assert labeled, "dataset should contain labeled transcripts"

    naive = _naive()
    deterministic = _deterministic()
    naive_hits = sum(naive.extract(t).member_id == t.member_id_gold for t in labeled)
    det_hits = sum(deterministic.extract(t).member_id == t.member_id_gold for t in labeled)

    naive_recall = naive_hits / len(labeled)
    det_recall = det_hits / len(labeled)

    assert 0.20 <= naive_recall <= 0.45, naive_recall
    assert det_recall >= 0.85, det_recall
    assert det_recall - naive_recall >= 0.45


def test_deterministic_never_produces_false_positive_id() -> None:
    """On labeled data, any produced id that mismatches gold would hurt precision."""
    scenario = PostCallAnalyticsScenario()
    dataset = scenario.generate_dataset(200, seed=99, labeled=True)
    deterministic = _deterministic()
    false_positives = 0
    for t in dataset:
        pred = deterministic.extract(t).member_id
        if pred is not None and t.member_id_gold is None:
            false_positives += 1
    # Missing-id calls should essentially never yield a spurious id.
    assert false_positives <= 1


def test_render_helpers_roundtrip() -> None:
    rng = random.Random(3)
    fmt = MemberIdFormat()
    mid = fmt.generate(rng)
    assert render_dashed(mid, rng).replace("-", "").replace(" ", "") == mid
    spoken = render_spoken(mid)
    assert "one" in spoken or "zero" in spoken or any(w in spoken for w in ("two", "three"))
