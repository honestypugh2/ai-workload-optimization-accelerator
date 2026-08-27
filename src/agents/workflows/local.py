"""Local, dependency-free workflow orchestration.

Provides a minimal sequential workflow abstraction usable without the Agent
Framework. When the Agent Framework is available, these definitions can be
mapped onto its workflow primitives via ``agents.adapters``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """A single named step in a workflow."""

    name: str
    run: Callable[[dict], dict]


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """An ordered sequence of workflow steps."""

    name: str
    steps: Sequence[WorkflowStep]


def run_local_workflow(workflow: WorkflowDefinition, initial: dict) -> dict:
    """Execute a workflow sequentially, threading state through each step."""
    state = dict(initial)
    for step in workflow.steps:
        state = step.run(state)
    return state
