"""Model routing abstractions and quota modelling.

Routers select a backing :class:`ModelProvider` for each request. Concrete
routers cover the patterns the assessment recommends evaluating: single
deployment, round-robin, weighted, health-aware, quota-aware, task-based,
fallback, and PTU-base-plus-Standard-burst. A :class:`QuotaModel` supports the
429 / throttling simulation performed by the benchmark runner.
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from shared.contracts import ModelProvider
from shared.exceptions import ConfigurationError
from shared.types import ModelRequest


@dataclass(slots=True)
class DeploymentState:
    """Runtime state for a single deployment used by quota-aware routing."""

    name: str
    tpm_limit: int
    healthy: bool = True
    consumed_tokens: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.tpm_limit - self.consumed_tokens)


class Router(ABC):
    """Selects a provider for a request."""

    name: ClassVar[str]

    def __init__(self, providers: list[ModelProvider]) -> None:
        if not providers:
            raise ConfigurationError("A router requires at least one provider.")
        self._providers = providers
        self._by_name = {p.deployment: p for p in providers}

    @abstractmethod
    def route(self, request: ModelRequest) -> ModelProvider:
        raise NotImplementedError


class SingleDeploymentRouter(Router):
    """Always routes to the first (only) deployment: the reference baseline."""

    name = "single_deployment"

    def route(self, request: ModelRequest) -> ModelProvider:
        return self._providers[0]


class RoundRobinRouter(Router):
    """Distributes requests evenly across deployments."""

    name = "round_robin"

    def __init__(self, providers: list[ModelProvider]) -> None:
        super().__init__(providers)
        self._cycle = itertools.cycle(providers)

    def route(self, request: ModelRequest) -> ModelProvider:
        return next(self._cycle)


class WeightedRouter(Router):
    """Routes by static weights (default: uniform)."""

    name = "weighted"

    def __init__(self, providers: list[ModelProvider], weights: list[float] | None = None) -> None:
        super().__init__(providers)
        self._weights = weights or [1.0] * len(providers)
        if len(self._weights) != len(providers):
            raise ConfigurationError("weights length must match provider count.")
        self._acc = [0.0] * len(providers)

    def route(self, request: ModelRequest) -> ModelProvider:
        # Deterministic weighted round-robin (smooth weighted).
        for i, w in enumerate(self._weights):
            self._acc[i] += w
        idx = max(range(len(self._acc)), key=lambda i: self._acc[i])
        self._acc[idx] -= sum(self._weights)
        return self._providers[idx]


class HealthAwareRouter(Router):
    """Skips deployments marked unhealthy, falling back to round-robin."""

    name = "health_aware"

    def __init__(
        self, providers: list[ModelProvider], states: dict[str, DeploymentState] | None = None
    ) -> None:
        super().__init__(providers)
        self._states = states or {
            p.deployment: DeploymentState(p.deployment, tpm_limit=10**9) for p in providers
        }
        self._cycle = itertools.cycle(providers)

    def route(self, request: ModelRequest) -> ModelProvider:
        for _ in range(len(self._providers)):
            provider = next(self._cycle)
            if self._states[provider.deployment].healthy:
                return provider
        return self._providers[0]


class QuotaAwareRouter(Router):
    """Routes to the deployment with the most remaining quota."""

    name = "quota_aware"

    def __init__(self, providers: list[ModelProvider], states: dict[str, DeploymentState]) -> None:
        super().__init__(providers)
        self._states = states

    def route(self, request: ModelRequest) -> ModelProvider:
        best = max(self._providers, key=lambda p: self._states[p.deployment].remaining)
        return best


class TaskBasedRouter(Router):
    """Routes based on the request task via a task -> deployment map."""

    name = "task_based"

    def __init__(self, providers: list[ModelProvider], task_map: dict[str, str]) -> None:
        super().__init__(providers)
        self._task_map = task_map

    def route(self, request: ModelRequest) -> ModelProvider:
        deployment = self._task_map.get(request.task)
        if deployment and deployment in self._by_name:
            return self._by_name[deployment]
        return self._providers[0]


class FallbackRouter(Router):
    """Primary deployment with an ordered fallback chain."""

    name = "fallback"

    def __init__(
        self, providers: list[ModelProvider], states: dict[str, DeploymentState] | None = None
    ) -> None:
        super().__init__(providers)
        self._states = states or {
            p.deployment: DeploymentState(p.deployment, tpm_limit=10**9) for p in providers
        }

    def route(self, request: ModelRequest) -> ModelProvider:
        for provider in self._providers:
            state = self._states[provider.deployment]
            if state.healthy and state.remaining > 0:
                return provider
        return self._providers[0]


class PtuBurstRouter(Router):
    """PTU base deployment with Standard/PayGo burst overflow.

    Routes to the PTU deployment until its reserved quota is exhausted, then
    bursts to Standard deployments.
    """

    name = "ptu_burst"

    def __init__(
        self,
        providers: list[ModelProvider],
        states: dict[str, DeploymentState],
        ptu_deployment: str,
    ) -> None:
        super().__init__(providers)
        self._states = states
        self._ptu = ptu_deployment

    def route(self, request: ModelRequest) -> ModelProvider:
        ptu_state = self._states.get(self._ptu)
        if ptu_state and ptu_state.remaining > 0 and self._ptu in self._by_name:
            return self._by_name[self._ptu]
        for provider in self._providers:
            if provider.deployment != self._ptu and self._states[provider.deployment].remaining > 0:
                return provider
        return self._providers[0]


@dataclass(slots=True)
class QuotaModel:
    """Tracks token consumption per deployment within a rolling minute window.

    Used by the benchmark runner to simulate HTTP 429 throttling and retry
    behaviour deterministically.
    """

    states: dict[str, DeploymentState] = field(default_factory=dict)

    @classmethod
    def from_deployments(cls, deployments: dict[str, int]) -> QuotaModel:
        return cls(states={n: DeploymentState(n, tpm_limit=t) for n, t in deployments.items()})

    def try_consume(self, deployment: str, tokens: int) -> bool:
        """Attempt to consume ``tokens``. Returns False if it would throttle."""
        state = self.states.get(deployment)
        if state is None:
            return True
        if state.consumed_tokens + tokens > state.tpm_limit:
            return False
        state.consumed_tokens += tokens
        return True

    def reset_window(self) -> None:
        for state in self.states.values():
            state.consumed_tokens = 0


_ROUTERS: dict[str, type[Router]] = {
    SingleDeploymentRouter.name: SingleDeploymentRouter,
    RoundRobinRouter.name: RoundRobinRouter,
    WeightedRouter.name: WeightedRouter,
    HealthAwareRouter.name: HealthAwareRouter,
    QuotaAwareRouter.name: QuotaAwareRouter,
    TaskBasedRouter.name: TaskBasedRouter,
    FallbackRouter.name: FallbackRouter,
    PtuBurstRouter.name: PtuBurstRouter,
}


def available_routers() -> list[str]:
    return sorted(_ROUTERS)


def build_router(
    name: str,
    providers: list[ModelProvider],
    *,
    states: dict[str, DeploymentState] | None = None,
    task_map: dict[str, str] | None = None,
    weights: list[float] | None = None,
    ptu_deployment: str | None = None,
) -> Router:
    """Construct a router by name, supplying the extras each router needs."""
    if name not in _ROUTERS:
        raise ConfigurationError(f"Unknown router '{name}'. Available: {available_routers()}")
    cls = _ROUTERS[name]
    if cls is WeightedRouter:
        return WeightedRouter(providers, weights=weights)
    if cls is TaskBasedRouter:
        return TaskBasedRouter(providers, task_map=task_map or {})
    if cls is QuotaAwareRouter:
        if states is None:
            raise ConfigurationError("quota_aware router requires deployment states.")
        return QuotaAwareRouter(providers, states=states)
    if cls is PtuBurstRouter:
        if states is None or ptu_deployment is None:
            raise ConfigurationError("ptu_burst router requires states and ptu_deployment.")
        return PtuBurstRouter(providers, states=states, ptu_deployment=ptu_deployment)
    if cls in (HealthAwareRouter, FallbackRouter):
        return cls(providers, states=states)
    return cls(providers)
