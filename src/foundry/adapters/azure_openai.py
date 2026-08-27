"""Microsoft Foundry / Azure OpenAI provider adapter.

This module is imported lazily and only when running in ``AZURE`` execution mode.
It depends on the optional ``foundry`` extra (``azure-ai-projects``,
``azure-identity``). Business logic never imports this module directly.
"""

# The azure-* SDKs are optional (installed via the ``foundry`` extra); their
# imports are guarded at call sites, so missing-import diagnostics are expected.
# pyright: reportMissingImports=false

from __future__ import annotations

import time
from typing import NoReturn

from foundry.projects import FoundryProjectSettings
from shared.configuration import ModelDefinition
from shared.contracts import ModelProvider, TokenCounter
from shared.exceptions import ProviderError, ThrottlingError
from shared.types import ModelRequest, ModelResponse, TokenUsage


class FoundryModelProvider:
    """Adapter over a Microsoft Foundry project model deployment.

    Uses ``DefaultAzureCredential`` (via the project client) so no secrets are
    handled in code. Credentials are resolved from the environment / managed
    identity at runtime.
    """

    def __init__(
        self,
        deployment: str,
        model: ModelDefinition,
        token_counter: TokenCounter,
        settings: FoundryProjectSettings,
    ) -> None:
        self._deployment = deployment
        self._model = model
        self._counter = token_counter
        self._settings = settings
        self._client = self._build_client(settings)

    @property
    def deployment(self) -> str:
        return self._deployment

    @staticmethod
    def _build_client(settings: FoundryProjectSettings) -> object:
        try:
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ProviderError(
                "azure-ai-projects is not installed. Install the 'foundry' extra "
                "to run in AZURE mode: uv sync --extra foundry"
            ) from exc

        if not settings.project_endpoint:
            raise ProviderError("FOUNDRY_PROJECT_ENDPOINT is not configured.")

        return AIProjectClient(
            endpoint=settings.project_endpoint,
            credential=DefaultAzureCredential(),
        )

    def complete(self, request: ModelRequest) -> ModelResponse:  # pragma: no cover
        # Real invocation path. Exercised only against a live Foundry project.
        start = time.perf_counter()
        try:
            client = self._client
            # azure-ai-projects 2.x exposes an authenticated openai client rather
            # than the removed 1.x ``.inference`` namespace.
            openai_client = client.get_openai_client()  # type: ignore[attr-defined]
            result = openai_client.chat.completions.create(
                model=self._settings.model_name or self._deployment,
                messages=[{"role": "user", "content": request.prompt}],
                max_completion_tokens=request.max_output_tokens,
            )
            content = result.choices[0].message.content or ""
            usage = TokenUsage(
                prompt_tokens=getattr(result.usage, "prompt_tokens", 0),
                output_tokens=getattr(result.usage, "completion_tokens", 0),
            )
        except Exception as exc:
            _raise_translated(exc)
        latency = (time.perf_counter() - start) * 1000.0
        return ModelResponse(
            content=content,
            usage=usage,
            deployment=self._deployment,
            latency_ms=round(latency, 3),
        )


def _raise_translated(exc: Exception) -> NoReturn:  # pragma: no cover - live call
    """Translate a 429 into ThrottlingError so the retry wrapper can react."""
    status = getattr(exc, "status_code", None)
    if status == 429 or exc.__class__.__name__ in {"RateLimitError", "TooManyRequests"}:
        retry_after = _retry_after_from(exc)
        raise ThrottlingError(str(exc), retry_after_seconds=retry_after) from exc
    raise ProviderError(f"Foundry completion failed: {exc}") from exc


def _retry_after_from(exc: Exception) -> float | None:  # pragma: no cover - live call
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    raw = headers.get("Retry-After") or headers.get("retry-after")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def build_azure_provider(
    deployment: str,
    model: ModelDefinition,
    token_counter: TokenCounter,
) -> ModelProvider:
    """Construct a live Foundry provider from environment settings."""
    settings = FoundryProjectSettings.from_env()
    return FoundryModelProvider(deployment, model, token_counter, settings)
