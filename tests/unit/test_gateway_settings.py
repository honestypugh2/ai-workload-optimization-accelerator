"""Tests for OpenAI-compatible gateway settings (LiteLLM / APIM)."""

from __future__ import annotations

import pytest

from foundry.projects import GatewaySettings
from shared.exceptions import ConfigurationError

_ENV_KEYS = [
    "AIWOA_GATEWAY_KIND",
    "AIWOA_GATEWAY_BASE_URL",
    "AIWOA_GATEWAY_API_KEY",
    "AIWOA_GATEWAY_API_KEY_HEADER",
    "AIWOA_GATEWAY_API_VERSION",
    "AIWOA_GATEWAY_USE_AAD",
    "AIWOA_GATEWAY_DEPLOYMENTS",
    "AIWOA_GATEWAY_MAX_RETRIES",
    "AIWOA_GATEWAY_BASE_BACKOFF_S",
]


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_to_direct_no_gateway() -> None:
    settings = GatewaySettings.from_env()
    assert settings.kind == "direct"
    assert settings.is_gateway is False
    assert settings.max_retries == 5
    assert settings.base_backoff_s == 0.5


def test_litellm_gateway_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIWOA_GATEWAY_KIND", "litellm")
    monkeypatch.setenv("AIWOA_GATEWAY_BASE_URL", "http://localhost:4000")
    monkeypatch.setenv("AIWOA_GATEWAY_DEPLOYMENTS", '{"baseline": "gpt-4o-mini"}')
    settings = GatewaySettings.from_env()
    assert settings.is_gateway is True
    assert settings.base_url == "http://localhost:4000"
    assert settings.model_for("baseline") == "gpt-4o-mini"
    # Unmapped aliases fall back to the alias itself.
    assert settings.model_for("large") == "large"


def test_apim_is_a_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIWOA_GATEWAY_KIND", "apim")
    assert GatewaySettings.from_env().is_gateway is True


def test_invalid_kind_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIWOA_GATEWAY_KIND", "bogus")
    with pytest.raises(ConfigurationError):
        GatewaySettings.from_env()


def test_invalid_deployments_json_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIWOA_GATEWAY_DEPLOYMENTS", "not-json")
    with pytest.raises(ConfigurationError):
        GatewaySettings.from_env()


def test_non_string_deployments_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIWOA_GATEWAY_DEPLOYMENTS", '{"baseline": 3}')
    with pytest.raises(ConfigurationError):
        GatewaySettings.from_env()


def test_invalid_int_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIWOA_GATEWAY_MAX_RETRIES", "abc")
    with pytest.raises(ConfigurationError):
        GatewaySettings.from_env()
