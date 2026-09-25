// Types mirroring the JSON emitted by the Python harness. Kept intentionally
// permissive: the viewer only reads a known subset and passes the rest through.

export interface BenchmarkMetrics {
  transcripts: number;
  transcripts_per_minute: number;
  effective_tokens_per_minute: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  total_input_tokens: number;
  total_output_tokens: number;
  average_tokens_per_transcript: number;
  estimated_cost: number;
  cost_per_transcript: number;
  cost_per_1k_transcripts: number;
  cost_per_day: number;
  cost_per_month: number;
  http_429_rate: number;
  retry_count: number;
  error_count: number;
  cache_hit_rate: number;
  deployment_utilization: Record<string, number>;
  workload_queue_depth: number;
  batch_completion_seconds: number;
  // schema_version >= 2. "modeled" = quota simulation; "observed" = live 429s / wall clock.
  throttling_source?: "modeled" | "observed";
  timing_source?: "modeled" | "observed";
  observed_http_429_count?: number | null;
  observed_wall_clock_seconds?: number | null;
  daily_volume?: number | null;
  cost_extrapolated?: boolean;
  cost_extrapolation_factor?: number;
}

export interface RunProvenance {
  generated_at: string;
  git_commit?: string | null;
  config_path?: string | null;
  config_sha256: string;
  config_overrides?: Record<string, unknown>;
  config_execution_mode?: string | null;
  model_deployments?: Record<string, string>;
  endpoint_host?: string | null;
}

export interface BenchmarkResult {
  schema_version?: number;
  name: string;
  scenario: string;
  strategy: string;
  routing: string;
  execution_mode: string;
  execution_backend?: string;
  use_optimized_mapping: boolean;
  currency: string;
  metrics: BenchmarkMetrics;
  provenance?: RunProvenance | null;
  notes?: string[];
}

export interface ThresholdOutcome {
  metric: string;
  op: string;
  threshold: number;
  actual: number;
  passed: boolean;
}

export interface EvaluationResult {
  name: string;
  scenario: string;
  metrics: Record<string, number>;
  thresholds: ThresholdOutcome[];
  gate_passed: boolean;
}

export function isEvaluationResult(
  value: unknown,
): value is EvaluationResult {
  return (
    typeof value === "object" &&
    value !== null &&
    "gate_passed" in value &&
    "thresholds" in value
  );
}

export function isBenchmarkResult(value: unknown): value is BenchmarkResult {
  return (
    typeof value === "object" &&
    value !== null &&
    "metrics" in value &&
    "strategy" in value
  );
}

export interface ScorecardRow {
  metric: string;
  label: string;
  category: "Operations" | "Cost" | "Quality";
  unit: string;
  higher_is_better: boolean;
  values: (number | null)[];
  delta: number | null;
  improved: boolean | null;
}

export interface ScorecardRunMeta {
  execution_mode: string | null;
  execution_backend: string | null;
  transcripts: number | null;
  schema_version: number;
  throttling_source: string | null;
  cost_extrapolated: boolean | null;
  model_deployments: Record<string, string>;
}

export interface ComparabilityIssue {
  label: string;
  check: string;
  message: string;
  blocking: boolean;
}

export interface Scorecard {
  runs: string[];
  rows: ScorecardRow[];
  mixed?: boolean;
  provenance?: (ScorecardRunMeta | null)[];
  comparability_issues?: ComparabilityIssue[];
}

export function isScorecard(value: unknown): value is Scorecard {
  return (
    typeof value === "object" &&
    value !== null &&
    "runs" in value &&
    "rows" in value &&
    Array.isArray((value as Scorecard).rows)
  );
}

