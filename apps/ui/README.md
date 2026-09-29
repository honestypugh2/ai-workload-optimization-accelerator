# Accelerator Result Viewer (thin, optional)

A minimal React + TypeScript + Vite app for **viewing** benchmark and evaluation
result JSON produced by the Python harness. It is intentionally thin: it performs
no computation and requires no backend. The CLI and local test path are the
source of truth; this viewer only renders their output.

## Usage

```bash
cd apps/ui
npm install
npm run dev
```

The viewer opens with results already loaded. Use the **Results** dropdown to
switch between the bundled result sets or choose **Upload your own files…**:

| Result set | What it shows |
|---|---|
| Reference demo (synthetic, 200 transcripts) | Each optimization lever plus the stacked optimized target, member-ID quality (naive 30.8% → deterministic 93.5% recall), and the combined scorecard. Matches release `v0.1.0`. |
| Architecture options (modeled, 7,000/day) | Current state vs Options A/B/C and a single high-quota deployment. Operations and cost only. |
| Live Azure (sandbox) — current state vs Option B, 7,000 each | Live gpt-5.4-nano runs, back to back: batch 1.50 h → 39 min, p95 −57%, tokens −51%, 0 HTTP 429s in 65,253 calls. |
| Live Azure (sandbox) — earlier 7,000 baseline (August, legacy) | Earlier live baseline: 2.5 h, 0 HTTP 429s at ~24% of quota. Observed figures from run logs. |

Every view explains itself:

- **About these results** — takeaways, caveats, and (for live sets) an
  **Observed on live Azure** table derived from the run logs.
- **What the loaded results show** — plain-English findings computed from
  whatever is loaded, including your own uploads.
- **How to read these results** — a glossary of every metric and run tag.
- Live runs recorded before run provenance mark their modeled TPM and HTTP 429
  values with `*`. Bundled live results have the endpoint hostname redacted.

To view your own runs, use the file pickers with files from
`workload-scenarios/post-call-analytics/reports/`:

- **Benchmark results** — `*.result.json` (load two or more to compare)
- **Evaluation results** — `*.eval.json`
- **Combined scorecard** — `scorecard.json`

Uploading replaces the bundled set; further uploads are added alongside. Files
are parsed in the browser — nothing is uploaded to a server.

## Bundled samples

The result sets live in `public/samples/` (listed in `public/samples/index.json`,
which also holds each set's labels, takeaways, caveats, and observed figures).
The reference and architecture sets are **synthetic** (mock provider, synthetic
labeled transcripts). The live sets are past runs against the author's sandbox
Azure deployment using synthetic transcripts; they contain no endpoints,
credentials, or customer data, and their run logs are not bundled. Regenerate the
synthetic sets from a clean checkout with:

```bash
scripts/refresh-ui-samples.sh
```

To add a set, write its files to `public/samples/<id>/` and add an entry to
`index.json`. The first entry is shown on start.
