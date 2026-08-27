"""Chunking strategies for long transcripts.

Provides multiple chunkers used to compare cost/quality trade-offs: full
transcript, fixed-size (with and without overlap), sentence/context-aware,
recursive, speaker-aware, semantic (keyword heuristic and embedding-based),
hierarchical, and map-reduce. Each chunker turns a transcript into a list of
text chunks; the map-reduce chunker additionally signals a reduce step.

The default implementations are dependency-free native Python so local
benchmarking works without extra installs. A few chunkers transparently use
popular libraries when they are available (installed via the optional
``chunking`` extra) and fall back to the native path otherwise:

- ``sentence`` uses NLTK's Punkt tokenizer when present, else a regex splitter.
- ``recursive`` uses LangChain's ``RecursiveCharacterTextSplitter`` when present,
  else a native token-budgeted recursive splitter.
- ``semantic_embedding`` uses sentence-transformers embeddings when present, else
  falls back to the ``semantic`` keyword heuristic.
"""

# pyright: reportMissingImports=false
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from math import sqrt
from typing import Any, ClassVar

from shared.contracts import TokenCounter
from shared.exceptions import ConfigurationError
from shared.types import Transcript

# Separator hierarchy for recursive splitting, coarsest to finest.
_RECURSIVE_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", " ", "")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, preferring NLTK Punkt when available."""
    stripped = text.strip()
    if not stripped:
        return []
    try:
        import nltk

        return [s for s in nltk.sent_tokenize(stripped) if s.strip()]
    except Exception:
        # NLTK missing or Punkt data not downloaded: fall back to regex.
        return [s for s in _SENTENCE_RE.split(stripped) if s.strip()]


def _pack_by_budget(
    units: list[str],
    token_counter: TokenCounter,
    max_tokens: int,
    joiner: str = " ",
) -> list[str]:
    """Greedily pack text units into chunks that stay within a token budget."""
    chunks: list[str] = []
    buffer: list[str] = []
    for unit in units:
        if buffer and token_counter.count(joiner.join([*buffer, unit])) > max_tokens:
            chunks.append(joiner.join(buffer))
            buffer = []
        buffer.append(unit)
    if buffer:
        chunks.append(joiner.join(buffer))
    return chunks


