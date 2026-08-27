"""Configuration validation tests (pydantic boundaries)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.configuration import (
    DatasetProfile,
    ModelCatalog,
    ModelDefinition,
    ScorecardConfig,
    ThresholdRule,
    load_scenario_config,
)
from shared.exceptions import ConfigurationError
from workloads.post_call_analytics.scenario import default_scenario_root


def test_dataset_profile_rejects_bad_distribution() -> None:
    with pytest.raises((ValidationError, ConfigurationError)):
        DatasetProfile(
            target_daily_volume=1000,
            average_token_count=5000,
            size_distribution={"small": 0.5, "average": 0.2},  # sums to 0.7
        )


def test_dataset_profile_accepts_valid_distribution() -> None:
    profile = DatasetProfile(
        target_daily_volume=1000,
        average_token_count=5000,
        size_distribution={"small": 0.3, "average": 0.5, "long": 0.2},
    )
    assert abs(sum(profile.size_distribution.values()) - 1.0) < 1e-9


def test_model_catalog_get_missing_alias_raises() -> None:
    catalog = ModelCatalog(baseline=ModelDefinition(name="nano", role="baseline"))
    with pytest.raises(ConfigurationError):
        catalog.get("large")


def test_threshold_rule_rejects_unknown_operator() -> None:
    with pytest.raises(ValidationError):
        ThresholdRule(metric="recall", op="approximately", value=0.9)


def test_relative_latency_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ModelDefinition(name="x", role="r", relative_latency=0)


def test_scenario_config_loads_from_disk() -> None:
    config = load_scenario_config(default_scenario_root() / "scenario.yaml")
    assert config.model_catalog.baseline is not None
    assert config.dataset_profile.target_daily_volume > 0


def test_scorecard_config_requires_a_source_per_run() -> None:
    with pytest.raises(ValidationError):
        ScorecardConfig.model_validate({"name": "c", "runs": [{"label": "a"}]})


def test_scorecard_config_accepts_benchmark_runs() -> None:
    cfg = ScorecardConfig.model_validate(
        {
            "name": "current-state-vs-options",
            "runs": [
                {
                    "label": "current-state",
                    "benchmark": "../reports/current-state-azure.result.json",
                },
                {"label": "option-a", "benchmark": "../reports/option-a-azure.result.json"},
            ],
        }
    )
    assert cfg.runs[0].label == "current-state"
    assert cfg.runs[1].benchmark == "../reports/option-a-azure.result.json"


def test_shipped_scorecard_config_loads() -> None:
    from shared.configuration import load_scorecard_config

    path = default_scenario_root() / "scorecards" / "current-state-vs-options.yaml"
    cfg = load_scorecard_config(path)
    assert [r.label for r in cfg.runs] == [
        "current-state",
        "option-a",
        "option-b",
        "option-c",
        "foundry-current",
    ]
