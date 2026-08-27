"""Agent Framework availability detection.

Kept isolated so that importing the accelerator never hard-fails when the
optional ``agent-framework`` package is absent.
"""

from __future__ import annotations


def agent_framework_available() -> bool:
    """Return True only if the Microsoft Agent Framework is importable."""
    try:
        import agent_framework  # noqa: F401  # pyright: ignore[reportMissingImports]
    except ImportError:
        return False
    return True