def _cosine(a: Any, b: Any) -> float:
    """Cosine similarity for two equal-length numeric sequences (native)."""
    dot = sum(float(x) * float(y) for x, y in zip(a, b, strict=False))
    na = sqrt(sum(float(x) * float(x) for x in a))
    nb = sqrt(sum(float(y) * float(y) for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@lru_cache(maxsize=1)
def _load_embedding_model(name: str = "all-MiniLM-L6-v2") -> Any | None:
    """Load a sentence-transformers model if the library is installed, else None."""
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(name)
    except Exception:  # pragma: no cover - exercised only when the lib is absent
        return None


@dataclass(frozen=True, slots=True)
class Chunk:
    """A unit of transcript text to be processed by the model."""

    index: int
    text: str
    is_reduce: bool = False


class Chunker(ABC):
    """Splits a transcript into processable chunks."""

    name: ClassVar[str]

    @abstractmethod
    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        raise NotImplementedError


class FullTranscriptChunker(Chunker):
    """No chunking: the entire transcript is a single chunk."""

    name = "full"

    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        return [Chunk(index=0, text=transcript.text)]


class FixedSizeChunker(Chunker):
    """Splits into fixed token-budget chunks by word windows."""

    name = "fixed"

    def __init__(self, max_tokens: int = 1200) -> None:
        self._max_tokens = max_tokens

    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        words = transcript.text.split()
        chunks: list[Chunk] = []
        window: list[str] = []
        idx = 0
        for word in words:
            window.append(word)
            if token_counter.count(" ".join(window)) >= self._max_tokens:
                chunks.append(Chunk(index=idx, text=" ".join(window)))
                idx += 1
                window = []
        if window:
            chunks.append(Chunk(index=idx, text=" ".join(window)))
        return chunks or [Chunk(index=0, text=transcript.text)]


class FixedSizeOverlapChunker(Chunker):
    """Fixed token-budget chunks that carry a sliding overlap between windows.

    Overlap preserves context that would otherwise be cut at a chunk boundary,
    at the cost of re-sending the overlapping tokens. ``overlap_tokens`` of 0 is
    equivalent to :class:`FixedSizeChunker`.
    """

    name = "fixed_overlap"

    def __init__(self, max_tokens: int = 1200, overlap_tokens: int = 150) -> None:
        self._max_tokens = max_tokens
        self._overlap_tokens = max(0, min(overlap_tokens, max_tokens - 1))

    def _overlap_tail(self, window: list[str], token_counter: TokenCounter) -> list[str]:
        tail: list[str] = []
        for word in reversed(window):
            candidate = [word, *tail]
            if token_counter.count(" ".join(candidate)) > self._overlap_tokens:
                break
            tail = candidate
        return tail

    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        words = transcript.text.split()
        chunks: list[Chunk] = []
        window: list[str] = []
        idx = 0
        new_since_emit = 0
        for word in words:
            window.append(word)
            new_since_emit += 1
            if token_counter.count(" ".join(window)) >= self._max_tokens:
                chunks.append(Chunk(index=idx, text=" ".join(window)))
                idx += 1
                window = self._overlap_tail(window, token_counter) if self._overlap_tokens else []
                new_since_emit = 0
        if new_since_emit:
            chunks.append(Chunk(index=idx, text=" ".join(window)))
        return chunks or [Chunk(index=0, text=transcript.text)]


class SentenceChunker(Chunker):
    """Context-aware chunking that never splits mid-sentence.

    Sentences are detected with NLTK's Punkt tokenizer when available and a
    regex fallback otherwise, then packed into token-budgeted chunks.
    """

    name = "sentence"

    def __init__(self, max_tokens: int = 1200) -> None:
        self._max_tokens = max_tokens

    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        sentences = _split_sentences(transcript.text)
        packed = _pack_by_budget(sentences, token_counter, self._max_tokens)
        return [Chunk(index=i, text=text) for i, text in enumerate(packed)] or [
            Chunk(index=0, text=transcript.text)
        ]


class RecursiveChunker(Chunker):
    """Recursively split on a separator hierarchy until chunks fit the budget.

    Mirrors LangChain's ``RecursiveCharacterTextSplitter`` and delegates to it
    when the library is installed; otherwise uses a native token-budgeted
    implementation that walks paragraph -> line -> sentence -> word -> character.
    """

    name = "recursive"

    def __init__(self, max_tokens: int = 1200) -> None:
        self._max_tokens = max_tokens

    def _native_split(
        self,
        text: str,
        token_counter: TokenCounter,
        separators: tuple[str, ...],
    ) -> list[str]:
        if token_counter.count(text) <= self._max_tokens or not text:
            return [text]
        for i, sep in enumerate(separators):
            if sep == "":
                # Last resort: hard character windows.
                return _pack_by_budget(list(text), token_counter, self._max_tokens, joiner="")
            if sep not in text:
                continue
            result: list[str] = []
            buffer = ""
            for piece in text.split(sep):
                candidate = f"{buffer}{sep}{piece}" if buffer else piece
                if token_counter.count(candidate) <= self._max_tokens:
                    buffer = candidate
                    continue
                if buffer:
                    result.append(buffer)
                if token_counter.count(piece) > self._max_tokens:
                    result.extend(self._native_split(piece, token_counter, separators[i + 1 :]))
                    buffer = ""
                else:
                    buffer = piece
            if buffer:
                result.append(buffer)
            return result
        return [text]

    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        text = transcript.text
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self._max_tokens,
                chunk_overlap=0,
                length_function=token_counter.count,
                separators=list(_RECURSIVE_SEPARATORS),
            )
            pieces = [p for p in splitter.split_text(text) if p.strip()]
        except Exception:
            native = self._native_split(text, token_counter, _RECURSIVE_SEPARATORS)
            pieces = [p for p in native if p]
        return [Chunk(index=i, text=p) for i, p in enumerate(pieces)] or [Chunk(index=0, text=text)]


class SpeakerAwareChunker(Chunker):
    """Groups consecutive utterances by speaker turn, respecting a budget."""

    name = "speaker_aware"

    def __init__(self, max_tokens: int = 1200) -> None:
        self._max_tokens = max_tokens

    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        chunks: list[Chunk] = []
        buffer: list[str] = []
        idx = 0
        for utt in transcript.utterances:
            line = f"{utt.speaker.value}: {utt.text}"
            if buffer and token_counter.count("\n".join([*buffer, line])) > self._max_tokens:
                chunks.append(Chunk(index=idx, text="\n".join(buffer)))
                idx += 1
                buffer = []
            buffer.append(line)
        if buffer:
            chunks.append(Chunk(index=idx, text="\n".join(buffer)))
        return chunks or [Chunk(index=0, text=transcript.text)]


class SemanticChunker(Chunker):
    """Approximate semantic chunking by topic-keyword boundaries.

    A lightweight, dependency-free heuristic: start a new chunk when a new topic
    keyword appears and the current chunk already carries content. Stands in for
    embedding-based segmentation without requiring a model at chunk time.
    """

    name = "semantic"

    _TOPIC_MARKERS = ("claim", "eligib", "benefit", "authoriz", "billing", "provider")

    def __init__(self, max_tokens: int = 1400) -> None:
        self._max_tokens = max_tokens

    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        chunks: list[Chunk] = []
        buffer: list[str] = []
        idx = 0
        for utt in transcript.utterances:
            line = f"{utt.speaker.value}: {utt.text}"
            starts_topic = any(m in utt.text.lower() for m in self._TOPIC_MARKERS)
            over_budget = (
                bool(buffer) and token_counter.count("\n".join([*buffer, line])) > self._max_tokens
            )
            if buffer and (over_budget or starts_topic):
                chunks.append(Chunk(index=idx, text="\n".join(buffer)))
                idx += 1
                buffer = []
            buffer.append(line)
        if buffer:
            chunks.append(Chunk(index=idx, text="\n".join(buffer)))
        return chunks or [Chunk(index=0, text=transcript.text)]


class EmbeddingSemanticChunker(Chunker):
    """Semantic chunking driven by sentence-embedding similarity.

    Starts a new chunk when the cosine similarity between adjacent sentences
    drops below a threshold (a topic shift) or the token budget is exceeded.
    Requires sentence-transformers; when it is not installed this transparently
    falls back to the keyword-based :class:`SemanticChunker`.
    """

    name = "semantic_embedding"

    def __init__(self, max_tokens: int = 1400, similarity_threshold: float = 0.5) -> None:
        self._max_tokens = max_tokens
        self._threshold = similarity_threshold

    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        model = _load_embedding_model()
        sentences = _split_sentences(transcript.text)
        if model is None or len(sentences) <= 1:
            return SemanticChunker(self._max_tokens).split(transcript, token_counter)
        return self._embed_split(sentences, model, token_counter)

    def _embed_split(  # pragma: no cover - requires the optional model
        self,
        sentences: list[str],
        model: Any,
        token_counter: TokenCounter,
    ) -> list[Chunk]:
        embeddings = [list(vec) for vec in model.encode(sentences)]
        chunks: list[Chunk] = []
        buffer: list[str] = [sentences[0]]
        idx = 0
        for sentence, vec_prev, vec in zip(sentences[1:], embeddings, embeddings[1:], strict=False):
            over_budget = token_counter.count(" ".join([*buffer, sentence])) > self._max_tokens
            topic_shift = _cosine(vec_prev, vec) < self._threshold
            if over_budget or topic_shift:
                chunks.append(Chunk(index=idx, text=" ".join(buffer)))
                idx += 1
                buffer = []
            buffer.append(sentence)
        if buffer:
            chunks.append(Chunk(index=idx, text=" ".join(buffer)))
        return chunks or [Chunk(index=0, text=" ".join(sentences))]


class HierarchicalChunker(Chunker):
    """Two-level chunking: coarse fixed windows subdivided by speaker turns."""

    name = "hierarchical"

    def __init__(self, coarse_tokens: int = 2000, fine_tokens: int = 800) -> None:
        self._coarse = FixedSizeChunker(coarse_tokens)
        self._fine_tokens = fine_tokens

    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        coarse = self._coarse.split(transcript, token_counter)
        result: list[Chunk] = []
        idx = 0
        for block in coarse:
            words = block.text.split()
            window: list[str] = []
            for word in words:
                window.append(word)
                if token_counter.count(" ".join(window)) >= self._fine_tokens:
                    result.append(Chunk(index=idx, text=" ".join(window)))
                    idx += 1
                    window = []
            if window:
                result.append(Chunk(index=idx, text=" ".join(window)))
                idx += 1
        return result or [Chunk(index=0, text=transcript.text)]


class MapReduceChunker(Chunker):
    """Fixed-size map chunks plus a final reduce chunk."""

    name = "map_reduce"

    def __init__(self, max_tokens: int = 1200) -> None:
        self._mapper = FixedSizeChunker(max_tokens)

    def split(self, transcript: Transcript, token_counter: TokenCounter) -> list[Chunk]:
        map_chunks = self._mapper.split(transcript, token_counter)
        reduce_chunk = Chunk(
            index=len(map_chunks),
            text=f"Reduce {len(map_chunks)} partial analyses into a final summary.",
            is_reduce=True,
        )
        return [*map_chunks, reduce_chunk]


_CHUNKERS: dict[str, type[Chunker]] = {
    FullTranscriptChunker.name: FullTranscriptChunker,
    FixedSizeChunker.name: FixedSizeChunker,
    FixedSizeOverlapChunker.name: FixedSizeOverlapChunker,
    SentenceChunker.name: SentenceChunker,
    RecursiveChunker.name: RecursiveChunker,
    SpeakerAwareChunker.name: SpeakerAwareChunker,
    SemanticChunker.name: SemanticChunker,
    EmbeddingSemanticChunker.name: EmbeddingSemanticChunker,
    HierarchicalChunker.name: HierarchicalChunker,
    MapReduceChunker.name: MapReduceChunker,
}


def get_chunker(name: str) -> Chunker:
    """Instantiate a chunker by name."""
    if name not in _CHUNKERS:
        raise ConfigurationError(f"Unknown chunker '{name}'. Available: {sorted(_CHUNKERS)}")
    return _CHUNKERS[name]()


def available_chunkers() -> list[str]:
    return sorted(_CHUNKERS)
