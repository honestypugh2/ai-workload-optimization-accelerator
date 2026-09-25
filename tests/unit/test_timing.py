"""Tests for the elapsed-time clock used by providers and the benchmark runner."""

from __future__ import annotations

import time

from shared.timing import clock_name, monotonic_seconds


def test_monotonic_seconds_is_non_decreasing_and_tracks_sleep() -> None:
    start = monotonic_seconds()
    time.sleep(0.05)
    elapsed = monotonic_seconds() - start
    assert elapsed >= 0.04
    assert elapsed < 5.0


def test_clock_name_prefers_raw_monotonic_when_available() -> None:
    expected = "CLOCK_MONOTONIC_RAW" if hasattr(time, "CLOCK_MONOTONIC_RAW") else "perf_counter"
    assert clock_name() == expected
