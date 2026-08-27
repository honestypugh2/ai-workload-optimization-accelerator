"""Wiring helpers that assemble providers, routers, and quota models.

Isolated here so the runner stays focused on orchestration. All Azure specifics
remain behind ``foundry.build_provider`` (which only touches Azure in AZURE mode).
"""

from __future__ import annotations

from foundry import build_provider
from foundry.model_catalog import ApproxTokenCounter
from optimization.routing import (
    DeploymentState,
    QuotaModel,
    Router,
    build_router,
)
from shared.configuration import (
    DeploymentProfile,
    ModelCatalog,
    ModelMapping,
    ScenarioConfig,
)
from shared.contracts import ModelProvider
from shared.types import ExecutionMode

# Maps a strategy task name to the mapping field that selects its model alias.
_TASK_TO_FIELD = {
    "sentiment": "sentiment_model",
    "escalation": "escalation_model",
    "summary": "summary_model",
    "evidence": "evidence_model",
    "extraction": "extraction_model",
}


def task_alias_map(mapping: ModelMapping) -> dict[str, str]:
    """Return {task: model_alias} from a mapping."""
    return {task: getattr(mapping, field) for task, field in _TASK_TO_FIELD.items()}


def build_providers(
    catalog: ModelCatalog,
    mapping: ModelMapping,
    token_counter: ApproxTokenCounter,
    mode: ExecutionMode,
) -> dict[str, ModelProvider]:
    """Build one provider per distinct model alias used by the mapping."""
    aliases = set(task_alias_map(mapping).values())
    providers: dict[str, ModelProvider] = {}
    for alias in sorted(aliases):
        model = catalog.get(alias)
        providers[alias] = build_provider(alias, model, token_counter, mode=mode)
    return providers


def build_quota_model(
    providers: dict[str, ModelProvider],
    profile: DeploymentProfile,
) -> QuotaModel:
    """Build a quota model. Shared quota splits the limit across deployments."""
    count = max(1, profile.deployment_count)
    per_deployment = (
        profile.tokens_per_minute_limit // count
        if profile.shared_quota
        else profile.tokens_per_minute_limit
    )
    return QuotaModel(
        states={name: DeploymentState(name, tpm_limit=per_deployment) for name in providers}
    )


def build_states(quota: QuotaModel) -> dict[str, DeploymentState]:
    return quota.states


def assemble_router(
    routing: str,
    providers: dict[str, ModelProvider],
    mapping: ModelMapping,
    quota: QuotaModel,
    ptu_deployment: str | None,
) -> Router:
    """Construct the requested router from built providers and quota state."""
    provider_list = list(providers.values())
    return build_router(
        routing,
        provider_list,
        states=quota.states,
        task_map=task_alias_map(mapping),
        ptu_deployment=ptu_deployment,
    )


def resolve_scenario_deployment_profile(
    scenario: ScenarioConfig, overrides: dict
) -> DeploymentProfile:
    """Apply benchmark deployment overrides onto the scenario profile."""
    base = scenario.deployment_profile.model_dump()
    base.update({k: v for k, v in overrides.items() if k in base})
    return DeploymentProfile.model_validate(base)
