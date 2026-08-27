"""Tests for the opt-in Foundry agent mode and provider dispatch."""

from __future__ import annotations

import pytest

from foundry.adapters import build_provider, resolve_execution_backend
from foundry.adapters._retry import RetryingProvider
from foundry.projects import FoundryProjectSettings
from shared.configuration import ModelDefinition
from shared.types import ExecutionMode, ModelRequest, ModelResponse, TokenUsage

_ENV_KEYS = [
    "AIWOA_GATEWAY_KIND",
    "FOUNDRY_USE_AGENT",
    "FOUNDRY_PROJECT_ENDPOINT",
    "FOUNDRY_MODEL_NAME",
    "FOUNDRY_AGENT_NAME",
    "FOUNDRY_AGENT_INSTRUCTIONS",
    "AZURE_TENANT_ID",
]


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


_MODEL = ModelDefinition(name="baseline", role="summarization")


class _StubProvider:
    def __init__(self, deployment: str) -> None:
        self._deployment = deployment

    @property
    def deployment(self) -> str:
        return self._deployment

    def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content="{}",
            usage=TokenUsage(prompt_tokens=1, output_tokens=1),
            deployment=self._deployment,
            latency_ms=1.0,
        )


class _Counter:
    def count(self, text: str) -> int:
        return len(text)


def test_agent_disabled_by_default() -> None:
    assert FoundryProjectSettings.from_env().use_agent is False


def test_agent_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_USE_AGENT", "1")
    monkeypatch.setenv("FOUNDRY_AGENT_NAME", "pca-agent")
    monkeypatch.setenv("FOUNDRY_AGENT_INSTRUCTIONS", "Do the task.")
    settings = FoundryProjectSettings.from_env()
    assert settings.use_agent is True
    assert settings.agent_name == "pca-agent"
    assert settings.agent_instructions == "Do the task."


def test_azure_mode_routes_to_agent_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_USE_AGENT", "1")
    import foundry.adapters.agent as agent_mod

    captured: dict[str, object] = {}

    def _fake_build(deployment: str, model: object, counter: object) -> _StubProvider:
        captured["deployment"] = deployment
        return _StubProvider(deployment)

    monkeypatch.setattr(agent_mod, "build_agent_provider", _fake_build)

    provider = build_provider("baseline", _MODEL, _Counter(), ExecutionMode.AZURE)

    assert isinstance(provider, RetryingProvider)
    assert captured["deployment"] == "baseline"


def test_azure_mode_uses_direct_inference_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    import foundry.adapters.azure_openai as azure_mod

    calls: list[str] = []

    def _fake_build(deployment: str, model: object, counter: object) -> _StubProvider:
        calls.append(deployment)
        return _StubProvider(deployment)

    monkeypatch.setattr(azure_mod, "build_azure_provider", _fake_build)

    provider = build_provider("baseline", _MODEL, _Counter(), ExecutionMode.AZURE)

    assert isinstance(provider, RetryingProvider)
    assert calls == ["baseline"]


def test_backend_provenance_local() -> None:
    assert resolve_execution_backend(ExecutionMode.LOCAL) == "local"
    assert resolve_execution_backend(ExecutionMode.DRY_RUN) == "local"


def test_backend_provenance_direct_by_default() -> None:
    assert resolve_execution_backend(ExecutionMode.AZURE) == "direct"


def test_backend_provenance_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_USE_AGENT", "1")
    assert resolve_execution_backend(ExecutionMode.AZURE) == "agent"


def test_backend_provenance_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIWOA_GATEWAY_KIND", "apim")
    assert resolve_execution_backend(ExecutionMode.AZURE) == "gateway:apim"
