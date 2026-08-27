"""Model provider adapters.

``MockModelProvider`` is the default, fully-local provider. ``build_provider``
selects a provider based on the requested execution mode, importing the Azure
adapter lazily so that ``azure-ai-projects`` remains an optional dependency.
"""

from foundry.adapters.mock import MockModelProvider, build_provider, resolve_execution_backend

__all__ = ["MockModelProvider", "build_provider", "resolve_execution_backend"]
