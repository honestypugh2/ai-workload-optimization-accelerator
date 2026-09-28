import type { BenchmarkResult, EvaluationResult } from "./types";

/** Live runs recorded before schema v2 carry modeled TPM, 429 rate, and batch time. */
export function isLegacyLive(r: BenchmarkResult): boolean {
  return r.execution_mode === "azure" && !(r.schema_version && r.schema_version >= 2);
}

function change(from: number, to: number): string | null {
  if (!Number.isFinite(from) || !Number.isFinite(to) || from === 0) return null;
  const pct = ((to - from) / from) * 100;
  const sign = pct > 0 ? "+" : pct < 0 ? "−" : "±";
  return `${sign}${Math.abs(pct).toFixed(1)}%`;
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const money = (v: number) =>
  `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const seconds = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms.toFixed(0)} ms`);

export function benchmarkFindings(results: BenchmarkResult[], mixed: boolean): string[] {
  if (results.length === 0) return [];
  const [base, ...rest] = results;
  const out: string[] = [];

  if (rest.length === 0) {
    const m = base.metrics;
    out.push(
      `${base.name} processed ${m.transcripts.toLocaleString()} transcripts at ` +
        `${Math.round(m.average_tokens_per_transcript).toLocaleString()} tokens each, with p50 latency ` +
        `${seconds(m.p50_latency_ms)} and p95 ${seconds(m.p95_latency_ms)}; estimated cost ` +
        `${money(m.cost_per_month)}/month.`,
    );
  }

  for (const c of rest) {
    const parts = [
      ["tokens per transcript", change(base.metrics.average_tokens_per_transcript, c.metrics.average_tokens_per_transcript)],
      ["p95 latency", change(base.metrics.p95_latency_ms, c.metrics.p95_latency_ms)],
      ["estimated cost per month", change(base.metrics.cost_per_month, c.metrics.cost_per_month)],
    ]
      .filter(([, v]) => v !== null)
      .map(([label, v]) => `${label} ${v}`);
    let sentence = `${c.name} vs ${base.name}: ${parts.join(", ")}`;
    if (!isLegacyLive(base) && !isLegacyLive(c)) {
      const modeled = c.metrics.throttling_source !== "observed" ? " (modeled)" : "";
      sentence += `; HTTP 429 rate ${pct(base.metrics.http_429_rate)} → ${pct(c.metrics.http_429_rate)}${modeled}`;
    }
    out.push(`${sentence}.`);
  }

  if (rest.length >= 2) {
    const cheapest = results.reduce((a, b) => (b.metrics.cost_per_month < a.metrics.cost_per_month ? b : a));
    const fastest = results.reduce((a, b) => (b.metrics.p95_latency_ms < a.metrics.p95_latency_ms ? b : a));
    out.push(
      `Lowest estimated cost: ${cheapest.name} (${money(cheapest.metrics.cost_per_month)}/month). ` +
        `Lowest p95 latency: ${fastest.name} (${seconds(fastest.metrics.p95_latency_ms)}).`,
    );
  }

  if (mixed) {
    out.push("These runs are not like-for-like (see the warning below), so treat the differences as directional.");
  }
  if (results.some(isLegacyLive)) {
    out.push(
      "Live runs recorded before run provenance was added report modeled TPM, HTTP 429 rate, and batch time; " +
        "latency, tokens, and cost are measured. Use the observed figures where shown.",
    );
  }
  return out;
}

export function evaluationFindings(results: EvaluationResult[]): string[] {
  const out: string[] = [];
  for (const e of results) {
    const m = e.metrics;
    const bits: string[] = [];
    if ("member_id_recall" in m) bits.push(`recall ${pct(m.member_id_recall)}`);
    if ("member_id_precision" in m) bits.push(`precision ${pct(m.member_id_precision)}`);
    if ("member_id_false_positive_rate" in m) bits.push(`false-positive rate ${pct(m.member_id_false_positive_rate)}`);
    const passed = e.thresholds.filter((t) => t.passed).length;
    const failed = e.thresholds.filter((t) => !t.passed).map((t) => t.metric);
    const gate =
      e.thresholds.length === 0
        ? "no release-gate rules (informational baseline)"
        : e.gate_passed
          ? `release gate PASSED (${passed}/${e.thresholds.length} rules)`
          : `release gate FAILED on ${failed.join(", ")}`;
    out.push(`${e.name}: ${bits.length ? bits.join(", ") + " — " : ""}${gate}.`);
  }
  const withRecall = results.filter((e) => "member_id_recall" in e.metrics);
  if (withRecall.length >= 2) {
    const first = withRecall[0];
    const last = withRecall[withRecall.length - 1];
    const pts = (last.metrics.member_id_recall - first.metrics.member_id_recall) * 100;
    out.push(
      `Member-ID recall moves from ${pct(first.metrics.member_id_recall)} (${first.name}) to ` +
        `${pct(last.metrics.member_id_recall)} (${last.name}), ${pts >= 0 ? "+" : "−"}${Math.abs(pts).toFixed(1)} points.`,
    );
  }
  return out;
}
