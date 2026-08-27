"""``aiwoa`` command-line interface.

Importing this module registers all scenarios, strategies, and evaluators via
their package import side effects, then mounts the Typer sub-applications.
"""

from __future__ import annotations

import typer

# Registration side effects: importing these populates the registries.
import evaluation  # noqa: F401
import optimization  # noqa: F401
import workloads  # noqa: F401
from cli.commands import benchmark, evaluate, report, scenario

app = typer.Typer(
    name="aiwoa",
    help="AI Workload Optimization Accelerator — benchmark and evaluate Azure AI workloads.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(scenario.app, name="scenario", help="Inspect workload scenarios.")
app.add_typer(benchmark.app, name="benchmark", help="Run performance benchmarks.")
app.add_typer(evaluate.app, name="evaluate", help="Run quality/regression evaluations.")
app.add_typer(report.app, name="report", help="Compare benchmark/evaluation results.")


if __name__ == "__main__":  # pragma: no cover
    app()
