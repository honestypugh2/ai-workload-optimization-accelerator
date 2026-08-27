# Sample data

**All data in this directory is 100% synthetic.** No real member names, member
IDs, employer data, claims, provider identifiers, call recordings, or PHI/PII are
present. Member identifiers (e.g. `MBR482910337`) are randomly generated fakes.

These hand-authored samples illustrate the transcript shape. The full benchmark
and evaluation datasets are generated on the fly by
`workloads.post_call_analytics.infrastructure.SyntheticTranscriptGenerator`,
which reproduces the statistical profile documented in
[dataset-profile.yaml](dataset-profile.yaml).

## Files

| File | Illustrates |
| --- | --- |
| `transcript-001.json` | Clean, contiguous member id (recoverable by naive regex) |
| `transcript-002.json` | Spoken-digit id, escalation, ASR noise |
| `transcript-long-001.json` | Long-tail, fragmented id split across turns |

## Member-id presentation mix

Among transcripts that contain an id, the generator uses this presentation mix so
that a naive baseline regex recovers ~30% while the optimized deterministic
extractor recovers ~90%:

- `clean` 30% — contiguous, correctly formatted
- `dashed` 25% — separated by dashes/spaces
- `spoken` 25% — read out as digit words
- `fragmented` 20% — split across turns with ASR-style errors
