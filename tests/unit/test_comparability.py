"""Unit tests for benchmark-result comparability checks."""

from __future__ import annotations

from reporting import RunMeta, ScorecardRun, build_scorecard, check_comparability, has_blocking


def _meta(**overrides) -> RunMeta:
    base = {
        "execution_mode": "local",
        "execution_backend": "local",
        "transcripts": 7000,
        "schema_version": 2,
        "throttling_source": "modeled",
        "timing_source": "modeled",
        "cost_extrapolated": False,
        "model_deployments": {"baseline": "mock:baseline"},
    }
    base.update(overrides)
    return RunMeta(**base)


def test_like_for_like_runs_have_no_issues() -> None:
    issues = check_comparability([("a", _meta()), ("b", _meta())])
    assert issues == []


def test_mode_backend_and_source_mismatch_is_blocking() -> None:
    live = _meta(
        execution_mode="azure",
        execution_backend="direct",
        throttling_source="observed",
        timing_source="observed",
        model_deployments={"small": "gpt-nano"},
    )
    issues = check_comparability([("current", _meta()), ("option-b", live)])
    checks = {i.check for i in issues if i.blocking}
    assert {"execution_mode", "execution_backend", "throttling_source"} <= checks
    assert has_blocking(issues)
    assert all(i.label == "option-b" for i in issues if i.blocking)


def test_volume_ratio_beyond_limit_is_blocking() -> None:
    issues = check_comparability([("full", _meta()), ("smoke", _meta(transcripts=25))])
    assert [i.check for i in issues if i.blocking] == ["transcripts"]


def test_volume_ratio_within_limit_is_allowed() -> None:
    issues = check_comparability(
        [("a", _meta(transcripts=300)), ("b", _meta(transcripts=500))], max_volume_ratio=2.0
    )
    assert not has_blocking(issues)


def test_legacy_live_result_gets_caveats_not_blocks() -> None:
    legacy = RunMeta.from_result(
        {
            "execution_mode": "azure",
            "execution_backend": "direct",
            "metrics": {"transcripts": 7000},
        }
    )
    assert legacy.is_legacy
    assert legacy.throttling_source == "modeled"
    issues = check_comparability([("legacy", legacy)])
    checks = {i.check for i in issues}
    assert {"provenance", "throttling_source"} <= checks
    assert not has_blocking(issues)


def test_single_live_deployment_for_tiered_aliases_is_a_caveat() -> None:
    meta = _meta(
        execution_mode="azure",
        execution_backend="direct",
        throttling_source="observed",
        model_deployments={"small": "gpt-nano", "medium": "gpt-nano"},
    )
    issues = check_comparability([("b", meta)])
    assert [i.check for i in issues] == ["model_deployments"]


def test_mode_override_is_a_caveat() -> None:
    meta = RunMeta.from_result(
        {
            "schema_version": 2,
            "execution_mode": "local",
            "execution_backend": "local",
            "metrics": {"transcripts": 7000, "daily_volume": 7000},
            "provenance": {"config_execution_mode": "azure"},
        }
    )
    issues = check_comparability([("x", meta)])
    assert [i.check for i in issues] == ["mode_override"]


def test_evaluation_only_runs_are_ignored() -> None:
    issues = check_comparability([("a", _meta()), ("eval", None), ("b", _meta())])
    assert issues == []


def test_scorecard_exposes_issues_and_mixed_flag() -> None:
    runs = [
        ScorecardRun(label="full", benchmark={"cost_per_day": 1.0}, meta=_meta()),
        ScorecardRun(label="smoke", benchmark={"cost_per_day": 2.0}, meta=_meta(transcripts=25)),
    ]
    card = build_scorecard(runs)
    assert card.is_mixed
    assert any(i.check == "transcripts" for i in card.issues)
