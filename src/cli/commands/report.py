"""``aiwoa report`` commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from evaluation import compare_results
from reporting import (
    DEFAULT_MAX_VOLUME_RATIO,
    ComparabilityIssue,
    RunMeta,
    ScorecardRow,
    ScorecardRun,
    build_scorecard,
    check_comparability,
    has_blocking,
    load_run,
)
from shared.configuration import load_scorecard_config

app = typer.Typer(no_args_is_help=True, add_completion=False)
_console = Console()

_ALLOW_MIXED_HELP = (
    "Proceed even when runs differ in execution mode, backend, throttling source, or "
    "volume. The output is labelled as a mixed comparison."
)
_VOLUME_RATIO_HELP = "Largest transcript-count ratio vs the baseline treated as comparable."


def _load_result(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _numeric_metrics(data: dict) -> dict[str, float]:
    metrics = data.get("metrics", {})
    # Keep only numeric metrics; benchmark utilization is a nested dict. bool is an
    # int subclass, so exclude flags such as cost_extrapolated from the diff.
    return {
        k: float(v)
        for k, v in metrics.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def _meta_or_none(data: dict) -> RunMeta | None:
    """Benchmark results carry execution provenance; evaluation results do not."""
    return RunMeta.from_result(data) if "execution_mode" in data else None


def _print_issues(
    issues: list[ComparabilityIssue], *, allow_mixed: bool, run_labels: list[str] | None = None
) -> None:
    if not issues:
        return
    blocking = [i for i in issues if i.blocking]
    caveats = [i for i in issues if not i.blocking]
    if blocking:
        style = "yellow" if allow_mixed else "red"
        heading = (
            "MIXED COMPARISON (--allow-mixed): these runs are not like-for-like"
            if allow_mixed
            else "Runs are not comparable"
        )
        _console.print(f"[bold {style}]{heading}:[/bold {style}]")
        for issue in blocking:
            _console.print(f"[{style}]  ✗ {issue.label}: {issue.message}[/{style}]")
    if caveats:
        # Collapse a caveat shared by several runs into one line.
        grouped: dict[str, list[str]] = {}
        for issue in caveats:
            grouped.setdefault(issue.message, []).append(issue.label)
        _console.print("[bold]Caveats:[/bold]")
        for message, labels in grouped.items():
            everyone = run_labels is not None and len(labels) > 1 and set(labels) >= set(run_labels)
            who = "all runs" if everyone else ", ".join(labels)
            _console.print(f"[dim]  • {who}: {message}[/dim]")


def _abort_if_mixed(issues: list[ComparabilityIssue], *, allow_mixed: bool) -> None:
    if has_blocking(issues) and not allow_mixed:
        _console.print(
            "[red]Refusing to compare. Re-run the benchmarks with the same --mode, backend, "
            "and --transcripts, or pass --allow-mixed to override.[/red]"
        )
        raise typer.Exit(code=1)


@app.command("compare")
def compare(
    baseline: Path = typer.Option(..., "--baseline", help="Baseline result JSON path."),
    candidate: Path = typer.Option(..., "--candidate", help="Candidate result JSON path."),
    allow_mixed: bool = typer.Option(False, "--allow-mixed", help=_ALLOW_MIXED_HELP),
    max_volume_ratio: float = typer.Option(
        DEFAULT_MAX_VOLUME_RATIO, "--max-volume-ratio", min=1.0, help=_VOLUME_RATIO_HELP
    ),
) -> None:
    """Compare two benchmark or evaluation result files metric-by-metric."""
    if not baseline.exists() or not candidate.exists():
        _console.print("[red]Both --baseline and --candidate files must exist.[/red]")
        raise typer.Exit(code=1)

    base_data, cand_data = _load_result(baseline), _load_result(candidate)
    issues = check_comparability(
        [("baseline", _meta_or_none(base_data)), ("candidate", _meta_or_none(cand_data))],
        max_volume_ratio=max_volume_ratio,
    )
    _print_issues(issues, allow_mixed=allow_mixed)
    _abort_if_mixed(issues, allow_mixed=allow_mixed)

    comparison = compare_results(_numeric_metrics(base_data), _numeric_metrics(cand_data))

    title = "Baseline vs candidate" + (" (MIXED)" if has_blocking(issues) else "")
    table = Table(title=title)
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


def _runs_from_config(config: Path) -> list[ScorecardRun]:
    """Load scorecard runs from a YAML config, resolving paths relative to it."""
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


def _add_provenance_rows(table: Table, runs: tuple[ScorecardRun, ...]) -> None:
    """Show how each column was produced, above the metrics it qualifies."""
    metas = [run.meta for run in runs]
    if not any(metas):
        return

    def cells(render) -> list[str]:
        return [render(m) if m else "—" for m in metas]

    trailing = [""] if len(runs) > 1 else []
    table.add_row("[bold]Provenance[/bold]", *([""] * len(runs)), *trailing)
    table.add_row(
        "  Mode / backend",
        *cells(lambda m: f"{m.execution_mode} / {m.execution_backend}"),
        *trailing,
    )
    table.add_row(
        "  Transcripts",
        *cells(lambda m: f"{m.transcripts:,}" if m.transcripts else "?"),
        *trailing,
    )
    table.add_row("  429 / timing source", *cells(lambda m: m.throttling_source or "?"), *trailing)
    table.add_row(
        "  Cost extrapolated",
        *cells(lambda m: "yes" if m.cost_extrapolated else "no"),
        *trailing,
    )
    table.add_row(
        "  Deployments",
        *cells(
            lambda m: (
                ", ".join(sorted(set(m.model_deployments.values())))
                if m.model_deployments
                else "unrecorded"
            )
        ),
        *trailing,
    )


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
    allow_mixed: bool = typer.Option(False, "--allow-mixed", help=_ALLOW_MIXED_HELP),
    max_volume_ratio: float = typer.Option(
        DEFAULT_MAX_VOLUME_RATIO, "--max-volume-ratio", min=1.0, help=_VOLUME_RATIO_HELP
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
    card = build_scorecard(scorecard_runs, max_volume_ratio=max_volume_ratio)
    issues = list(card.issues)
    benchmark_labels = [run.label for run in card.runs if run.meta is not None]
    _print_issues(issues, allow_mixed=allow_mixed, run_labels=benchmark_labels)
    _abort_if_mixed(issues, allow_mixed=allow_mixed)

    if not card.rows:
        _console.print("[yellow]No comparable metrics found across the provided runs.[/yellow]")
        raise typer.Exit(code=1)

    title = "Ops + Cost + Quality scorecard" + (" — MIXED COMPARISON" if card.is_mixed else "")
    table = Table(title=title, show_lines=False)
    table.add_column("Metric", style="cyan", no_wrap=True)
    for run in card.runs:
        table.add_column(run.label, justify="right")
    if len(card.runs) > 1:
        table.add_column("Δ vs baseline", justify="right")

    _add_provenance_rows(table, card.runs)
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
            "mixed": card.is_mixed,
            "provenance": [run.meta.to_dict() if run.meta else None for run in card.runs],
            "comparability_issues": [issue.to_dict() for issue in card.issues],
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
