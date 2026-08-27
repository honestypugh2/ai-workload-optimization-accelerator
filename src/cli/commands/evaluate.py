"""``aiwoa evaluate`` commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from evaluation import EvaluationResult, run_evaluation_file
from shared.exceptions import AcceleratorError

app = typer.Typer(no_args_is_help=True, add_completion=False)
_console = Console()


def _default_output(scenario: str, name: str) -> Path:
    slug = name.replace(" ", "-").lower()
    return Path("workload-scenarios") / scenario / "reports" / f"{slug}.eval.json"


def _print_summary(result: EvaluationResult) -> None:
    table = Table(title=f"Evaluation: {result.name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")
    for metric, value in sorted(result.metrics.items()):
        table.add_row(metric, f"{value:.4f}")
    _console.print(table)

    if result.thresholds:
        gate = Table(title="Release gate")
        gate.add_column("Metric", style="cyan")
        gate.add_column("Rule")
        gate.add_column("Actual", justify="right")
        gate.add_column("Pass", justify="center")
        for outcome in result.thresholds:
            gate.add_row(
                outcome.metric,
                f"{outcome.op} {outcome.threshold}",
                f"{outcome.actual:.4f}",
                "[green]PASS[/green]" if outcome.passed else "[red]FAIL[/red]",
            )
        _console.print(gate)

    verdict = "[green]PASSED[/green]" if result.gate_passed else "[red]FAILED[/red]"
    _console.print(f"Release gate: {verdict}")


@app.command("run")
def run(
    scenario: str = typer.Option(..., "--scenario", help="Scenario name."),
    config: Path = typer.Option(..., "--config", help="Evaluation config YAML path."),
    output: Path | None = typer.Option(None, "--output", help="Result JSON output path."),
) -> None:
    """Run an evaluation configuration and write a JSON result."""
    try:
        result = run_evaluation_file(config)
    except AcceleratorError as exc:
        _console.print(f"[red]Evaluation failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    out_path = output or _default_output(result.scenario, result.name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    _print_summary(result)
    _console.print(f"[dim]Result written to {out_path}[/dim]")

    if not result.gate_passed:
        raise typer.Exit(code=2)
