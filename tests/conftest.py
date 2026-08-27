"""Shared pytest fixtures for the accelerator test suite."""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from shared.types import Speaker, Transcript, Utterance
from workloads.post_call_analytics.domain.member_id import MemberIdFormat


@pytest.fixture
def rng() -> random.Random:
    return random.Random(20240501)


@pytest.fixture
def id_format() -> MemberIdFormat:
    return MemberIdFormat()


TranscriptBuilder = Callable[..., Transcript]


@pytest.fixture
def make_transcript() -> TranscriptBuilder:
    """Return a builder for minimal labeled transcripts."""

    def _build(
        transcript_id: str,
        member_utterance: str,
        *,
        gold: str | None,
        extra: list[tuple[Speaker, str]] | None = None,
    ) -> Transcript:
        utterances = [
            Utterance(Speaker.AGENT, "Can you read me your member identification number?"),
            Utterance(Speaker.MEMBER, member_utterance),
        ]
        for speaker, text in extra or []:
            utterances.append(Utterance(speaker, text))
        return Transcript(
            transcript_id=transcript_id,
            utterances=tuple(utterances),
            member_id_gold=gold,
        )

    return _build
