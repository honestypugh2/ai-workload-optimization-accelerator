"""``aiwoa scenario`` commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from registry.scenario_registry import scenario_registry

app = typer.Typer(no_args_is_help=True, add_completion=False)
_console = Console()


@app.command("list")
def list_scenarios() -> None:
    """List all registered workload scenarios."""
    table = Table(title="Registered workload scenarios")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Display name", style="green")

    for name, cls in sorted(scenario_registry.items()):
        display = getattr(cls, "display_name", name)
        table.add_row(name, display)

    if not scenario_registry.names():
        _console.print("[yellow]No scenarios are registered.[/yellow]")
        raise typer.Exit(code=0)

    _console.print(table)


@app.command("show")
def show_scenario(name: str = typer.Argument(..., help="Scenario name.")) -> None:
    """Show a scenario's configuration summary."""
    try:
        scenario = scenario_registry.get(name)()
    except KeyError as exc:
        _console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    config = scenario.load_config()
    _console.print(f"[bold]{config.display_name}[/bold] ({config.name})")
    _console.print(config.description)
    _console.print(f"Expected outputs: {', '.join(config.expected_outputs)}")
    _console.print(f"Optimization variants: {', '.join(config.optimization_variants)}")
    profile = config.dataset_profile
    _console.print(
        f"Dataset profile: {profile.target_daily_volume} transcripts/day, "
        f"~{profile.average_token_count} tokens avg, "
        f"baseline extraction {profile.baseline_extraction_success:.0%}"
    )
