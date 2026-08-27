"""Registry of workload scenario plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from registry._base import Registry

if TYPE_CHECKING:
    from workloads.base import WorkloadScenario  # noqa: F401

ScenarioRegistry = Registry["type[WorkloadScenario]"]

scenario_registry: ScenarioRegistry = Registry("scenario")
