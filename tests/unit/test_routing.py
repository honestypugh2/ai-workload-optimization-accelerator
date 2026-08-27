"""Routing and quota-model tests."""

from __future__ import annotations

import pytest

from foundry.adapters.mock import MockModelProvider
from foundry.model_catalog import ApproxTokenCounter
from optimization.routing import (
    DeploymentState,
    QuotaModel,
    available_routers,
    build_router,
)
from shared.configuration import ModelDefinition
from shared.contracts import ModelProvider
from shared.exceptions import ConfigurationError
from shared.types import ModelRequest

EXPECTED = {
    "single_deployment",
    "round_robin",
    "weighted",
    "health_aware",
    "quota_aware",
    "task_based",
    "fallback",
    "ptu_burst",
}


def _provider(name: str) -> MockModelProvider:
    model = ModelDefinition(name=name, role="test")
    return MockModelProvider(name, model, ApproxTokenCounter())


def _providers(n: int) -> list[ModelProvider]:
    return [_provider(f"dep-{i}") for i in range(n)]


def test_all_expected_routers_registered() -> None:
    assert EXPECTED.issubset(set(available_routers()))


def test_single_deployment_always_same_provider() -> None:
    router = build_router("single_deployment", _providers(3))
    req = ModelRequest(prompt="hello", task="extraction")
    picks = {router.route(req).deployment for _ in range(5)}
    assert picks == {"dep-0"}


def test_round_robin_cycles_providers() -> None:
    router = build_router("round_robin", _providers(3))
    req = ModelRequest(prompt="hello")
    seen = [router.route(req).deployment for _ in range(6)]
    assert set(seen) == {"dep-0", "dep-1", "dep-2"}


def test_weighted_router_respects_weights() -> None:
    router = build_router("weighted", _providers(2), weights=[1.0, 0.0])
    req = ModelRequest(prompt="hello")
    picks = {router.route(req).deployment for _ in range(10)}
    assert picks == {"dep-0"}


def test_task_based_router_maps_task_to_deployment() -> None:
    router = build_router(
        "task_based",
        _providers(2),
        task_map={"summary": "dep-1"},
    )
    assert router.route(ModelRequest(prompt="x", task="summary")).deployment == "dep-1"


def test_quota_aware_requires_states() -> None:
    with pytest.raises(ConfigurationError):
        build_router("quota_aware", _providers(1))


def test_quota_model_throttles_when_exhausted() -> None:
    quota = QuotaModel.from_deployments({"dep-0": 1000})
    assert quota.try_consume("dep-0", 600) is True
    assert quota.try_consume("dep-0", 600) is False  # would exceed limit within window
    quota.reset_window()
    assert quota.try_consume("dep-0", 600) is True


def test_quota_model_unknown_deployment_not_throttled() -> None:
    quota = QuotaModel.from_deployments({"dep-0": 1000})
    assert quota.try_consume("other", 10_000) is True


def test_deployment_state_remaining_never_negative() -> None:
    state = DeploymentState(name="d", tpm_limit=100, consumed_tokens=250)
    assert state.remaining == 0
