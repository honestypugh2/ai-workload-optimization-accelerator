import type { SampleSet } from "./SourcePicker";

function duration(seconds: number): string {
  if (seconds >= 3600) return `${(seconds / 3600).toFixed(2)} h`;
  if (seconds >= 60) return `${(seconds / 60).toFixed(1)} min`;
  return `${seconds.toFixed(0)} s`;
}

/** Author-written context for a bundled result set: takeaways, caveats, and observed live figures. */
export function AboutPanel({ set }: { set: SampleSet }) {
  const hasContent = set.takeaways?.length || set.caveats?.length || set.observed;
  if (!hasContent) return null;

  return (
    <section className="about">
      <h2>About these results</h2>
      {set.takeaways && set.takeaways.length > 0 && (
        <>
          <h3>Key takeaways</h3>
          <ul>
            {set.takeaways.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </>
      )}
      {set.observed && (
        <>
          <h3>Observed on live Azure</h3>
          <p className="section-intro">{set.observed.note}</p>
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th className="num">Transcripts</th>
                <th className="num">Workers</th>
                <th className="num">Wall clock</th>
                <th className="num">Requests</th>
                <th className="num">HTTP 200</th>
                <th className="num">HTTP 429</th>
                <th>Other</th>
                <th className="num">Observed TPM</th>
                <th className="num">Transcripts/min</th>
              </tr>
            </thead>
            <tbody>
              {set.observed.rows.map((r) => (
                <tr key={r.run}>
                  <td>{r.run}</td>
                  <td className="num">{r.transcripts.toLocaleString()}</td>
                  <td className="num">{r.workers}</td>
                  <td className="num">{duration(r.wall_clock_seconds)}</td>
                  <td className="num">{r.requests.toLocaleString()}</td>
                  <td className="num">{r.http_200.toLocaleString()}</td>
                  <td className="num">{r.http_429.toLocaleString()}</td>
                  <td>{r.other_errors}</td>
                  <td className="num">{Math.round(r.observed_tokens_per_minute).toLocaleString()}</td>
                  <td className="num">{r.transcripts_per_minute.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {set.caveats && set.caveats.length > 0 && (
        <div className="caveat">
          <strong>Caveats</strong>
          <ul>
            {set.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
