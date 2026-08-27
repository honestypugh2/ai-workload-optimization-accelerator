"""Azure AI Foundry integration.

Foundry is an OPTIONAL dependency. The local benchmark and evaluation paths run
entirely against ``MockModelProvider`` and never import the Azure SDK. Azure code
is isolated in ``foundry.adapters`` and imported lazily.
"""

from foundry.adapters import MockModelProvider, build_provider
from foundry.model_catalog import ApproxTokenCounter, load_catalog_from_scenario

__all__ = [
    "ApproxTokenCounter",
    "MockModelProvider",
    "build_provider",
    "load_catalog_from_scenario",
]
