"""OpenAI-compatible gateway settings (LiteLLM proxy or APIM AI Gateway).

Both LiteLLM and APIM expose the OpenAI Chat Completions protocol, so a single
provider targets either one by pointing ``base_url`` at the proxy/gateway. All
values are read from the environment; secrets are never stored in code.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from shared.exceptions import ConfigurationError

# Recognised gateway kinds. ``direct`` bypasses any gateway and uses the native
# Foundry project client; ``litellm`` and ``apim`` use the OpenAI-compatible path.
_GATEWAY_KINDS = frozenset({"direct", "litellm", "apim"})


@dataclass(frozen=True, slots=True)
class GatewaySettings:
    """Connection settings for an OpenAI-compatible AI gateway."""

    kind: str
    base_url: str | None
    api_key: str | None
    api_key_header: str
    api_version: str | None
    use_aad: bool
    deployments: dict[str, str]
    max_retries: int
    base_backoff_s: float

    @classmethod
    def from_env(cls) -> GatewaySettings:
        kind = (os.environ.get("AIWOA_GATEWAY_KIND") or "direct").strip().lower()
        if kind not in _GATEWAY_KINDS:
            raise ConfigurationError(
                f"AIWOA_GATEWAY_KIND='{kind}' is invalid; expected one of {sorted(_GATEWAY_KINDS)}."
            )
        return cls(
            kind=kind,
            base_url=os.environ.get("AIWOA_GATEWAY_BASE_URL") or None,
            api_key=os.environ.get("AIWOA_GATEWAY_API_KEY") or None,
            api_key_header=os.environ.get("AIWOA_GATEWAY_API_KEY_HEADER") or "Authorization",
            api_version=os.environ.get("AIWOA_GATEWAY_API_VERSION") or None,
            use_aad=_env_flag("AIWOA_GATEWAY_USE_AAD"),
            deployments=_parse_deployments(os.environ.get("AIWOA_GATEWAY_DEPLOYMENTS")),
            max_retries=_env_int("AIWOA_GATEWAY_MAX_RETRIES", 5),
            base_backoff_s=_env_float("AIWOA_GATEWAY_BASE_BACKOFF_S", 0.5),
        )

    @property
    def is_gateway(self) -> bool:
        """True when requests should route through an OpenAI-compatible gateway."""
        return self.kind in {"litellm", "apim"}

    def model_for(self, alias: str) -> str:
        """Resolve a catalog alias to its gateway model/deployment name."""
        return self.deployments.get(alias, alias)


def _parse_deployments(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            "AIWOA_GATEWAY_DEPLOYMENTS must be a JSON object mapping alias -> model name."
        ) from exc
    if not isinstance(parsed, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()
    ):
        raise ConfigurationError(
            "AIWOA_GATEWAY_DEPLOYMENTS must be a JSON object of string keys and values."
        )
    return parsed


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got '{raw}'.") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number, got '{raw}'.") from exc
