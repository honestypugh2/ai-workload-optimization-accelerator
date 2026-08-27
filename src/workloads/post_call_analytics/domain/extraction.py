"""Member-id extraction: naive baseline, deterministic optimized, and fallbacks.

* ``NaiveRegexExtractor`` models the reference baseline: a single regex over the
  raw transcript. It only recovers cleanly-formatted, contiguous ids (~30%).
* ``DeterministicMemberIdExtractor`` normalizes spoken digits and delimiters and
  reconstructs fragmented ids, reaching the optimized ~90% recall target.
* ``NerExtractorAdapter`` and ``LlmFallbackExtractorAdapter`` are documented,
  swappable placeholders that keep the pipeline extensible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Protocol

from optimization.preprocessing import normalize_spoken_digits
from shared.contracts import MemberIdExtractor
from shared.types import (
    ConfidenceTier,
    ExtractionCandidate,
    ExtractionResult,
    Transcript,
)

# A permissive candidate pattern: 2-4 letters followed by 6-12 digits.
_CLEAN_RE = re.compile(r"\b([A-Z]{2,4})[\s-]?(\d{6,12})\b")
_DIGIT_RUN_RE = re.compile(r"\d[\d ]*\d")


class CheckDigitValidator(Protocol):
    """Validates the integrity of a candidate member id (e.g. a check digit)."""

    def is_valid(self, member_id: str) -> bool: ...


@dataclass(slots=True)
class LuhnCheckDigitValidator:
    """Luhn (mod-10) validation over the numeric portion of a member id.

    Provided as a concrete, testable example of a check-digit gate. The real
    payer member-id algorithm is not published in the assessment, so this is
    disabled by default (limitation: wire the payer's actual algorithm here
    before enabling in production).
    """

    def is_valid(self, member_id: str) -> bool:
        digits = [int(c) for c in member_id if c.isdigit()]
        if not digits:
            return False
        total = 0
        for index, digit in enumerate(reversed(digits)):
            if index % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        return total % 10 == 0


def _empty(transcript_id: str) -> ExtractionResult:
    return ExtractionResult(
        transcript_id=transcript_id,
        member_id=None,
        confidence=0.0,
        tier=ConfidenceTier.LOW,
        provenance=(),
        candidates=(),
    )


class NaiveRegexExtractor:
    """Baseline extractor: a single regex over raw transcript text."""

    name = "naive_regex"

    def __init__(self, digit_length: int = 9) -> None:
        self._digit_length = digit_length

    def extract(self, transcript: Transcript) -> ExtractionResult:
        match = _CLEAN_RE.search(transcript.text)
        if not match:
            return _empty(transcript.transcript_id)
        digits = match.group(2)
        if len(digits) != self._digit_length:
            return _empty(transcript.transcript_id)
        value = f"{match.group(1)}{digits}"
        candidate = ExtractionCandidate(
            value=value,
            confidence=0.9,
            tier=ConfidenceTier.HIGH,
            source=self.name,
            evidence_span=match.group(0),
        )
        return ExtractionResult(
            transcript_id=transcript.transcript_id,
            member_id=value,
            confidence=candidate.confidence,
            tier=candidate.tier,
            provenance=(self.name,),
            candidates=(candidate,),
        )


@dataclass(slots=True)
class DeterministicMemberIdExtractor:
    """Optimized deterministic extractor with normalization and reconstruction."""

    digit_length: int = 9
    ner: MemberIdExtractor | None = None
    llm_fallback: MemberIdExtractor | None = None
    check_digit: CheckDigitValidator | None = None

    name: str = "deterministic"

    def extract(self, transcript: Transcript) -> ExtractionResult:
        normalized = self._normalize(transcript.text)
        candidate = self._match_contiguous(normalized) or self._reconstruct_fragmented(normalized)
        if candidate is None:
            # Extensible fallbacks (NER, then LLM) - disabled by default.
            for fallback in (self.ner, self.llm_fallback):
                if fallback is not None:
                    result = fallback.extract(transcript)
                    if result.member_id is not None:
                        return result
            return _empty(transcript.transcript_id)
        candidate = self._apply_check_digit(candidate)
        return ExtractionResult(
            transcript_id=transcript.transcript_id,
            member_id=candidate.value,
            confidence=candidate.confidence,
            tier=candidate.tier,
            provenance=(self.name, candidate.source),
            candidates=(candidate,),
        )

    def _apply_check_digit(self, candidate: ExtractionCandidate) -> ExtractionCandidate:
        """Downgrade a candidate that fails the configured check-digit gate."""
        if self.check_digit is None or self.check_digit.is_valid(candidate.value):
            return candidate
        return replace(
            candidate,
            confidence=min(candidate.confidence, 0.4),
            tier=ConfidenceTier.LOW,
            source=f"{candidate.source}+check_digit_failed",
        )

    def _normalize(self, text: str) -> str:
        t = normalize_spoken_digits(text)
        # Join spaced single uppercase letters: "M B R" -> "MBR". Restricting to
        # uppercase avoids absorbing lowercase word tails (e.g. the "s" in "it's").
        t = re.sub(r"\b([A-Z])(?:\s+([A-Z])\b)+", lambda m: m.group(0).replace(" ", ""), t)
        # Remove separators between a letter prefix and digits.
        t = re.sub(r"([A-Za-z])[\s\-]+(?=\d)", r"\1", t)
        # Collapse separators inside digit groups.
        t = re.sub(r"(?<=\d)[\s\-]+(?=\d)", "", t)
        return t

    def _match_contiguous(self, text: str) -> ExtractionCandidate | None:
        for match in _CLEAN_RE.finditer(text):
            digits = match.group(2)
            if len(digits) == self.digit_length:
                value = f"{match.group(1).upper()}{digits}"
                return ExtractionCandidate(
                    value=value,
                    confidence=0.92,
                    tier=ConfidenceTier.HIGH,
                    source="contiguous",
                    evidence_span=match.group(0),
                )
        return None

    def _reconstruct_fragmented(self, text: str) -> ExtractionCandidate | None:
        # Find a prefix followed by a partial digit run, then append the next
        # digit run(s) until the required length is reached.
        prefix_match = re.search(r"([A-Z]{2,4})(\d{2,})", text)
        if not prefix_match:
            return None
        prefix = prefix_match.group(1)
        digits = prefix_match.group(2)
        if len(digits) >= self.digit_length:
            return None  # would have matched contiguous
        tail_region = text[prefix_match.end() :]
        for run in _DIGIT_RUN_RE.findall(tail_region):
            digits += run.replace(" ", "")
            if len(digits) >= self.digit_length:
                break
        if len(digits) < self.digit_length:
            return None
        value = f"{prefix}{digits[: self.digit_length]}"
        return ExtractionCandidate(
            value=value,
            confidence=0.62,
            tier=ConfidenceTier.MEDIUM,
            source="fragment_reconstruction",
            evidence_span=f"{prefix}{digits}",
        )


@dataclass(slots=True)
class NerExtractorAdapter:
    """Placeholder NER-based extractor. Wire a real model behind this seam."""

    name: str = "ner"

    def extract(self, transcript: Transcript) -> ExtractionResult:  # pragma: no cover
        return _empty(transcript.transcript_id)


@dataclass(slots=True)
class LlmFallbackExtractorAdapter:
    """Placeholder LLM fallback extractor for the hardest transcripts."""

    name: str = "llm_fallback"

    def extract(self, transcript: Transcript) -> ExtractionResult:  # pragma: no cover
        return _empty(transcript.transcript_id)
