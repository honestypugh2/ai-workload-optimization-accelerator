"""Microsoft Foundry Agent provider adapter (opt-in).

Direct model inference (``azure_openai.py``) is the default and recommended
path for the throughput/cost story. This module provides an *opt-in* agent
runtime instead: set ``FOUNDRY_USE_AGENT=1`` to route each request through the
Foundry agent (OpenAI Responses API) so the same benchmark can compare an
agent-style invocation against raw model inference. Agent calls carry extra
per-request orchestration (persona instructions, server-side state), so this
mode is intentionally not recommended for peak throughput.

Imported lazily and only in ``AZURE`` execution mode; the azure-* SDKs are the
optional ``foundry`` extra, so imports are guarded at call sites.
"""

# pyright: reportMissingImports=false

from __future__ import annotations

import time

from foundry.adapters.azure_openai import _raise_translated
from foundry.projects import FoundryProjectSettings
from shared.configuration import ModelDefinition
from shared.contracts import ModelProvider, TokenCounter
from shared.exceptions import ProviderError
from shared.types import ModelRequest, ModelResponse, TokenUsage

# Default agent persona when FOUNDRY_AGENT_INSTRUCTIONS is not supplied.
_DEFAULT_AGENT_INSTRUCTIONS = (
    "You are a post-call analytics assistant. Follow the task instructions in "
    "the user prompt exactly and return only the requested structured output."
)


class FoundryAgentProvider:
    """Adapter over the Foundry agent runtime (OpenAI Responses API).

    Uses ``DefaultAzureCredential`` via the project client so no secrets are
    handled in code. The agent persona is supplied as ``instructions`` on each
    request; the underlying deployment still performs the inference.
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
        self._instructions = settings.agent_instructions or _DEFAULT_AGENT_INSTRUCTIONS
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
                "to run in AZURE agent mode: uv sync --extra foundry"
            ) from exc

        if not settings.project_endpoint:
            raise ProviderError("FOUNDRY_PROJECT_ENDPOINT is not configured.")

        return AIProjectClient(
            endpoint=settings.project_endpoint,
            credential=DefaultAzureCredential(),
        )

    def complete(self, request: ModelRequest) -> ModelResponse:  # pragma: no cover
        # Live agent path. Exercised only against a real Foundry project.
        start = time.perf_counter()
        try:
            openai_client = self._client.get_openai_client()  # type: ignore[attr-defined]
            result = openai_client.responses.create(
                model=self._settings.model_name or self._deployment,
                instructions=request.system_prompt or self._instructions,
                input=request.prompt,
                max_output_tokens=request.max_output_tokens,
            )
            content = _output_text(result)
            usage = TokenUsage(
                prompt_tokens=getattr(result.usage, "input_tokens", 0),
                output_tokens=getattr(result.usage, "output_tokens", 0),
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


def _output_text(result: object) -> str:  # pragma: no cover - live call
    """Extract assistant text from a Responses API result."""
    text = getattr(result, "output_text", None)
    if text:
        return text
    parts: list[str] = []
    for item in getattr(result, "output", []) or []:
        for block in getattr(item, "content", []) or []:
            value = getattr(block, "text", None)
            if isinstance(value, str):
                parts.append(value)
    return "".join(parts)


def build_agent_provider(
    deployment: str,
    model: ModelDefinition,
    token_counter: TokenCounter,
) -> ModelProvider:
    """Construct a live Foundry agent provider from environment settings."""
    settings = FoundryProjectSettings.from_env()
    return FoundryAgentProvider(deployment, model, token_counter, settings)
