"""Model routing strategies, quota modelling, and router registry."""

from __future__ import annotations

from optimization.routing.routers import (
    DeploymentState,
    FallbackRouter,
    HealthAwareRouter,
    PtuBurstRouter,
    QuotaAwareRouter,
    QuotaModel,
    RoundRobinRouter,
    Router,
    SingleDeploymentRouter,
    TaskBasedRouter,
    WeightedRouter,
    available_routers,
    build_router,
)

__all__ = [
    "DeploymentState",
    "FallbackRouter",
    "HealthAwareRouter",
    "PtuBurstRouter",
    "QuotaAwareRouter",
    "QuotaModel",
    "RoundRobinRouter",
    "Router",
    "SingleDeploymentRouter",
    "TaskBasedRouter",
    "WeightedRouter",
    "available_routers",
    "build_router",
]
