"""Post-call analytics workload package.

Importing this package registers the ``post-call-analytics`` scenario plugin.
"""

from workloads.post_call_analytics.scenario import PostCallAnalyticsScenario

__all__ = ["PostCallAnalyticsScenario"]
