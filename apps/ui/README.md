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

Then load result files from
`workload-scenarios/post-call-analytics/reports/` using the file pickers:

- **Benchmark results** — `*.result.json` (load two to compare baseline vs optimized)
- **Evaluation results** — `*.eval.json`

Nothing is uploaded anywhere; files are parsed in the browser.
