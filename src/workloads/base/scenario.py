"""Workload scenario base contracts.

A workload scenario is the plugin unit of the accelerator. It knows how to load
its configuration, generate a faithful synthetic dataset, and construct its
default extractor. Call center post-call analytics is the first implementation, but
the architecture treats it as one plugin among many.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from shared.configuration import ScenarioConfig
from shared.contracts import MemberIdExtractor
from shared.types import Transcript


class WorkloadScenario(ABC):
    """Base class for all workload scenario plugins."""

    name: ClassVar[str]
    display_name: ClassVar[str]

    def __init__(self, root: Path | None = None) -> None:
        # Root of the externalized scenario content (workload-scenarios/<name>).
        self._root = root or self.default_root()

    @classmethod
    def default_root(cls) -> Path:
        return Path("workload-scenarios") / cls.name

    @property
    def root(self) -> Path:
        return self._root

    @abstractmethod
    def load_config(self) -> ScenarioConfig:
        """Load and validate the scenario configuration."""

    @abstractmethod
    def generate_dataset(
        self, count: int, *, seed: int = 1234, labeled: bool = True
    ) -> list[Transcript]:
        """Generate a synthetic dataset faithful to the workload profile."""

    @abstractmethod
    def default_extractor(self) -> MemberIdExtractor:
        """Return the scenario's default deterministic extractor."""
