"""Model catalog loading and local token estimation."""

from __future__ import annotations

import math
import re

from shared.configuration import ModelCatalog, ScenarioConfig

_WORD_RE = re.compile(r"\w+|[^\w\s]")


class ApproxTokenCounter:
    """Local, offline token estimator.

    Uses a word/punctuation heuristic (~0.75 tokens per word plus punctuation)
    that is stable and dependency-free. It is intentionally approximate; real
    counts come from the provider when running against Azure.
    """

    def __init__(self, tokens_per_word: float = 1.33) -> None:
        self._tokens_per_word = tokens_per_word

    def count(self, text: str) -> int:
        if not text:
            return 0
        pieces = _WORD_RE.findall(text)
        return max(1, math.ceil(len(pieces) * self._tokens_per_word / 1.33))


def load_catalog_from_scenario(scenario: ScenarioConfig) -> ModelCatalog:
    """Return the model catalog embedded in a scenario configuration."""
    return scenario.model_catalog
