"""``aiwoa report`` commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from evaluation import compare_results
from reporting import ScorecardRow, build_scorecard, load_run
from shared.configuration import load_scorecard_config

app = typer.Typer(no_args_is_help=True, add_completion=False)
_console = Console()


def _load_metrics(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    metrics = data.get("metrics", {})
    # Keep only numeric metrics; benchmark utilization is a nested dict.
    return {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))}


@app.command("compare")
def compare(
    baseline: Path = typer.Option(..., "--baseline", help="Baseline result JSON path."),
    candidate: Path = typer.Option(..., "--candidate", help="Candidate result JSON path."),
) -> None:
    """Compare two benchmark or evaluation result files metric-by-metric."""
    if not baseline.exists() or not candidate.exists():
        _console.print("[red]Both --baseline and --candidate files must exist.[/red]")
        raise typer.Exit(code=1)

    comparison = compare_results(_load_metrics(baseline), _load_metrics(candidate))

    table = Table(title="Baseline vs candidate")
    table.add_column("Metric", style="cyan")
    table.add_column("Baseline", justify="right")
    table.add_column("Candidate", justify="right")
    table.add_column("Delta", justify="right")
    for metric, values in comparison.items():
        delta = values["delta"]
        style = "green" if delta >= 0 else "red"
        table.add_row(
            metric,
            f"{values['baseline']:.4f}",
            f"{values['candidate']:.4f}",
            f"[{style}]{delta:+.4f}[/{style}]",
        )
    _console.print(table)


def _parse_run(spec: str) -> tuple[str, str | None, str | None]:
    """Parse a ``LABEL=BENCH[::EVAL]`` run specification."""
    if "=" not in spec:
        raise typer.BadParameter(f"Run '{spec}' must be 'LABEL=benchmark.json[::evaluation.json]'.")
    label, _, paths = spec.partition("=")
    bench_part, _, eval_part = paths.partition("::")
    bench = bench_part.strip() or None
    evaluation = eval_part.strip() or None
    if bench is None and evaluation is None:
        raise typer.BadParameter(f"Run '{label}' has no benchmark or evaluation file.")
    return label.strip(), bench, evaluation


def _runs_from_config(config: Path):
    """Load scorecard runs from a YAML config, resolving paths relative to it."""
    from reporting import ScorecardRun

    cfg = load_scorecard_config(config)
    base = config.resolve().parent

    def _resolve(rel: str | None) -> Path | None:
        if rel is None:
            return None
        p = Path(rel)
        return p if p.is_absolute() else base / p

    scorecard_runs: list[ScorecardRun] = []
    for spec in cfg.runs:
        scorecard_runs.append(
            load_run(
                spec.label,
                benchmark_path=_resolve(spec.benchmark),
                evaluation_path=_resolve(spec.evaluation),
            )
        )
    return scorecard_runs


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "$":
        return f"${value:,.4f}" if abs(value) < 1 else f"${value:,.2f}"
    if unit == "rate":
        return f"{value:.1%}"
    if unit in {"ms", "s", "tok", "tok/min", "tx/min"}:
        return f"{value:,.1f}"
    return f"{value:,.0f}" if value == int(value) else f"{value:,.2f}"


def _delta_cell(row: ScorecardRow) -> str:
    if row.delta is None or len(row.values) < 2:
        return ""
    improved = row.improved
    style = "green" if improved else ("red" if improved is False else "white")
    arrow = "▲" if row.delta > 0 else ("▼" if row.delta < 0 else "•")
    return f"[{style}]{arrow} {row.delta:+,.2f}[/{style}]"


@app.command("scorecard")
def scorecard(
    runs: list[str] = typer.Option(
        [],
        "--run",
        "-r",
        help="Run as 'LABEL=benchmark.json[::evaluation.json]'. Repeat for each run. "
        "The first run is the baseline for delta comparison.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Scorecard YAML listing labelled runs (alternative to repeating --run). "
        "Result paths are resolved relative to the config file.",
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Optional JSON path to write the combined scorecard."
    ),
) -> None:
    """Combined operations + cost + quality scorecard across runs, side by side."""
    if config is not None:
        scorecard_runs = _runs_from_config(config)
    elif runs:
        parsed = [_parse_run(spec) for spec in runs]
        scorecard_runs = [
            load_run(label, benchmark_path=bench, evaluation_path=ev) for label, bench, ev in parsed
        ]
    else:
        _console.print("[red]Provide either --config or at least one --run.[/red]")
        raise typer.Exit(code=1)
    card = build_scorecard(scorecard_runs)

    if not card.rows:
        _console.print("[yellow]No comparable metrics found across the provided runs.[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title="Ops + Cost + Quality scorecard", show_lines=False)
    table.add_column("Metric", style="cyan", no_wrap=True)
    for run in card.runs:
        table.add_column(run.label, justify="right")
    if len(card.runs) > 1:
        table.add_column("Δ vs baseline", justify="right")

    for category in ("Operations", "Cost", "Quality"):
        rows = card.rows_for(category)
        if not rows:
            continue
        table.add_section()
        table.add_row(f"[bold]{category}[/bold]", *([""] * (len(card.runs))))
        for row in rows:
            cells = [_fmt(v, row.spec.unit) for v in row.values]
            label = f"  {row.spec.label}"
            if len(card.runs) > 1:
                table.add_row(label, *cells, _delta_cell(row))
            else:
                table.add_row(label, *cells)
    _console.print(table)

    if output is not None:
        payload = {
            "runs": [run.label for run in card.runs],
            "rows": [
                {
                    "metric": row.spec.key,
                    "label": row.spec.label,
                    "category": row.spec.category,
                    "unit": row.spec.unit,
                    "higher_is_better": row.spec.higher_is_better,
                    "values": list(row.values),
                    "delta": row.delta,
                    "improved": row.improved,
                }
                for row in card.rows
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        _console.print(f"[dim]Scorecard written to {output}[/dim]")
