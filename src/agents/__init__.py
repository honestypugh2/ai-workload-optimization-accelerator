"""Microsoft Agent Framework integration (optional).

The accelerator remains fully usable without the Agent Framework. These adapters
provide optional workflow orchestration and harness-like agent evaluation. When
the ``agent-framework`` package is not installed, ``agent_framework_available``
returns ``False`` and callers fall back to the local harnesses.
"""

from agents.adapters import agent_framework_available
from agents.evaluators import LocalAgentEvaluator
from agents.workflows import WorkflowDefinition, run_local_workflow

__all__ = [
    "LocalAgentEvaluator",
    "WorkflowDefinition",
    "agent_framework_available",
    "run_local_workflow",
]
