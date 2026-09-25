"""Public benchmarking API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from benchmarking.application import BenchmarkRunner
from benchmarking.domain import BenchmarkMetrics, BenchmarkResult
from shared.configuration import BenchmarkConfig, load_benchmark_config

__all__ = [
    "BenchmarkConfig",
    "BenchmarkMetrics",
    "BenchmarkResult",
    "BenchmarkRunner",
    "run_benchmark",
    "run_benchmark_file",
]


def run_benchmark(
    config: BenchmarkConfig,
    *,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    config_execution_mode: str | None = None,
) -> BenchmarkResult:
    """Run a benchmark from a validated configuration object."""
    return BenchmarkRunner().run(
        config,
        config_path=config_path,
        overrides=overrides,
        config_execution_mode=config_execution_mode,
    )


def run_benchmark_file(path: str | Path) -> BenchmarkResult:
    """Load a benchmark configuration file and run it."""
    config = load_benchmark_config(path)
    return run_benchmark(config, config_path=path, config_execution_mode=config.execution_mode)
