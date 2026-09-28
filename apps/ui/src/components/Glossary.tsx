const TERMS: [string, string][] = [
  ["Columns and Δ", "Each column is one run. The first run is the baseline; the Δ column compares the last run with it. Green means better, red means worse."],
  ["Run tags (e.g. local/local · 200 tx · 429s modeled)", "Execution mode / backend, transcript volume, and whether HTTP 429s and timing were modeled (quota simulation) or observed (live responses and wall clock). \"legacy\" = recorded before run provenance; its 429 and timing fields are modeled even for live runs."],
  ["local / mock", "Deterministic mock model provider over synthetic transcripts. No Azure calls, no credentials, reproducible."],
  ["azure / direct", "Live inference against a Microsoft Foundry model deployment."],
  ["Avg tokens / transcript", "Input + output tokens per transcript across all analysis tasks. Drives cost and quota usage."],
  ["Effective TPM", "Tokens per minute actually achieved, compared with the deployment's quota ceiling."],
  ["p50 / p95 latency", "Median and 95th-percentile time to process one transcript. p95 shows the slow tail."],
  ["Throughput / batch completion", "Transcripts per minute and the time to clear the whole batch."],
  ["HTTP 429 rate / retries", "Share of calls throttled by the quota and the retries they caused."],
  ["Cache hit rate", "Share of calls answered from the prompt/result cache."],
  ["Cost / transcript, day, month", "Estimates from the pricing file for the tokens used. \"cost extrapolated\" = scaled from the sample to the full daily volume."],
  ["Recall / precision", "Recall: share of transcripts with a member ID where it was found. Precision: share of extracted IDs that were correct."],
  ["False-positive / false-negative rate", "Wrong IDs returned, and IDs present but missed."],
  ["Release gate", "Threshold rules (e.g. recall ≥ 0.90). The gate passes only if every rule passes; a failing gate exits with code 2 in the CLI."],
  ["Mixed comparison", "Runs that differ in mode, backend, 429 source, or volume by more than 2×. Differences are directional, not like-for-like."],
];

export function Glossary() {
  return (
    <details className="glossary">
      <summary>How to read these results</summary>
      <dl>
        {TERMS.map(([term, definition]) => (
          <div key={term}>
            <dt>{term}</dt>
            <dd>{definition}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
