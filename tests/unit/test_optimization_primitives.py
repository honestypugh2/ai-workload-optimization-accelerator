"""Preprocessing, caching, and PTU-simulation tests."""

from __future__ import annotations

from optimization.caching import (
    CacheBundle,
    ContentCache,
    IncrementalProcessor,
    SemanticCache,
)
from optimization.preprocessing import normalize_spoken_digits, redact_pii
from optimization.ptu_simulation import (
    PtuSizingInput,
    compare_ptu_vs_standard,
    size_ptus,
)


def test_normalize_spoken_digits_joins_runs() -> None:
    assert "771043928" in normalize_spoken_digits("seven seven one zero four three nine two eight")


def test_normalize_spoken_digits_leaves_plain_text() -> None:
    assert normalize_spoken_digits("hello world") == "hello world"


def test_content_cache_hit_rate() -> None:
    cache: ContentCache[str] = ContentCache(enabled=True)
    assert cache.get("k") is None  # miss
    cache.put("k", "v")
    assert cache.get("k") == "v"  # hit
    assert cache.hit_rate == 0.5


def test_disabled_cache_never_hits() -> None:
    cache: ContentCache[str] = ContentCache(enabled=False)
    cache.put("k", "v")
    assert cache.get("k") is None


def test_cache_bundle_from_flags_enables_named_caches() -> None:
    bundle = CacheBundle.from_flags(["prompt"])
    assert bundle.prompt_cache.enabled is True
    assert bundle.result_cache.enabled is False


def test_semantic_cache_collides_near_duplicates() -> None:
    cache: SemanticCache[str] = SemanticCache(enabled=True)
    cache.put("Refund the Charge!", "v")
    assert cache.get("refund   the charge") == "v"  # casing/punctuation/space ignored


def test_cache_bundle_enables_semantic_and_incremental() -> None:
    bundle = CacheBundle.from_flags(["semantic", "incremental"])
    assert bundle.semantic_cache.enabled is True
    assert bundle.incremental.enabled is True
    assert bundle.prompt_cache.enabled is False


def test_incremental_processor_skips_repeats() -> None:
    watermark = IncrementalProcessor(enabled=True)
    assert watermark.should_process("t1") is True
    assert watermark.should_process("t1") is False  # already seen
    assert watermark.should_process("t2") is True
    assert watermark.skip_rate == 1 / 3


def test_incremental_processor_disabled_never_skips() -> None:
    watermark = IncrementalProcessor(enabled=False)
    assert watermark.should_process("t1") is True
    assert watermark.should_process("t1") is True
    assert watermark.skip_rate == 0.0


def test_redact_pii_masks_structured_identifiers() -> None:
    redacted = redact_pii("ssn 123-45-6789 call 555-867-5309 mail a@b.com")
    assert "[SSN]" in redacted
    assert "[PHONE]" in redacted
    assert "[EMAIL]" in redacted
    assert "123-45-6789" not in redacted


def test_size_ptus_rounds_up_to_meet_peak() -> None:
    result = size_ptus(
        PtuSizingInput(
            peak_tokens_per_minute=300_000,
            tokens_per_minute_per_ptu=50_000,
            utilization_target=0.75,
        )
    )
    assert result.required_ptus >= 8
    assert result.effective_capacity_tpm >= 300_000
    assert result.headroom_tpm >= 0


def test_compare_ptu_vs_standard_picks_cheaper() -> None:
    comparison = compare_ptu_vs_standard(
        required_ptus=10,
        ptu_monthly_price_per_unit=1000.0,
        monthly_tokens=1_000_000_000,
        standard_price_per_1k=0.05,
    )
    assert comparison.cheaper_option in {"ptu", "standard"}
    assert comparison.monthly_savings >= 0
