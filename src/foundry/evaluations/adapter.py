"""Foundry evaluation adapter.

Provides a thin seam over Microsoft Foundry evaluation capabilities. It is
optional: local evaluation runs entirely on the deterministic evaluators in
``evaluation``. When Foundry is unavailable, ``FoundryEvaluationAdapter`` reports
``available == False`` and callers fall back to local evaluators.
"""

# azure.ai.projects is optional (installed via the ``foundry`` extra); its import
# is guarded at the call site, so missing-import diagnostics are expected.
# pyright: reportMissingImports=false

from __future__ import annotations

from dataclasses import dataclass

from foundry.projects import FoundryProjectSettings


@dataclass(frozen=True, slots=True)
class FoundryEvaluationAdapter:
    """Optional adapter that delegates evaluation to Microsoft Foundry."""

    settings: FoundryProjectSettings

    @classmethod
    def from_env(cls) -> FoundryEvaluationAdapter:
        return cls(settings=FoundryProjectSettings.from_env())

    @property
    def available(self) -> bool:
        """True only when a project endpoint and the SDK are both present."""
        if not self.settings.is_configured:
            return False
        try:
            import azure.ai.projects  # noqa: F401
        except ImportError:
            return False
        return True

    def evaluate(self, dataset_path: str, evaluators: list[str]) -> dict:  # pragma: no cover
        """Run a Foundry-hosted evaluation.

        Intentionally a stub: wire up ``azure.ai.projects`` evaluations when
        running against a live project. Local runs never reach this path.
        """
        if not self.available:
            raise RuntimeError(
                "Foundry evaluation is not available. Configure FOUNDRY_PROJECT_ENDPOINT "
                "and install the 'foundry' extra, or use local evaluators."
            )
        raise NotImplementedError(
            "Foundry-hosted evaluation is a documented extension point. "
            "Local deterministic evaluators cover the accelerator's default path."
        )
