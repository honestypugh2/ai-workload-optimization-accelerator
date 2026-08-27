"""Unit tests for the combined ops + cost + quality scorecard."""

from __future__ import annotations

import json
from pathlib import Path

from reporting import ScorecardRun, build_scorecard, load_run


def _make_runs() -> list[ScorecardRun]:
    baseline = ScorecardRun(
        label="current-state",
        benchmark={
            "batch_completion_seconds": 44400.0,
            "cost_per_month": 811.66,
            "http_429_rate": 0.0196,
            "average_tokens_per_transcript": 24137.0,
        },
        evaluation={"member_id_recall": 0.31},
    )
    optimized = ScorecardRun(
        label="optimized",
        benchmark={
            "batch_completion_seconds": 7020.0,
            "cost_per_month": 411.70,
            "http_429_rate": 0.0027,
            "average_tokens_per_transcript": 11705.0,
        },
        evaluation={"member_id_recall": 0.93},
    )
    return [baseline, optimized]


def test_build_scorecard_keeps_present_metrics() -> None:
    card = build_scorecard(_make_runs())
    keys = {row.spec.key for row in card.rows}
    assert "cost_per_month" in keys
    assert "member_id_recall" in keys
    # Metrics absent from every run are dropped.
    assert "cache_hit_rate" not in keys


def test_build_scorecard_drops_all_missing_metric() -> None:
    runs = [ScorecardRun(label="a", benchmark={"cost_per_month": 10.0})]
    card = build_scorecard(runs)
    assert all(row.spec.key != "member_id_recall" for row in card.rows)


def test_delta_and_improved_direction() -> None:
    card = build_scorecard(_make_runs())
    rows = {row.spec.key: row for row in card.rows}

    # Cost is lower-is-better: a drop is an improvement.
    cost = rows["cost_per_month"]
    assert cost.delta is not None and cost.delta < 0
    assert cost.improved is True

    # Recall is higher-is-better: a rise is an improvement.
    recall = rows["member_id_recall"]
    assert recall.delta is not None and recall.delta > 0
    assert recall.improved is True

    # 429 rate lower-is-better.
    throttle = rows["http_429_rate"]
    assert throttle.improved is True


def test_categories_partition_rows() -> None:
    card = build_scorecard(_make_runs())
    ops = card.rows_for("Operations")
    cost = card.rows_for("Cost")
    quality = card.rows_for("Quality")
    assert {r.spec.key for r in cost} == {
        r.spec.key for r in card.rows if r.spec.category == "Cost"
    }
    assert ops and cost and quality


def test_load_run_reads_benchmark_and_evaluation(tmp_path: Path) -> None:
    bench = tmp_path / "b.json"
    bench.write_text(
        json.dumps({"metrics": {"cost_per_month": 100.0, "deployment_utilization": {"x": 0.5}}}),
        encoding="utf-8",
    )
    ev = tmp_path / "e.json"
    ev.write_text(json.dumps({"metrics": {"member_id_recall": 0.9}}), encoding="utf-8")

    run = load_run("r1", benchmark_path=bench, evaluation_path=ev)
    assert run.benchmark["cost_per_month"] == 100.0
    # Nested/non-numeric metrics are skipped.
    assert "deployment_utilization" not in run.benchmark
    assert run.evaluation["member_id_recall"] == 0.9
