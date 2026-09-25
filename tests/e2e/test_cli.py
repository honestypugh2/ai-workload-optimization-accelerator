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


def test_no_org_names_in_scenario_output() -> None:
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


def _bench(out: Path, *extra: str) -> None:
    result = runner.invoke(
        app,
        [
            "benchmark",
            "run",
            "--scenario",
            "post-call-analytics",
            "--config",
            "workload-scenarios/post-call-analytics/benchmarks/baseline-batch.yaml",
            "--output",
            str(out),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.stdout


def test_default_output_name_includes_execution_mode() -> None:
    from cli.commands.benchmark import _default_output

    local = _default_output("post-call-analytics", "current-state-azure", "local")
    live = _default_output("post-call-analytics", "current-state-azure", "azure")
    assert local.name == "current-state-azure.local.result.json"
    assert live.name == "current-state-azure.azure.result.json"


def test_mode_override_warns_and_is_recorded(tmp_path) -> None:
    out = tmp_path / "r.json"
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
            "--transcripts",
            "5",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0
    assert "overrides the config's execution_mode" in result.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["provenance"]["config_execution_mode"] == "local"
    assert payload["provenance"]["config_overrides"]["execution_mode"] == "dry-run"


def test_scorecard_refuses_mixed_volume_without_flag(tmp_path) -> None:
    full, smoke = tmp_path / "full.json", tmp_path / "smoke.json"
    _bench(full, "--transcripts", "40")
    _bench(smoke, "--transcripts", "5")

    refused = runner.invoke(
        app, ["report", "scorecard", "--run", f"full={full}", "--run", f"smoke={smoke}"]
    )
    assert refused.exit_code == 1
    assert "not comparable" in refused.stdout

    out = tmp_path / "scorecard.json"
    allowed = runner.invoke(
        app,
        [
            "report",
            "scorecard",
            "--run",
            f"full={full}",
            "--run",
            f"smoke={smoke}",
            "--allow-mixed",
            "--output",
            str(out),
        ],
    )
    assert allowed.exit_code == 0
    assert "MIXED COMPARISON" in allowed.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["mixed"] is True
    assert payload["provenance"][1]["transcripts"] == 5
    assert any(i["check"] == "transcripts" for i in payload["comparability_issues"])


def test_compare_refuses_mixed_modes_without_flag(tmp_path) -> None:
    local, dry = tmp_path / "local.json", tmp_path / "dry.json"
    _bench(local, "--transcripts", "10")
    _bench(dry, "--transcripts", "10", "--mode", "dry-run")

    args = ["report", "compare", "--baseline", str(local), "--candidate", str(dry)]
    refused = runner.invoke(app, args)
    assert refused.exit_code == 1
    assert "execution_mode" in refused.stdout

    allowed = runner.invoke(app, [*args, "--allow-mixed"])
    assert allowed.exit_code == 0
    assert "MIXED" in allowed.stdout


def test_compare_like_for_like_runs_succeeds(tmp_path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    _bench(a, "--transcripts", "10")
    _bench(b, "--transcripts", "10")
    result = runner.invoke(app, ["report", "compare", "--baseline", str(a), "--candidate", str(b)])
    assert result.exit_code == 0
    assert "not comparable" not in result.stdout
