"""Shared execution helpers used by concrete strategies.

Keeps per-task model invocation, prompt caching, and chunk fan-out in one place
so individual strategies stay small and declarative.
"""

from __future__ import annotations

from optimization.base import ModelCall, StrategyContext
from optimization.chunking import get_chunker
from shared.types import ModelRequest, Transcript


def _prompt_for(ctx: StrategyContext, task: str, text: str, template: str) -> str:
    return template.replace("{transcript}", text) + f"\n\n[task={task}]"


def call_task(ctx: StrategyContext, task: str, text: str, template: str) -> ModelCall:
    """Invoke a single task, honouring the prompt cache when enabled."""
    prompt = _prompt_for(ctx, task, text, template)
    # Cache lookup and routing touch shared state; keep them under the lock so
    # concurrent transcripts see consistent hit-rate and dispatch accounting.
    with ctx.lock:
        cached = ctx.caches.prompt_cache.get(prompt)
        if cached is None and ctx.caches.semantic_cache.enabled:
            cached = ctx.caches.semantic_cache.get(prompt)
        if cached is not None:
            return ModelCall(
                task=task,
                deployment="cache",
                prompt_tokens=0,
                output_tokens=0,
                latency_ms=0.5,
                from_cache=True,
            )
        request = ModelRequest(prompt=prompt, task=task)
        provider = ctx.router.route(request)
    # The model call is the slow, I/O-bound step; run it outside the lock so
    # concurrent transcripts overlap their requests.
    response = provider.complete(request)
    with ctx.lock:
        ctx.caches.prompt_cache.put(prompt, response.content)
        ctx.caches.semantic_cache.put(prompt, response.content)
    return ModelCall(
        task=task,
        deployment=response.deployment,
        prompt_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=response.latency_ms,
        from_cache=False,
    )


def process_over_chunks(
    ctx: StrategyContext,
    transcript: Transcript,
    text: str,
    tasks: tuple[str, ...],
    template: str,
) -> list[ModelCall]:
    """Run ``tasks`` over the transcript, chunking when a chunker is configured."""
    calls: list[ModelCall] = []
    if ctx.chunker_name:
        chunker = get_chunker(ctx.chunker_name)
        chunks = chunker.split(
            Transcript(transcript_id=transcript.transcript_id, utterances=transcript.utterances),
            ctx.token_counter,
        )
        # Map: analytic tasks run per map-chunk; reduce chunk runs summary/evidence once.
        for chunk in chunks:
            chunk_tasks = ("summary", "evidence") if chunk.is_reduce else tasks
            for task in chunk_tasks:
                calls.append(call_task(ctx, task, chunk.text, template))
    else:
        for task in tasks:
            calls.append(call_task(ctx, task, text, template))
    return calls
