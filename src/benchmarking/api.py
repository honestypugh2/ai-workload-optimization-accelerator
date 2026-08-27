"""Public benchmarking API."""

from __future__ import annotations

from pathlib import Path

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


def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """Run a benchmark from a validated configuration object."""
    return BenchmarkRunner().run(config)


def run_benchmark_file(path: str | Path) -> BenchmarkResult:
    """Load a benchmark configuration file and run it."""
    return run_benchmark(load_benchmark_config(path))
