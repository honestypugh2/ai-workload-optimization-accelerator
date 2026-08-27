import type { EvaluationResult } from "../types";

interface EvaluationPanelProps {
  results: EvaluationResult[];
}

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
                  <td>{metric}</td>
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
                    <td>{t.metric}</td>
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
