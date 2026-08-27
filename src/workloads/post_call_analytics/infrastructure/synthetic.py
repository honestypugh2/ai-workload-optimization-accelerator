"""Synthetic post-call analytics transcript generator.

Produces entirely fake healthcare payer / member-services call transcripts that
preserve the *statistical and operational* shape of a call center analytics workload:
volume, token distribution, member-id presence and presentation mix, escalation
and noise rates. No real names, ids, claims, or PHI are generated.

The member-id *presentation* mix is deliberately tuned so that a naive baseline
regex recovers ~30% of present ids while the optimized deterministic extractor
recovers ~90%.
"""

from __future__ import annotations

import random

from foundry.model_catalog import ApproxTokenCounter
from shared.configuration import DatasetProfile
from shared.types import Speaker, Transcript, Utterance
from workloads.post_call_analytics.domain.member_id import (
    IdPresentation,
    MemberIdFormat,
    render_clean,
    render_dashed,
    render_fragmented,
    render_spoken,
)

_GREETINGS = (
    "Thank you for calling member services, this call may be recorded for quality "
    "and training purposes. My name is Jordan, how can I help you today?",
    "Member services, your call is important to us. Please listen carefully as our "
    "menu options have recently changed. How can I assist?",
)

_CATEGORY_LINES: dict[str, tuple[str, ...]] = {
    "eligibility": (
        "I'm calling to check if my plan is still active for this month.",
        "Can you confirm whether my dependents are covered under the same policy?",
        "Let me pull up your eligibility. It shows active coverage effective this year.",
    ),
    "claims": (
        "I have a question about a claim that was denied last week.",
        "The claim shows as processed but I was still billed the full amount.",
        "I see the claim here; it was applied to your deductible, let me explain.",
    ),
    "benefits": (
        "What are my benefits for physical therapy visits this year?",
        "Is there a copay for a specialist visit under my current plan?",
        "Your plan covers twenty visits per year with a small copay each visit.",
    ),
    "prior_auth": (
        "My provider said I need prior authorization for an upcoming procedure.",
        "Has the prior authorization request been approved yet?",
        "I show the authorization is pending review by our clinical team.",
    ),
    "verification": (
        "Before we continue I need to verify your identity on the account.",
        "Can you provide your member identification number please?",
        "Thank you, let me confirm that number against our records.",
    ),
    "billing": (
        "I think I was double billed for last month's premium.",
        "My autopay didn't go through and now I have a past due notice.",
        "I can see the billing history and will submit an adjustment request.",
    ),
    "provider": (
        "Is Dr. Rivera still in network for my plan this year?",
        "I need to find an in-network lab near my zip code.",
        "That provider is in network; I can send you a few nearby options.",
    ),
    "transfer": (
        "I'm going to transfer you to our claims specialty team, please hold.",
        "Let me get a supervisor on the line to review this with you.",
    ),
}

_NOISE_LINES = (
    "[inaudible] sorry could you repeat that the connection cut out",
    "uh um yeah so like I was saying you know it's been a while",
    "[background noise] one moment please my system is loading",
    "hold on my headset is uh cutting in and out can you hear me now",
)

_ESCALATION_LINES = (
    "This is the third time I've called and I want to speak to a supervisor now.",
    "I am very frustrated, this needs to be escalated immediately.",
    "I understand your frustration, I'm escalating this to our resolution team.",
)

_FILLER_LINES = (
    "Okay, and just to make sure I have everything documented correctly on my end.",
    "Alright, give me just a moment while I make a note of that in the account.",
    "Thanks for your patience, the system can be a little slow this time of day.",
    "Let me read that back to you to confirm we have the correct information.",
)

_PRESENTATION_WEIGHTS: dict[IdPresentation, float] = {
    IdPresentation.CLEAN: 0.30,
    IdPresentation.DASHED: 0.25,
    IdPresentation.SPOKEN: 0.25,
    IdPresentation.FRAGMENTED: 0.20,
}

# Approximate word counts per size bucket, chosen so the average lands near the
# reference's ~5,000 token profile (~1.33 tokens/word).
_SIZE_WORD_TARGETS = {"small": 900, "average": 3800, "long": 9000}


