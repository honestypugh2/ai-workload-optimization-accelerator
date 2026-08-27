"""OpenAI-compatible gateway provider for LiteLLM and APIM AI Gateway.

Both gateways speak the OpenAI Chat Completions protocol, so this single adapter
targets either by pointing ``base_url`` at the proxy/gateway. Selection between
them is configuration only (``AIWOA_GATEWAY_KIND``), never separate code paths.
Imported lazily and only in AZURE mode; depends on the optional ``foundry`` extra.
"""

# The openai/azure SDKs are optional (installed via the ``foundry`` extra); their
# imports are guarded at call sites, so missing-import diagnostics are expected.
# pyright: reportMissingImports=false

from __future__ import annotations

import time
from typing import NoReturn

from foundry.projects import GatewaySettings
from shared.configuration import ModelDefinition
from shared.contracts import ModelProvider, TokenCounter
from shared.exceptions import ProviderError, ThrottlingError
from shared.types import ModelRequest, ModelResponse, TokenUsage

# AAD scope for Azure OpenAI / APIM when using managed identity instead of a key.
_AAD_SCOPE = "https://cognitiveservices.azure.com/.default"


class OpenAICompatibleProvider:
    """Adapter over a LiteLLM proxy or APIM AI Gateway deployment."""

    def __init__(
        self,
        deployment: str,
        model: ModelDefinition,
        token_counter: TokenCounter,
        settings: GatewaySettings,
    ) -> None:
        self._deployment = deployment
        self._model_name = settings.model_for(model.name)
        self._counter = token_counter
        self._settings = settings
        self._client = self._build_client(settings)

    @property
    def deployment(self) -> str:
        return self._deployment

    @staticmethod
    def _build_client(settings: GatewaySettings) -> object:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ProviderError(
                "openai is not installed. Install the 'foundry' extra to route "
                "through a gateway: uv sync --extra foundry"
            ) from exc

        if not settings.base_url:
            raise ProviderError("AIWOA_GATEWAY_BASE_URL is not configured.")

        api_key = settings.api_key
        default_headers: dict[str, str] = {}
        if settings.use_aad and not api_key:
            api_key = _aad_token()
        # A non-Authorization header (e.g. APIM 'Ocp-Apim-Subscription-Key' or
        # 'api-key') is passed explicitly; Authorization uses the bearer api_key.
        if api_key and settings.api_key_header.lower() != "authorization":
            default_headers[settings.api_key_header] = api_key
            api_key = "unused"

        return OpenAI(
            base_url=settings.base_url,
            api_key=api_key or "unused",
            default_headers=default_headers or None,
        )

    def complete(self, request: ModelRequest) -> ModelResponse:  # pragma: no cover - live call
        start = time.perf_counter()
        try:
            client = self._client
            result = client.chat.completions.create(  # type: ignore[attr-defined]
                model=self._model_name,
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


def _aad_token() -> str:  # pragma: no cover - requires live credentials
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise ProviderError(
            "azure-identity is not installed. Install the 'foundry' extra to use "
            "AAD auth: uv sync --extra foundry"
        ) from exc
    return DefaultAzureCredential().get_token(_AAD_SCOPE).token


def _raise_translated(exc: Exception) -> NoReturn:  # pragma: no cover - live call
    """Translate a 429 into ThrottlingError so the retry wrapper can react."""
    status = getattr(exc, "status_code", None)
    retry_after = _retry_after_from(exc)
    if status == 429 or exc.__class__.__name__ == "RateLimitError":
        raise ThrottlingError(str(exc), retry_after_seconds=retry_after) from exc
    raise ProviderError(f"Gateway completion failed: {exc}") from exc


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


def build_gateway_provider(
    deployment: str,
    model: ModelDefinition,
    token_counter: TokenCounter,
    settings: GatewaySettings,
) -> ModelProvider:
    """Construct an OpenAI-compatible gateway provider from settings."""
    return OpenAICompatibleProvider(deployment, model, token_counter, settings)
