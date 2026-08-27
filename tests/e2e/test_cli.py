"""End-to-end CLI tests via the Typer test runner."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_scenario_list_shows_registered_scenario() -> None:
    result = runner.invoke(app, ["scenario", "list"])
    assert result.exit_code == 0
    assert "post-call-analytics" in result.stdout


def test_scenario_show_displays_config() -> None:
    result = runner.invoke(app, ["scenario", "show", "post-call-analytics"])
    assert result.exit_code == 0


def test_benchmark_run_writes_report(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "benchmark",
            "run",
            "--scenario",
            "post-call-analytics",
            "--config",
            "workload-scenarios/post-call-analytics/benchmarks/baseline-batch.yaml",
        ],
    )
    assert result.exit_code == 0
    assert "baseline-batch" in result.stdout


def test_evaluate_run_passes_gate() -> None:
    result = runner.invoke(
        app,
        [
            "evaluate",
            "run",
            "--scenario",
            "post-call-analytics",
            "--config",
            "workload-scenarios/post-call-analytics/evaluations/member-id.yaml",
        ],
    )
    assert result.exit_code == 0


def test_evaluate_regression_gate_uses_naive_baseline() -> None:
    result = runner.invoke(
        app,
        [
            "evaluate",
            "run",
            "--scenario",
            "post-call-analytics",
            "--config",
            "workload-scenarios/post-call-analytics/evaluations/regression.yaml",
        ],
    )
    assert result.exit_code == 0


def test_no_customer_names_in_scenario_output() -> None:
    result = runner.invoke(app, ["scenario", "list"])
    lowered = result.stdout.lower()
    assert "geha" not in lowered
    assert "umr" not in lowered


def test_benchmark_run_mode_and_concurrency_overrides(tmp_path) -> None:
    out = tmp_path / "result.json"
    result = runner.invoke(
        app,
        [
            "benchmark",
            "run",
            "--scenario",
            "post-call-analytics",
            "--config",
            "workload-scenarios/post-call-analytics/benchmarks/baseline-batch.yaml",
            "--mode",
            "dry-run",
            "--concurrency",
            "4",
            "--transcripts",
            "12",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    # --mode and --transcripts overrides are reflected in the written result.
    assert payload["execution_mode"] == "dry-run"
    assert payload["metrics"]["transcripts"] == 12


def _run_benchmark_to(config_name: str, out: Path) -> None:
    result = runner.invoke(
        app,
        [
            "benchmark",
            "run",
            "--scenario",
            "post-call-analytics",
            "--config",
            f"workload-scenarios/post-call-analytics/benchmarks/{config_name}",
            "--transcripts",
            "12",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0


def test_report_scorecard_from_config(tmp_path) -> None:
    reports = tmp_path / "reports"
    scorecards = tmp_path / "scorecards"
    reports.mkdir()
    scorecards.mkdir()
    _run_benchmark_to("baseline-batch.yaml", reports / "current-state.result.json")
    _run_benchmark_to("token-optimization.yaml", reports / "optimized.result.json")

    config = scorecards / "sc.yaml"
    config.write_text(
        "name: sc\n"
        "runs:\n"
        "  - label: current-state\n"
        "    benchmark: ../reports/current-state.result.json\n"
        "  - label: optimized\n"
        "    benchmark: ../reports/optimized.result.json\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["report", "scorecard", "--config", str(config)])
    assert result.exit_code == 0
    assert "current-state" in result.stdout
    assert "optimized" in result.stdout


def test_report_scorecard_requires_runs_or_config() -> None:
    result = runner.invoke(app, ["report", "scorecard"])
    assert result.exit_code == 1
