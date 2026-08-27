"""Snowflake transcript source placeholder.

Models the reference Snowflake transcript source. Local runs use the synthetic
generator instead. Implement ``fetch_transcripts`` against the Snowflake
connector for real environments.
"""

from __future__ import annotations

from collections.abc import Iterator

from shared.types import Transcript


class SnowflakeTranscriptSource:
    """Placeholder Snowflake source (not required for local execution)."""

    def __init__(self, account: str | None = None, warehouse: str | None = None) -> None:
        self._account = account
        self._warehouse = warehouse

    def fetch_transcripts(self, limit: int) -> Iterator[Transcript]:  # pragma: no cover
        raise NotImplementedError(
            "SnowflakeTranscriptSource is a placeholder. Local runs use the "
            "SyntheticTranscriptGenerator; implement this with the Snowflake "
            "connector for cloud runs."
        )
