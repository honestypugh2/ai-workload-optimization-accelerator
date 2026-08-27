"""Registry and plugin-registration tests."""

from __future__ import annotations

import pytest

# Importing these packages triggers plugin registration side effects.
import evaluation  # noqa: F401
import optimization  # noqa: F401
import workloads  # noqa: F401
from registry import evaluator_registry, scenario_registry, strategy_registry
from registry._base import Registry


def test_scenario_registered() -> None:
    assert "post-call-analytics" in scenario_registry.names()


def test_expected_strategies_registered() -> None:
    expected = {
        "baseline_full_transcript",
        "prompt_optimization",
        "context_minimization",
        "selective_extraction",
        "summarize_before_analyze",
        "deterministic_first",
    }
    assert expected.issubset(set(strategy_registry.names()))


def test_expected_evaluators_registered() -> None:
    expected = {"member_id", "structured_output", "escalation"}
    assert expected.issubset(set(evaluator_registry.names()))


def test_duplicate_registration_raises() -> None:
    reg: Registry[type] = Registry("thing")
    reg.register("a", int)
    with pytest.raises(ValueError):
        reg.register("a", str)


def test_register_as_decorator() -> None:
    reg: Registry[type] = Registry("thing")

    @reg.register("obj")
    class Thing:
        pass

    assert reg.get("obj") is Thing


def test_get_missing_raises() -> None:
    reg: Registry[type] = Registry("thing")
    with pytest.raises(KeyError):
        reg.get("missing")
