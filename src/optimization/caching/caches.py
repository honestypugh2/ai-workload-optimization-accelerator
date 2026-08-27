"""Caching primitives: prompt, result, metadata, and semantic caching.

All caches are in-memory and content-addressed. They provide the same interface
so strategies can compose them. A ``CacheBundle`` groups the cache kinds used by
the post-call analytics workload, plus an incremental/watermark processor.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Generic, TypeVar

V = TypeVar("V")

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCTUATION_RE = re.compile(r"[^\w\s]")


def _key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _semantic_key(text: str) -> str:
    """Normalize casing, punctuation, and whitespace so near-duplicates collide."""
    normalized = _PUNCTUATION_RE.sub("", text.lower())
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return _key(normalized)


class ContentCache(Generic[V]):
    """A simple content-addressed cache with hit/miss accounting."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._store: dict[str, V] = {}
        self.hits = 0
        self.misses = 0

    def _make_key(self, content: str) -> str:
        return _key(content)

    def get(self, content: str) -> V | None:
        if not self.enabled:
            return None
        value = self._store.get(self._make_key(content))
        if value is None:
            self.misses += 1
        else:
            self.hits += 1
        return value

    def put(self, content: str, value: V) -> None:
        if self.enabled:
            self._store[self._make_key(content)] = value

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class SemanticCache(ContentCache[V]):
    """Near-duplicate-aware cache keyed on a normalized form of the content.

    Models an APIM/Redis semantic-cache gateway policy without embeddings:
    prompts that differ only by casing, punctuation, or whitespace collapse onto
    a single entry. Production would replace the normalization key with an
    embedding-similarity lookup (limitation: no embedding backend runs locally).
    """

    def _make_key(self, content: str) -> str:
        return _semantic_key(content)


@dataclass(slots=True)
class IncrementalProcessor:
    """Watermark that skips transcripts already processed in prior runs.

    Incremental / watermark processing is the highest-leverage way to avoid
    needless model load: a transcript that has already been analyzed is never
    reprocessed. Within a single benchmark over net-new synthetic transcripts
    there are no repeats, so in-run skips are zero by design; the saving
    materializes across re-runs, backfills, and retries (limitation: not
    exercised by a single one-shot benchmark).
    """

    enabled: bool = False
    _seen: set[str] = field(default_factory=set)
    skipped: int = 0
    processed: int = 0

    def should_process(self, transcript_id: str) -> bool:
        if not self.enabled:
            self.processed += 1
            return True
        if transcript_id in self._seen:
            self.skipped += 1
            return False
        self._seen.add(transcript_id)
        self.processed += 1
        return True

    @property
    def skip_rate(self) -> float:
        total = self.processed + self.skipped
        return self.skipped / total if total else 0.0


@dataclass(slots=True)
class CacheBundle:
    """Groups the prompt, result, metadata, and semantic caches for a run."""

    prompt_cache: ContentCache[str] = field(default_factory=lambda: ContentCache(enabled=False))
    result_cache: ContentCache[dict] = field(default_factory=lambda: ContentCache(enabled=False))
    metadata_cache: ContentCache[dict] = field(default_factory=lambda: ContentCache(enabled=False))
    semantic_cache: SemanticCache[str] = field(default_factory=lambda: SemanticCache(enabled=False))
    incremental: IncrementalProcessor = field(default_factory=IncrementalProcessor)

    @classmethod
    def from_flags(cls, flags: list[str]) -> CacheBundle:
        """Build a bundle enabling the caches named in ``flags``."""
        return cls(
            prompt_cache=ContentCache(enabled="prompt" in flags),
            result_cache=ContentCache(enabled="result" in flags),
            metadata_cache=ContentCache(enabled="metadata" in flags),
            semantic_cache=SemanticCache(enabled="semantic" in flags),
            incremental=IncrementalProcessor(enabled="incremental" in flags),
        )

    @property
    def combined_hit_rate(self) -> float:
        caches = (self.prompt_cache, self.result_cache, self.metadata_cache, self.semantic_cache)
        hits = sum(c.hits for c in caches)
        misses = sum(c.misses for c in caches)
        total = hits + misses
        return hits / total if total else 0.0
