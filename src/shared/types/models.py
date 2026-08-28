"""Immutable internal domain value objects.

These are lightweight ``dataclasses`` (not pydantic) because they represent
internal, already-validated domain state rather than untrusted external input.
External configuration is validated with pydantic in ``shared.configuration``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ExecutionMode(StrEnum):
    """How model calls are executed during a benchmark run."""

    LOCAL = "local"
    """Fully synthetic, deterministic mock providers. No network access."""

    DRY_RUN = "dry-run"
    """Plan the run and estimate metrics without invoking any provider."""

    AZURE = "azure"
    """Invoke real Microsoft Foundry / Azure OpenAI deployments."""


class ConfidenceTier(StrEnum):
    """Confidence bucket for an extraction result."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Speaker(StrEnum):
    """Speaker role in a call transcript."""

    AGENT = "agent"
    MEMBER = "member"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Utterance:
    """A single turn in a call transcript."""

    speaker: Speaker
    text: str
    start_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class Transcript:
    """A synthetic call-center transcript.

    ``member_id_gold`` is the ground-truth synthetic member id (may be ``None``
    when the call has no recoverable identifier). It is only present in labeled
    datasets used for evaluation.
    """

    transcript_id: str
    utterances: tuple[Utterance, ...]
    member_id_gold: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Flattened transcript text with speaker prefixes."""
        return "\n".join(f"{u.speaker.value}: {u.text}" for u in self.utterances)


@dataclass(frozen=True, slots=True)
class ExtractionCandidate:
    """A candidate member id produced by an extraction strategy."""

    value: str
    confidence: float
    tier: ConfidenceTier
    source: str
    evidence_span: str = ""


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """The resolved extraction outcome for a transcript."""

    transcript_id: str
    member_id: str | None
    confidence: float
    tier: ConfidenceTier
    provenance: tuple[str, ...] = ()
    candidates: tuple[ExtractionCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token accounting for a single model interaction."""

    prompt_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """A response returned by a model provider."""

    content: str
    usage: TokenUsage
    deployment: str
    latency_ms: float
    from_cache: bool = False


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """A request sent to a model provider."""

    prompt: str
    task: str = "generic"
    max_output_tokens: int = 512
    # Optional system message. When set, providers send it as a system role
    # ahead of the user prompt so live runs exercise production-style prompting.
    system_prompt: str | None = None
