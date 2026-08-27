"""Provisioned Throughput Unit (PTU) sizing and cost simulation.

Estimates how many PTUs are required to sustain a target throughput and compares
PTU (reserved) economics against Standard/PayGo for a given daily token volume.
All rates are configuration-driven; nothing is hardcoded to a real price.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PtuSizingInput:
    """Inputs for a PTU sizing calculation."""

    peak_tokens_per_minute: int
    tokens_per_minute_per_ptu: int
    utilization_target: float = 0.75

    def __post_init__(self) -> None:
        if self.tokens_per_minute_per_ptu <= 0:
            raise ValueError("tokens_per_minute_per_ptu must be positive.")
        if not 0 < self.utilization_target <= 1:
            raise ValueError("utilization_target must be in (0, 1].")


@dataclass(frozen=True, slots=True)
class PtuSizingResult:
    """Result of PTU sizing."""

    required_ptus: int
    effective_capacity_tpm: int
    headroom_tpm: int


def size_ptus(inputs: PtuSizingInput) -> PtuSizingResult:
    """Compute the number of PTUs needed to meet peak demand at target utilization."""
    effective_per_ptu = inputs.tokens_per_minute_per_ptu * inputs.utilization_target
    required = max(1, int(-(-inputs.peak_tokens_per_minute // effective_per_ptu)))
    capacity = required * inputs.tokens_per_minute_per_ptu
    headroom = capacity - inputs.peak_tokens_per_minute
    return PtuSizingResult(
        required_ptus=required,
        effective_capacity_tpm=int(capacity),
        headroom_tpm=int(headroom),
    )


@dataclass(frozen=True, slots=True)
class PtuCostComparison:
    """Monthly cost comparison of PTU vs Standard for a workload."""

    ptu_monthly_cost: float
    standard_monthly_cost: float

    @property
    def cheaper_option(self) -> str:
        return "ptu" if self.ptu_monthly_cost <= self.standard_monthly_cost else "standard"

    @property
    def monthly_savings(self) -> float:
        return abs(self.ptu_monthly_cost - self.standard_monthly_cost)


def compare_ptu_vs_standard(
    *,
    required_ptus: int,
    ptu_monthly_price_per_unit: float,
    monthly_tokens: int,
    standard_price_per_1k: float,
) -> PtuCostComparison:
    """Compare reserved PTU cost against per-token Standard cost for a month."""
    ptu_cost = required_ptus * ptu_monthly_price_per_unit
    standard_cost = (monthly_tokens / 1000.0) * standard_price_per_1k
    return PtuCostComparison(ptu_monthly_cost=ptu_cost, standard_monthly_cost=standard_cost)