class SyntheticTranscriptGenerator:
    """Generates faithful synthetic transcripts for the post-call workload."""

    def __init__(
        self,
        profile: DatasetProfile,
        *,
        id_format: MemberIdFormat | None = None,
    ) -> None:
        self._profile = profile
        self._id_format = id_format or MemberIdFormat()
        self._counter = ApproxTokenCounter()

    def generate(self, count: int, *, seed: int = 1234, labeled: bool = True) -> list[Transcript]:
        rng = random.Random(seed)
        return [self._one(rng, i, labeled) for i in range(count)]

    def _pick_size(self, rng: random.Random) -> str:
        dist = self._profile.size_distribution
        r = rng.random()
        cumulative = 0.0
        for bucket, weight in dist.items():
            cumulative += weight
            if r <= cumulative:
                return bucket
        return "average"

    def _pick_presentation(self, rng: random.Random) -> IdPresentation:
        r = rng.random()
        cumulative = 0.0
        for pres, weight in _PRESENTATION_WEIGHTS.items():
            cumulative += weight
            if r <= cumulative:
                return pres
        return IdPresentation.CLEAN

    def _one(self, rng: random.Random, index: int, labeled: bool) -> Transcript:
        size = self._pick_size(rng)
        target_words = _SIZE_WORD_TARGETS[size]
        category = rng.choice([c for c in _CATEGORY_LINES if c not in ("verification", "transfer")])
        has_id = rng.random() < self._profile.member_id_presence_rate
        escalated = rng.random() < self._profile.escalation_rate
        noisy = rng.random() < self._profile.noisy_transcript_rate

        utterances: list[Utterance] = []
        clock = 0.0

        def add(speaker: Speaker, text: str) -> None:
            nonlocal clock
            utterances.append(Utterance(speaker=speaker, text=text, start_seconds=clock))
            clock += 6.0

        add(Speaker.AGENT, rng.choice(_GREETINGS))
        add(Speaker.MEMBER, "Hi, yes, I have a couple of questions about my account.")

        member_id: str | None = None
        presentation = IdPresentation.MISSING
        if has_id:
            member_id = self._id_format.generate(rng)
            presentation = self._pick_presentation(rng)
            self._render_id(rng, add, member_id, presentation)

        # Verification exchange.
        add(Speaker.AGENT, rng.choice(_CATEGORY_LINES["verification"]))

        # Category-specific content.
        for line in _CATEGORY_LINES[category]:
            speaker = (
                Speaker.MEMBER if "?" in line and "your" not in line.lower() else Speaker.AGENT
            )
            add(speaker, line)

        if escalated:
            for line in _ESCALATION_LINES:
                add(Speaker.MEMBER if "I " in line else Speaker.AGENT, line)
            add(Speaker.AGENT, rng.choice(_CATEGORY_LINES["transfer"]))

        # Pad with filler / noise to reach the target size while preserving shape.
        self._pad(rng, add, target_words, noisy)

        add(Speaker.AGENT, "Is there anything else I can help you with today?")
        add(Speaker.MEMBER, "No, that's everything, thank you for your help.")

        metadata = {
            "category": category,
            "size_bucket": size,
            "id_presentation": presentation.value,
            "has_id": str(has_id),
            "escalated": str(escalated),
            "noisy": str(noisy),
        }
        return Transcript(
            transcript_id=f"pca-{index:06d}",
            utterances=tuple(utterances),
            member_id_gold=member_id if labeled else None,
            metadata=metadata,
        )

    def _render_id(self, rng, add, member_id: str, presentation: IdPresentation) -> None:
        add(Speaker.AGENT, "Can you read me your member identification number please?")
        if presentation is IdPresentation.CLEAN:
            add(Speaker.MEMBER, f"Sure, it's {render_clean(member_id)}.")
        elif presentation is IdPresentation.DASHED:
            add(Speaker.MEMBER, f"It's {render_dashed(member_id, rng)}.")
        elif presentation is IdPresentation.SPOKEN:
            add(Speaker.MEMBER, f"Okay, it's {render_spoken(member_id)}.")
        elif presentation is IdPresentation.FRAGMENTED:
            first, second = render_fragmented(member_id, rng)
            add(Speaker.MEMBER, f"Let me find it, um, {first}")
            add(Speaker.AGENT, "Okay, and the rest of the number?")
            add(Speaker.MEMBER, f"{second}, sorry the signal is bad.")

    def _pad(self, rng, add, target_words: int, noisy: bool) -> None:
        # Approximate remaining budget after ~120 words of structured content.
        words_needed = target_words - 120
        while words_needed > 0:
            if noisy and rng.random() < 0.35:
                line = rng.choice(_NOISE_LINES)
                speaker = Speaker.MEMBER
            else:
                line = rng.choice(_FILLER_LINES)
                speaker = rng.choice([Speaker.AGENT, Speaker.MEMBER])
            add(speaker, line)
            words_needed -= len(line.split())
