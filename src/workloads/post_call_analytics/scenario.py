"""The call center post-call analytics workload scenario plugin."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from registry.scenario_registry import scenario_registry
from shared.configuration import ScenarioConfig, load_scenario_config
from shared.contracts import MemberIdExtractor
from shared.exceptions import ConfigurationError
from shared.types import Transcript
from workloads.base import WorkloadScenario
from workloads.post_call_analytics.domain.extraction import (
    DeterministicMemberIdExtractor,
    NaiveRegexExtractor,
)
from workloads.post_call_analytics.domain.member_id import MemberIdFormat
from workloads.post_call_analytics.infrastructure.synthetic import (
    SyntheticTranscriptGenerator,
)


@scenario_registry.register("post-call-analytics")
class PostCallAnalyticsScenario(WorkloadScenario):
    """First workload scenario: healthcare payer post-call analytics."""

    name: ClassVar[str] = "post-call-analytics"
    display_name: ClassVar[str] = "Call Center Post-Call Analytics"

    def load_config(self) -> ScenarioConfig:
        config_path = self._root / "scenario.yaml"
        if not config_path.exists():
            raise ConfigurationError(
                f"Scenario config not found at {config_path}. Run from the repo root."
            )
        return load_scenario_config(config_path)

    def generate_dataset(
        self, count: int, *, seed: int = 1234, labeled: bool = True
    ) -> list[Transcript]:
        profile = self.load_config().dataset_profile
        generator = SyntheticTranscriptGenerator(profile, id_format=MemberIdFormat())
        return generator.generate(count, seed=seed, labeled=labeled)

    def default_extractor(self) -> MemberIdExtractor:
        return DeterministicMemberIdExtractor(digit_length=MemberIdFormat().digit_length)

    def baseline_extractor(self) -> MemberIdExtractor:
        """The naive baseline extractor used to demonstrate the ~30% starting point."""
        return NaiveRegexExtractor(digit_length=MemberIdFormat().digit_length)


def default_scenario_root() -> Path:
    return Path("workload-scenarios") / PostCallAnalyticsScenario.name
