interface KeyFindingsProps {
  benchmark: string[];
  evaluation: string[];
}

/** Plain-English findings computed from whatever results are loaded (bundled or uploaded). */
export function KeyFindings({ benchmark, evaluation }: KeyFindingsProps) {
  if (benchmark.length === 0 && evaluation.length === 0) return null;
  return (
    <section className="findings">
      <h2>What the loaded results show</h2>
      <p className="section-intro">
        Computed from the loaded files. The first benchmark is the baseline; each other run is compared to it.
      </p>
      {benchmark.length > 0 && (
        <>
          <h3>Operations and cost</h3>
          <ul>
            {benchmark.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </>
      )}
      {evaluation.length > 0 && (
        <>
          <h3>Quality</h3>
          <ul>
            {evaluation.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
