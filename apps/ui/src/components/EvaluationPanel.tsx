import type { EvaluationResult } from "../types";

interface EvaluationPanelProps {
  results: EvaluationResult[];
}

const LABELS: Record<string, string> = {
  member_id_recall: "Member-ID recall",
  member_id_precision: "Member-ID precision",
  member_id_false_positive_rate: "False-positive rate",
  member_id_false_negative_rate: "False-negative rate",
  extraction_success_rate: "Extraction success rate",
  json_validity: "JSON validity",
  schema_validity: "Schema validity",
  structured_output_validity: "Structured-output validity",
  escalation_accuracy: "Escalation accuracy",
};

const label = (metric: string) => LABELS[metric] ?? metric;

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export function EvaluationPanel({ results }: EvaluationPanelProps) {
  if (results.length === 0) {
    return (
      <section>
        <h2>Evaluation &amp; quality</h2>
        <p className="empty">
          Load *.eval.json files to view extraction quality and release gates.
        </p>
      </section>
    );
  }

  return (
    <section>
      <h2>Evaluation &amp; quality</h2>
      <p className="section-intro">
        Quality measured against labeled synthetic transcripts. A release gate passes only if every
        rule passes; runs without rules are informational baselines.
      </p>
      {results.map((result) => (
        <div key={result.name} style={{ marginBottom: 24 }}>
          <h3>
            {result.name}{" "}
            <span className={`badge ${result.gate_passed ? "pass" : "fail"}`}>
              {result.gate_passed ? "GATE PASSED" : "GATE FAILED"}
            </span>
          </h3>

          <table>
            <thead>
              <tr>
                <th>Metric</th>
                <th className="num">Value</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.metrics).map(([metric, value]) => (
                <tr key={metric}>
                  <td>{label(metric)}</td>
                  <td className="num">{pct(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {result.thresholds.length > 0 && (
            <table style={{ marginTop: 12 }}>
              <thead>
                <tr>
                  <th>Release gate</th>
                  <th>Rule</th>
                  <th className="num">Actual</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {result.thresholds.map((t) => (
                  <tr key={t.metric}>
                    <td>{label(t.metric)}</td>
                    <td>
                      {t.op} {t.threshold}
                    </td>
                    <td className="num">{t.actual.toFixed(4)}</td>
                    <td>
                      <span className={`badge ${t.passed ? "pass" : "fail"}`}>
                        {t.passed ? "PASS" : "FAIL"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </section>
  );
}
