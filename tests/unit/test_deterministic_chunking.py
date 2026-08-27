"""The deterministic_first strategy honours the configured chunker."""

from __future__ import annotations

from foundry.model_catalog import ApproxTokenCounter
from optimization.base import PromptBundle, StrategyContext
from optimization.caching import CacheBundle
from optimization.routing import build_router
from registry.strategy_registry import strategy_registry
from shared.configuration import ModelDefinition, ModelMapping
from shared.contracts import ModelProvider
from shared.types import Speaker, Transcript, Utterance


def _providers(n: int = 1) -> list[ModelProvider]:
    from foundry.adapters.mock import MockModelProvider

    return [
        MockModelProvider(
            f"dep-{i}", ModelDefinition(name=f"dep-{i}", role="test"), ApproxTokenCounter()
        )
        for i in range(n)
    ]


def _context(chunker_name: str | None) -> StrategyContext:
    return StrategyContext(
        router=build_router("single_deployment", _providers()),
        token_counter=ApproxTokenCounter(),
        mapping=ModelMapping(),
        caches=CacheBundle.from_flags([]),
        prompts=PromptBundle(),
        extractor=None,
        chunker_name=chunker_name,
    )


def _transcript(turns: int) -> Transcript:
    utterances = tuple(
        Utterance(
            Speaker.MEMBER if i % 2 else Speaker.AGENT,
            f"Turn {i}: the member asks about a claim and eligibility with several words here.",
        )
        for i in range(turns)
    )
    return Transcript("det-chunk", utterances)


def _strategy():
    return strategy_registry.get("deterministic_first")()


def test_unchunked_path_makes_the_classic_call_set() -> None:
    # Short transcript, no chunker: 4 analytic tasks + 1 extraction fallback.
    outcome = _strategy().process(_transcript(4), _context(None))
    assert len(outcome.calls) == 5


def test_chunker_fans_out_calls() -> None:
    transcript = _transcript(300)
    unchunked = _strategy().process(transcript, _context(None))
    chunked = _strategy().process(transcript, _context("speaker_aware"))
    assert len(chunked.calls) > len(unchunked.calls)
