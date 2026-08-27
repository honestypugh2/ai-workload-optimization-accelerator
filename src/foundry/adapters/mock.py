"""Local mock model provider and the provider factory."""

from __future__ import annotations

import hashlib
import json

from shared.configuration import ModelDefinition
from shared.contracts import ModelProvider, TokenCounter
from shared.types import ExecutionMode, ModelRequest, ModelResponse, TokenUsage

# Base per-call latency in milliseconds for a nominal (relative_latency == 1.0)
# deployment. Scaled by the model's relative latency and prompt size.
_BASE_LATENCY_MS = 45.0
_MS_PER_1K_PROMPT_TOKENS = 8.0


class MockModelProvider:
    """Deterministic, offline provider used for local benchmarking.

    Produces stable token usage and latency estimates without any network
    access. Throttling/quota behaviour is modelled separately by the benchmark
    runner so this provider stays pure and side-effect free.
    """

    def __init__(
        self,
        deployment: str,
        model: ModelDefinition,
        token_counter: TokenCounter,
    ) -> None:
        self._deployment = deployment
        self._model = model
        self._counter = token_counter

    @property
    def deployment(self) -> str:
        return self._deployment

    def complete(self, request: ModelRequest) -> ModelResponse:
        prompt_tokens = self._counter.count(request.prompt)
        output_tokens = self._synthetic_output_tokens(request, prompt_tokens)
        latency = (
            _BASE_LATENCY_MS + (prompt_tokens / 1000.0) * _MS_PER_1K_PROMPT_TOKENS
        ) * self._model.relative_latency
        content = self._synthetic_content(request)
        return ModelResponse(
            content=content,
            usage=TokenUsage(prompt_tokens=prompt_tokens, output_tokens=output_tokens),
            deployment=self._deployment,
            latency_ms=round(latency, 3),
        )

    def _synthetic_output_tokens(self, request: ModelRequest, prompt_tokens: int) -> int:
        # Structured extraction/classification produce compact output; summaries
        # produce more. Deterministic and bounded by max_output_tokens.
        base = {
            "sentiment": 24,
            "escalation": 24,
            "extraction": 40,
            "evidence": 120,
            "summary": 220,
        }.get(request.task, 64)
        scaled = base + prompt_tokens // 200
        return min(scaled, request.max_output_tokens)

    def _synthetic_content(self, request: ModelRequest) -> str:
        digest = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:8]
        payload = {"task": request.task, "deployment": self._deployment, "trace": digest}
        return json.dumps(payload, separators=(",", ":"))


def build_provider(
    deployment: str,
    model: ModelDefinition,
    token_counter: TokenCounter,
    mode: ExecutionMode = ExecutionMode.LOCAL,
) -> ModelProvider:
    """Return a provider for the given execution mode.

    ``LOCAL`` and ``DRY_RUN`` use the mock provider. ``AZURE`` lazily imports the
    Foundry adapter so the Azure SDK stays optional. In ``AZURE`` mode direct
    model inference is the default; a gateway (``AIWOA_GATEWAY_KIND``) or the
    opt-in agent runtime (``FOUNDRY_USE_AGENT=1``) can be selected instead.
    """
    if mode is ExecutionMode.AZURE:
        from foundry.adapters._retry import RetryingProvider
        from foundry.projects import GatewaySettings

        settings = GatewaySettings.from_env()
        if settings.is_gateway:
            from foundry.adapters.openai_gateway import build_gateway_provider

            provider = build_gateway_provider(deployment, model, token_counter, settings)
        else:
            from foundry.projects import FoundryProjectSettings

            foundry_settings = FoundryProjectSettings.from_env()
            if foundry_settings.use_agent:
                # Opt-in agent runtime. Direct inference stays the default.
                from foundry.adapters.agent import build_agent_provider

                provider = build_agent_provider(deployment, model, token_counter)
            else:
                from foundry.adapters.azure_openai import build_azure_provider

                provider = build_azure_provider(deployment, model, token_counter)
        return RetryingProvider(
            provider,
            max_retries=settings.max_retries,
            base_backoff_s=settings.base_backoff_s,
        )
    return MockModelProvider(deployment, model, token_counter)


def resolve_execution_backend(mode: ExecutionMode = ExecutionMode.LOCAL) -> str:
    """Return a provenance label for the provider path a run will use.

    Mirrors the selection logic in ``build_provider`` so a result can record
    which backend produced it: ``local`` (mock), ``gateway:<kind>`` (LiteLLM /
    APIM), ``agent`` (opt-in Foundry agent), or ``direct`` (model inference).
    """
    if mode is not ExecutionMode.AZURE:
        return "local"
    from foundry.projects import FoundryProjectSettings, GatewaySettings

    gateway = GatewaySettings.from_env()
    if gateway.is_gateway:
        return f"gateway:{gateway.kind}"
    if FoundryProjectSettings.from_env().use_agent:
        return "agent"
    return "direct"
