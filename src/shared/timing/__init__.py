"""Elapsed-time clock that is accurate on hosts with a mis-disciplined monotonic clock.

``time.perf_counter()`` is ``CLOCK_MONOTONIC`` on Linux, which the kernel
frequency-adjusts for time sync. On some virtualized hosts (observed on WSL2 on
ARM64) that adjustment is badly wrong: ``CLOCK_MONOTONIC`` ran ~10% fast against
server time, inflating every measured latency and wall-clock duration by the same
factor. ``CLOCK_MONOTONIC_RAW`` reads the hardware counter without that
adjustment, stays within ppm of true time on healthy hosts, and was accurate on
the affected host, so it is preferred wherever the platform provides it.
"""

from __future__ import annotations

import time

_RAW_CLOCK: int | None = getattr(time, "CLOCK_MONOTONIC_RAW", None)


def monotonic_seconds() -> float:
    """Seconds from an arbitrary origin, for measuring elapsed durations only."""
    if _RAW_CLOCK is not None:
        return time.clock_gettime(_RAW_CLOCK)
    return time.perf_counter()


def clock_name() -> str:
    """Name of the clock backing :func:`monotonic_seconds`, for run provenance."""
    return "CLOCK_MONOTONIC_RAW" if _RAW_CLOCK is not None else "perf_counter"


__all__ = ["clock_name", "monotonic_seconds"]
