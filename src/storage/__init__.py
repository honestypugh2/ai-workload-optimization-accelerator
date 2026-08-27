"""Storage abstractions and adapters.

The filesystem adapter is the default and requires no cloud services. Cosmos DB
and Snowflake adapters are placeholders that model the reference architecture
without being required for local runs.
"""

from storage.filesystem import FilesystemResultStore

__all__ = ["FilesystemResultStore"]
