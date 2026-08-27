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

  return (
    <section>
      <h2>Benchmark comparison</h2>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            {results.map((r) => (
              <th className="num" key={r.name}>
                {r.name}
                <div className="subtitle">
                  {r.strategy} / {r.routing}
                </div>
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
                {results.map((r) => (
                  <td className="num" key={r.name}>
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
