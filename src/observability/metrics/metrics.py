"""In-memory metric collection used by the benchmark harness."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from types import TracebackType


@dataclass
class MetricSink:
    """Accumulates counters and value samples during a run."""

    counters: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    samples: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def incr(self, name: str, amount: float = 1.0) -> None:
        self.counters[name] += amount

    def observe(self, name: str, value: float) -> None:
        self.samples[name].append(value)

    def percentile(self, name: str, pct: float) -> float:
        values = sorted(self.samples.get(name, []))
        if not values:
            return 0.0
        k = (len(values) - 1) * (pct / 100.0)
        lo = int(k)
        hi = min(lo + 1, len(values) - 1)
        frac = k - lo
        return values[lo] + (values[hi] - values[lo]) * frac

    def mean(self, name: str) -> float:
        values = self.samples.get(name, [])
        return sum(values) / len(values) if values else 0.0


class Timer:
    """Context manager measuring wall-clock milliseconds."""

    def __init__(self) -> None:
        self.elapsed_ms: float = 0.0
        self._start: float = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0
