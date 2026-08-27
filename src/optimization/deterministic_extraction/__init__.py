"""Deterministic-first extraction strategy.

Importing this package registers the ``deterministic_first`` strategy via the
:mod:`optimization.deterministic_extraction.strategy` import side effect.
"""

from __future__ import annotations

from optimization.deterministic_extraction.strategy import DeterministicFirstStrategy

__all__ = ["DeterministicFirstStrategy"]
