"""Synthetic member identifier model and formatting.

Generates entirely fake, configurable member identifiers and renders them in the
various spoken/written forms a call transcript contains. No real member IDs,
names, or PHI are ever produced.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum

_DIGIT_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


class IdPresentation(StrEnum):
    """How a member id appears in a transcript."""

    CLEAN = "clean"
    """Contiguous, correctly formatted (recoverable by naive regex)."""

    DASHED = "dashed"
    """Separated by dashes or spaces."""

    SPOKEN = "spoken"
    """Read out as spoken digit words."""

    FRAGMENTED = "fragmented"
    """Broken across utterances with ASR-style noise."""

    MISSING = "missing"
    """No recoverable identifier present."""


@dataclass(frozen=True, slots=True)
class MemberIdFormat:
    """Configurable fake member-id format (letters prefix + digits)."""

    prefixes: tuple[str, ...] = ("MBR", "HPL", "SVC")
    digit_length: int = 9

    def generate(self, rng: random.Random) -> str:
        prefix = rng.choice(self.prefixes)
        digits = "".join(str(rng.randint(0, 9)) for _ in range(self.digit_length))
        return f"{prefix}{digits}"


def _split_prefix_digits(member_id: str) -> tuple[str, str]:
    idx = 0
    while idx < len(member_id) and member_id[idx].isalpha():
        idx += 1
    return member_id[:idx], member_id[idx:]


def render_clean(member_id: str) -> str:
    return member_id


def render_dashed(member_id: str, rng: random.Random) -> str:
    prefix, digits = _split_prefix_digits(member_id)
    sep = rng.choice(["-", " ", " - "])
    grouped = sep.join(digits[i : i + 3] for i in range(0, len(digits), 3))
    return f"{prefix}{sep}{grouped}"


def render_spoken(member_id: str) -> str:
    prefix, digits = _split_prefix_digits(member_id)
    spoken = " ".join(_DIGIT_WORDS[d] for d in digits)
    letters = " ".join(prefix)
    return f"{letters} {spoken}"


def render_fragmented(member_id: str, rng: random.Random) -> tuple[str, str]:
    """Return two fragments simulating a value broken across utterances."""
    prefix, digits = _split_prefix_digits(member_id)
    cut = rng.randint(2, max(2, len(digits) - 2))
    first = f"{prefix} {digits[:cut]}"
    # Inject a plausible ASR slip on the tail fragment.
    tail = digits[cut:]
    if rng.random() < 0.3 and len(tail) > 1:
        pos = rng.randrange(len(tail))
        wrong = str((int(tail[pos]) + 1) % 10)
        tail = tail[:pos] + wrong + tail[pos + 1 :]
    second = f"and then {tail}"
    return first, second
