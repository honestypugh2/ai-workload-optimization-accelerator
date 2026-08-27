"""Minimal tracing span context manager.

No-op by default; provides a stable seam for a real tracer (OpenTelemetry) to be
injected without touching call sites.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from observability.logging import get_logger

_logger = get_logger("observability.trace")


@contextmanager
def span(name: str, **attributes: object) -> Iterator[None]:
    """A lightweight tracing span. Logs at DEBUG level."""
    _logger.debug("span.start name=%s attrs=%s", name, attributes)
    try:
        yield
    finally:
        _logger.debug("span.end name=%s", name)
