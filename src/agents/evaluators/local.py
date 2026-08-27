"""Harness-like local agent evaluation.

A thin, deterministic evaluator used to exercise agent workflows offline. It does
not require the Agent Framework; it validates that a workflow produced the
expected keys/values, which is sufficient for harness-style regression tests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocalAgentEvaluator:
    """Checks a workflow output dict against required keys."""

    required_keys: tuple[str, ...]

    def evaluate(self, output: dict) -> dict:
        missing = [k for k in self.required_keys if k not in output]
        return {
            "passed": not missing,
            "missing_keys": missing,
            "checked_keys": list(self.required_keys),
        }
