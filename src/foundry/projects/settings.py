"""Foundry project configuration read safely from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FoundryProjectSettings:
    """Connection settings for a Microsoft Foundry project.

    Values come exclusively from environment variables. No secrets are ever
    stored in code or defaulted to real values.
    """

    project_endpoint: str | None
    model_name: str | None
    tenant_id: str | None
    # Opt-in agent mode. Direct model inference is the default (recommended for
    # the throughput/cost story); set FOUNDRY_USE_AGENT=1 to route through the
    # Foundry agent runtime instead.
    use_agent: bool = False
    agent_name: str | None = None
    agent_instructions: str | None = None

    @classmethod
    def from_env(cls) -> FoundryProjectSettings:
        return cls(
            project_endpoint=os.environ.get("FOUNDRY_PROJECT_ENDPOINT") or None,
            model_name=os.environ.get("FOUNDRY_MODEL_NAME") or None,
            tenant_id=os.environ.get("AZURE_TENANT_ID") or None,
            use_agent=_env_flag("FOUNDRY_USE_AGENT"),
            agent_name=os.environ.get("FOUNDRY_AGENT_NAME") or None,
            agent_instructions=os.environ.get("FOUNDRY_AGENT_INSTRUCTIONS") or None,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.project_endpoint)


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}
