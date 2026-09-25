import type { BenchmarkResult } from "../types";

interface BenchmarkComparisonProps {
  results: BenchmarkResult[];
}

interface Row {
  key: string;
  label: string;
  format: (v: number) => string;
  lowerIsBetter: boolean;
}

const ROWS: Row[] = [
  { key: "average_tokens_per_transcript", label: "Avg tokens / transcript", format: int, lowerIsBetter: true },
  { key: "effective_tokens_per_minute", label: "Effective TPM", format: int, lowerIsBetter: false },
  { key: "p50_latency_ms", label: "p50 latency (ms)", format: ms, lowerIsBetter: true },
  { key: "p95_latency_ms", label: "p95 latency (ms)", format: ms, lowerIsBetter: true },
  { key: "cost_per_month", label: "Cost / month", format: money, lowerIsBetter: true },
  { key: "http_429_rate", label: "HTTP 429 rate", format: pct, lowerIsBetter: true },
  { key: "cache_hit_rate", label: "Cache hit rate", format: pct, lowerIsBetter: false },
];

function int(v: number): string {
  return Math.round(v).toLocaleString();
}
function ms(v: number): string {
  return v.toFixed(1);
}
function money(v: number): string {
  return `$${v.toFixed(2)}`;
}
function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function metricValue(r: BenchmarkResult, key: string): number {
  return (r.metrics as unknown as Record<string, number>)[key] ?? Number.NaN;
}

// Mirrors reporting/comparability.py so the viewer warns about the same
// like-for-unlike comparisons the CLI refuses.
const MAX_VOLUME_RATIO = 2;

function throttlingSource(r: BenchmarkResult): string {
  return r.metrics.throttling_source ?? "modeled";
}

function mixedReasons(results: BenchmarkResult[]): string[] {
  const [base, ...rest] = results;
  const reasons: string[] = [];
  for (const r of rest) {
    if (r.execution_mode !== base.execution_mode) {
      reasons.push(`${r.name}: mode ${r.execution_mode} vs baseline ${base.execution_mode}`);
    }
    if ((r.execution_backend ?? "unknown") !== (base.execution_backend ?? "unknown")) {
      reasons.push(`${r.name}: backend ${r.execution_backend} vs ${base.execution_backend}`);
    }
    if (throttlingSource(r) !== throttlingSource(base)) {
      reasons.push(`${r.name}: 429s ${throttlingSource(r)} vs ${throttlingSource(base)}`);
    }
    const a = base.metrics.transcripts;
    const b = r.metrics.transcripts;
    if (a > 0 && b > 0 && Math.max(a, b) / Math.min(a, b) > MAX_VOLUME_RATIO) {
      reasons.push(`${r.name}: ${b.toLocaleString()} transcripts vs ${a.toLocaleString()}`);
    }
  }
  return reasons;
}

function provenanceLine(r: BenchmarkResult): string {
  const backend = r.execution_backend ?? "?";
  const volume = r.metrics.transcripts.toLocaleString();
  const source = r.schema_version && r.schema_version >= 2 ? throttlingSource(r) : "legacy";
  const extrapolated = r.metrics.cost_extrapolated ? " · cost extrapolated" : "";
  return `${r.execution_mode}/${backend} · ${volume} tx · 429s ${source}${extrapolated}`;
}

export function BenchmarkComparison({ results }: BenchmarkComparisonProps) {
  if (results.length === 0) {
    return (
      <section>
        <h2>Benchmark comparison</h2>
        <p className="empty">Load one or more *.result.json files to compare architectures.</p>
      </section>
    );
  }

  const baseline = results[0];
  const showDelta = results.length >= 2;
  const reasons = mixedReasons(results);

  return (
    <section>
      <h2>Benchmark comparison</h2>
      {reasons.length > 0 && (
        <div className="warning">
          <strong>Mixed comparison — these runs are not like-for-like.</strong>
          <ul>
            {reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            {results.map((r, i) => (
              <th className="num" key={`${r.name}-${i}`}>
                {r.name}
                <div className="subtitle">
                  {r.strategy} / {r.routing}
                </div>
                <div className="subtitle">{provenanceLine(r)}</div>
              </th>
            ))}
            {showDelta && <th className="num">Δ vs first</th>}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => {
            const baseVal = metricValue(baseline, row.key);
            const lastVal = metricValue(results[results.length - 1], row.key);
            const delta = lastVal - baseVal;
            const improved = row.lowerIsBetter ? delta < 0 : delta > 0;
            return (
              <tr key={row.key}>
                <td>{row.label}</td>
                {results.map((r, i) => (
                  <td className="num" key={`${r.name}-${i}`}>
                    {row.format(metricValue(r, row.key))}
                  </td>
                ))}
                {showDelta && (
                  <td className={`num ${improved ? "delta-good" : "delta-bad"}`}>
                    {row.format(delta)}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
