"""Observability primitives: logging, tracing, and metrics.

These are deliberately lightweight and dependency-free so the accelerator has no
mandatory telemetry backend. Adapters (e.g. OpenTelemetry, App Insights) can be
layered on later behind the same interfaces.
"""

from observability.logging import get_logger
from observability.metrics import MetricSink, Timer
from observability.tracing import span

__all__ = ["MetricSink", "Timer", "get_logger", "span"]
