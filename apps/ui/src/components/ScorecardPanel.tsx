import { Fragment } from "react";
import type { Scorecard, ScorecardRow } from "../types";

interface ScorecardPanelProps {
  scorecard: Scorecard | null;
}

const CATEGORIES: ScorecardRow["category"][] = ["Operations", "Cost", "Quality"];

function formatValue(value: number | null, unit: string): string {
  if (value === null) return "—";
  switch (unit) {
    case "$":
      return Math.abs(value) < 1 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`;
    case "rate":
      return `${(value * 100).toFixed(1)}%`;
    case "ms":
    case "s":
    case "tok":
    case "tok/min":
    case "tx/min":
      return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
    default:
      return Number.isInteger(value)
        ? value.toLocaleString()
        : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
}

export function ScorecardPanel({ scorecard }: ScorecardPanelProps) {
  if (!scorecard) {
    return (
      <section>
        <h2>Combined scorecard</h2>
        <p className="empty">
          Load a scorecard.json (produced by <code>aiwoa report scorecard</code>) to
          compare operations, cost, and quality side by side.
        </p>
      </section>
    );
  }

  const { runs, rows } = scorecard;
  const showDelta = runs.length >= 2;

  return (
    <section>
      <h2>Combined ops + cost + quality scorecard</h2>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            {runs.map((run) => (
              <th className="num" key={run}>
                {run}
              </th>
            ))}
            {showDelta && <th className="num">Δ vs baseline</th>}
          </tr>
        </thead>
        <tbody>
          {CATEGORIES.map((category) => {
            const catRows = rows.filter((r) => r.category === category);
            if (catRows.length === 0) return null;
            return (
              <Fragment key={category}>
                <tr className="category-row">
                  <td colSpan={runs.length + (showDelta ? 2 : 1)}>
                    <strong>{category}</strong>
                  </td>
                </tr>
                {catRows.map((row) => (
                  <tr key={row.metric}>
                    <td>{row.label}</td>
                    {row.values.map((v, i) => (
                      <td className="num" key={`${row.metric}-${i}`}>
                        {formatValue(v, row.unit)}
                      </td>
                    ))}
                    {showDelta && (
                      <td
                        className={`num ${
                          row.improved === null
                            ? ""
                            : row.improved
                              ? "delta-good"
                              : "delta-bad"
                        }`}
                      >
                        {row.delta === null ? "" : formatValue(row.delta, row.unit)}
                      </td>
                    )}
                  </tr>
                ))}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
