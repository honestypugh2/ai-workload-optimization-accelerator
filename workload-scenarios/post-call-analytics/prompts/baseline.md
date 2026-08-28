# Baseline prompt (reference current-state)

The literal template sent to the model is the fenced block below (`{transcript}`
is replaced at runtime). It is loaded verbatim by the benchmark runner.

```text
You are analyzing a healthcare payer member-services call transcript.

Read the entire transcript below and return a JSON object with:
- `member_id`: the member identification number, or null if not present
- `sentiment`: one of positive, neutral, negative
- `escalation`: true if the caller requested a supervisor or escalation
- `summary`: a 2-3 sentence summary of the call
- `evidence`: short quotes supporting the sentiment and escalation determinations

Transcript:

{transcript}
```
