"""``aiwoa benchmark`` commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from benchmarking import BenchmarkResult
from benchmarking.api import run_benchmark
from shared.configuration import load_benchmark_config
from shared.exceptions import AcceleratorError
from shared.types import ExecutionMode

app = typer.Typer(no_args_is_help=True, add_completion=False)
_console = Console()


def _default_output(scenario: str, name: str) -> Path:
    slug = name.replace(" ", "-").lower()
    return Path("workload-scenarios") / scenario / "reports" / f"{slug}.result.json"


def _print_summary(result: BenchmarkResult) -> None:
    m = result.metrics
    table = Table(title=f"Benchmark: {result.name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")
    rows = [
        ("Strategy", result.strategy),
        ("Routing", result.routing),
        ("Transcripts", str(m.transcripts)),
        ("Transcripts/min", f"{m.transcripts_per_minute:.2f}"),
        ("Effective TPM", f"{m.effective_tokens_per_minute:,.0f}"),
        (
            "p50 / p95 / p99 (ms)",
            f"{m.p50_latency_ms:.1f} / {m.p95_latency_ms:.1f} / {m.p99_latency_ms:.1f}",
        ),
        ("Input tokens", f"{m.total_input_tokens:,}"),
        ("Output tokens", f"{m.total_output_tokens:,}"),
        ("Avg tokens/transcript", f"{m.average_tokens_per_transcript:,.0f}"),
        (f"Cost/day ({result.currency})", f"{m.cost_per_day:,.2f}"),
        (f"Cost/month ({result.currency})", f"{m.cost_per_month:,.2f}"),
        ("HTTP 429 rate", f"{m.http_429_rate:.1%}"),
        ("Retries", str(m.retry_count)),
        ("Cache hit rate", f"{m.cache_hit_rate:.1%}"),
        ("Queue depth", str(m.workload_queue_depth)),
    ]
    for label, value in rows:
        table.add_row(label, value)
    _console.print(table)


@app.command("run")
def run(
    scenario: str = typer.Option(..., "--scenario", help="Scenario name."),
    config: Path = typer.Option(..., "--config", help="Benchmark config YAML path."),
    output: Path | None = typer.Option(None, "--output", help="Result JSON output path."),
    transcripts: int | None = typer.Option(
        None,
        "--transcripts",
        help="Override the config's transcript_count (e.g. for smoke vs full-scale runs).",
        min=1,
    ),
    mode: ExecutionMode | None = typer.Option(
        None,
        "--mode",
        help="Override execution_mode (local, dry-run, azure). azure makes real Foundry calls.",
    ),
    concurrency: int | None = typer.Option(
        None,
        "--concurrency",
        help="Override max_concurrency: transcripts processed in parallel (I/O overlap in azure).",
        min=1,
    ),
) -> None:
    """Run a benchmark configuration and write a JSON result."""
    try:
        cfg = load_benchmark_config(config)
        overrides: dict[str, object] = {}
        if transcripts is not None:
            overrides["transcript_count"] = transcripts
        if mode is not None:
            overrides["execution_mode"] = mode.value
        if concurrency is not None:
            overrides["max_concurrency"] = concurrency
        if overrides:
            cfg = cfg.model_copy(update=overrides)
        result = run_benchmark(cfg)
    except AcceleratorError as exc:
        _console.print(f"[red]Benchmark failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if result.scenario != scenario:
        _console.print(
            f"[yellow]Warning: --scenario '{scenario}' differs from config "
            f"scenario '{result.scenario}'.[/yellow]"
        )

    out_path = output or _default_output(result.scenario, result.name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    _print_summary(result)
    _console.print(f"[dim]Result written to {out_path}[/dim]")
