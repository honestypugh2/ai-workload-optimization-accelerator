"""Workload scenario plugins.

Importing this package imports all built-in workloads for their scenario
registration side effects.
"""

from workloads import post_call_analytics  # noqa: F401
from workloads.base import WorkloadScenario

__all__ = ["WorkloadScenario"]
