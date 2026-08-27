"""Cosmos DB result store placeholder.

Models the reference Cosmos DB insight storage. It is a documented seam only;
local runs never require Cosmos DB. Implement ``save``/``load`` against
``azure-cosmos`` when running in a real environment.
"""

from __future__ import annotations


class CosmosResultStore:
    """Placeholder Cosmos DB adapter (not required for local execution)."""

    def __init__(self, endpoint: str | None = None, database: str | None = None) -> None:
        self._endpoint = endpoint
        self._database = database

    def save(self, key: str, payload: dict) -> str:  # pragma: no cover - placeholder
        raise NotImplementedError(
            "CosmosResultStore is a placeholder. Use FilesystemResultStore locally "
            "or implement this adapter with the azure-cosmos SDK for cloud runs."
        )

    def load(self, key: str) -> dict:  # pragma: no cover - placeholder
        raise NotImplementedError(
            "CosmosResultStore is a placeholder. Use FilesystemResultStore locally."
        )
