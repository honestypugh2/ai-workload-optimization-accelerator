"""Chunking strategy tests."""

from __future__ import annotations

import pytest

from foundry.model_catalog import ApproxTokenCounter
from optimization.chunking import available_chunkers, get_chunker
from optimization.chunking.chunkers import (
    FixedSizeChunker,
    FixedSizeOverlapChunker,
    RecursiveChunker,
)
from shared.exceptions import ConfigurationError
from shared.types import Speaker, Transcript, Utterance

EXPECTED = {
    "full",
    "fixed",
    "fixed_overlap",
    "sentence",
    "recursive",
    "speaker_aware",
    "semantic",
    "semantic_embedding",
    "hierarchical",
    "map_reduce",
}


def _transcript() -> Transcript:
    utterances = tuple(
        Utterance(
            Speaker.MEMBER if i % 2 else Speaker.AGENT,
            f"This is turn number {i} with several words to fill the token budget.",
        )
        for i in range(40)
    )
    return Transcript("chunk-t", utterances)


def test_all_expected_chunkers_registered() -> None:
    assert EXPECTED.issubset(set(available_chunkers()))


def test_full_chunker_returns_single_chunk() -> None:
    chunks = get_chunker("full").split(_transcript(), ApproxTokenCounter())
    assert len(chunks) == 1


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_chunker_produces_nonempty_chunks(name: str) -> None:
    chunks = get_chunker(name).split(_transcript(), ApproxTokenCounter())
    assert chunks
    assert all(c.text for c in chunks)


def test_map_reduce_has_reduce_step() -> None:
    chunks = get_chunker("map_reduce").split(_transcript(), ApproxTokenCounter())
    assert any(c.is_reduce for c in chunks)


def test_fixed_overlap_repeats_boundary_context() -> None:
    counter = ApproxTokenCounter()
    transcript = _transcript()
    plain = FixedSizeChunker(max_tokens=60).split(transcript, counter)
    overlap_chunker = FixedSizeOverlapChunker(max_tokens=60, overlap_tokens=15)
    overlapped = overlap_chunker.split(transcript, counter)
    assert len(plain) >= 2
    # Overlap re-sends boundary tokens, so consecutive chunks share a word.
    assert len(overlapped) >= len(plain)
    first_tail = overlapped[0].text.split()[-1]
    assert first_tail in overlapped[1].text.split()


def test_sentence_chunker_never_splits_mid_sentence() -> None:
    utterances = tuple(
        Utterance(Speaker.AGENT, f"Sentence number {i} ends here. Another clause follows now.")
        for i in range(20)
    )
    chunks = get_chunker("sentence").split(Transcript("s-t", utterances), ApproxTokenCounter())
    assert chunks
    for chunk in chunks:
        assert chunk.text.strip()[-1] in ".!?"


def test_recursive_chunker_respects_token_budget() -> None:
    counter = ApproxTokenCounter()
    chunks = RecursiveChunker(max_tokens=80).split(_transcript(), counter)
    assert len(chunks) >= 2
    assert all(counter.count(c.text) <= 80 for c in chunks)


def test_semantic_embedding_falls_back_without_model() -> None:
    # sentence-transformers is not a test dependency, so this exercises the
    # keyword-heuristic fallback path and must still produce usable chunks.
    chunks = get_chunker("semantic_embedding").split(_transcript(), ApproxTokenCounter())
    assert chunks
    assert all(c.text for c in chunks)


def test_unknown_chunker_raises() -> None:
    with pytest.raises(ConfigurationError):
        get_chunker("does-not-exist")
