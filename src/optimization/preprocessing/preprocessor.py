"""Transcript preprocessing and context minimization.

Removes repeated boilerplate, collapses noise, normalizes spoken digits, and
optionally keeps only the utterances most relevant to downstream analysis. These
transforms reduce prompt tokens while preserving signal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from shared.types import Speaker, Transcript, Utterance

_BOILERPLATE_PATTERNS = (
    re.compile(r"\bthis call may be recorded\b", re.IGNORECASE),
    re.compile(r"\bfor quality (and|&) training purposes\b", re.IGNORECASE),
    re.compile(r"\bplease listen carefully as our menu options\b", re.IGNORECASE),
    re.compile(r"\byour call is important to us\b", re.IGNORECASE),
)
_FILLER_RE = re.compile(r"\b(uh+|um+|er+|hmm+|you know|like)\b", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")

# Deterministic PII/PHI patterns. Ordered so multi-field spans are masked before
# their fragments. These cover structured identifiers only; free-form names and
# addresses require an NER model (see ``redact_pii`` limitation note).
_PII_PATTERNS = (
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b\d{13,16}\b"), "[CARD]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    (re.compile(r"\b(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"), "[PHONE]"),
)

_SPOKEN_DIGITS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}

_RELEVANCE_KEYWORDS = (
    "member",
    "id",
    "identification",
    "claim",
    "eligib",
    "benefit",
    "authoriz",
    "escalat",
    "supervisor",
    "billing",
    "provider",
)


@dataclass(frozen=True, slots=True)
class PreprocessResult:
    """Outcome of preprocessing, with before/after token accounting."""

    transcript: Transcript
    original_tokens: int
    reduced_tokens: int

    @property
    def reduction_ratio(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return 1.0 - (self.reduced_tokens / self.original_tokens)


def normalize_spoken_digits(text: str) -> str:
    """Convert spoken digit words into numerals (e.g. 'one two three' -> '123')."""

    def repl(match: re.Match[str]) -> str:
        return _SPOKEN_DIGITS[match.group(0).lower()]

    pattern = re.compile(r"\b(" + "|".join(_SPOKEN_DIGITS) + r")\b", re.IGNORECASE)
    # Join sequences of converted digits without spaces.
    converted = pattern.sub(repl, text)
    return re.sub(r"(?<=\d) (?=\d)", "", converted)


def redact_pii(text: str) -> str:
    """Mask common PII/PHI spans (SSN, card, email, phone) via deterministic regex.

    Moves PHI handling off the LLM and reduces compliance exposure. Production
    would use Azure AI Language PII detection for higher recall across names,
    addresses, and dates (limitation: this local version covers structured
    identifiers only and does not call any Azure service).
    """
    redacted = text
    for pattern, token in _PII_PATTERNS:
        redacted = pattern.sub(token, redacted)
    return redacted


def _clean_text(text: str) -> str:
    cleaned = text
    for pattern in _BOILERPLATE_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = _FILLER_RE.sub("", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def _is_relevant(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _RELEVANCE_KEYWORDS)


class TranscriptPreprocessor:
    """Cleans and optionally minimizes a transcript."""

    def __init__(
        self,
        *,
        remove_boilerplate: bool = True,
        normalize_digits: bool = True,
        selective_context: bool = False,
        redact_pii: bool = False,
    ) -> None:
        self._remove_boilerplate = remove_boilerplate
        self._normalize_digits = normalize_digits
        self._selective_context = selective_context
        self._redact_pii = redact_pii

    def run(self, transcript: Transcript, token_counter) -> PreprocessResult:
        original_tokens = token_counter.count(transcript.text)
        utterances: list[Utterance] = []
        for utt in transcript.utterances:
            text = utt.text
            if self._redact_pii:
                text = redact_pii(text)
            if self._remove_boilerplate:
                text = _clean_text(text)
            if self._normalize_digits:
                text = normalize_spoken_digits(text)
            if not text:
                continue
            if (
                self._selective_context
                and utt.speaker is not Speaker.MEMBER
                and not _is_relevant(text)
            ):
                continue
            utterances.append(
                Utterance(speaker=utt.speaker, text=text, start_seconds=utt.start_seconds)
            )
        reduced = Transcript(
            transcript_id=transcript.transcript_id,
            utterances=tuple(utterances),
            member_id_gold=transcript.member_id_gold,
            metadata=dict(transcript.metadata),
        )
        reduced_tokens = token_counter.count(reduced.text)
        return PreprocessResult(
            transcript=reduced,
            original_tokens=original_tokens,
            reduced_tokens=reduced_tokens,
        )
