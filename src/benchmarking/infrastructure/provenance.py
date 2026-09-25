"""Collects run provenance: config fingerprints, code version, and targets.

Everything here is best-effort and offline-safe: a missing git checkout or
package metadata yields ``None`` rather than failing the benchmark.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from benchmarking.domain import RunProvenance
from foundry.adapters import resolve_endpoint_host, resolve_model_deployments
from shared.configuration import BenchmarkConfig, DeploymentProfile, ModelDefinition
from shared.timing import clock_name
from shared.types import ExecutionMode

_PACKAGE = "ai-workload-optimization-accelerator"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str | None:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError:
        return None


def config_fingerprint(config: BenchmarkConfig) -> str:
    """Stable hash of the *effective* config (after CLI overrides)."""
    canonical = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(canonical.encode("utf-8"))


def _git(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=5, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def _git_state() -> tuple[str | None, bool | None]:
    commit = _git("rev-parse", "HEAD")
    if not commit:
        return None, None
    status = _git("status", "--porcelain", "--untracked-files=no")
    return commit, (bool(status) if status is not None else None)


def _package_version() -> str | None:
    try:
        return metadata.version(_PACKAGE)
    except metadata.PackageNotFoundError:
        return None


def collect_provenance(
    *,
    config: BenchmarkConfig,
    mode: ExecutionMode,
    scenario_root: Path,
    models: dict[str, ModelDefinition],
    profile: DeploymentProfile,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    config_execution_mode: str | None = None,
) -> RunProvenance:
    commit, dirty = _git_state()
    pricing_path = scenario_root / config.pricing_file
    return RunProvenance(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        accelerator_version=_package_version(),
        git_commit=commit,
        git_dirty=dirty,
        config_path=str(config_path) if config_path is not None else None,
        config_sha256=config_fingerprint(config),
        config_overrides=dict(overrides or {}),
        config_execution_mode=config_execution_mode,
        effective_config=config.model_dump(mode="json"),
        scenario_sha256=_sha256_file(scenario_root / "scenario.yaml"),
        pricing_file=config.pricing_file,
        pricing_sha256=_sha256_file(pricing_path),
        deployment_profile=profile.model_dump(mode="json"),
        model_deployments=resolve_model_deployments(models, mode),
        endpoint_host=resolve_endpoint_host(mode),
        timing_clock=clock_name(),
    )
