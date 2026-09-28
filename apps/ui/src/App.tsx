import { useEffect, useRef, useState } from "react";
import { FileLoader } from "./components/FileLoader";
import { BenchmarkComparison } from "./components/BenchmarkComparison";
import { EvaluationPanel } from "./components/EvaluationPanel";
import { ScorecardPanel } from "./components/ScorecardPanel";
import { AboutPanel } from "./components/AboutPanel";
import { KeyFindings } from "./components/KeyFindings";
import { Glossary } from "./components/Glossary";
import { mixedReasons } from "./components/BenchmarkComparison";
import { benchmarkFindings, evaluationFindings } from "./insights";
import { SourcePicker, UPLOAD_SOURCE, type SampleSet } from "./components/SourcePicker";
import {
  isBenchmarkResult,
  isEvaluationResult,
  isScorecard,
  type BenchmarkResult,
  type EvaluationResult,
  type Scorecard,
} from "./types";

// Resolved against the page URL so the viewer works under any base path.
const SAMPLES_ROOT = "samples/";

type LoadedFile = { name: string; data: unknown };

async function fetchJson(path: string): Promise<unknown> {
  const response = await fetch(`${SAMPLES_ROOT}${path}`);
  if (!response.ok) {
    throw new Error(`${path}: HTTP ${response.status}`);
  }
  return response.json();
}

function isSampleIndex(value: unknown): value is { sets: SampleSet[] } {
  return (
    typeof value === "object" &&
    value !== null &&
    Array.isArray((value as { sets?: unknown }).sets)
  );
}

export function App() {
  const [sets, setSets] = useState<SampleSet[]>([]);
  const [selected, setSelected] = useState<string>(UPLOAD_SOURCE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadedFiles, setLoadedFiles] = useState<string[]>([]);
  const [benchmarks, setBenchmarks] = useState<BenchmarkResult[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationResult[]>([]);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  // Ignores responses from superseded selections (fast switching, StrictMode re-runs).
  const requestId = useRef(0);

  function clearResults() {
    setBenchmarks([]);
    setEvaluations([]);
    setScorecard(null);
    setLoadedFiles([]);
  }

  async function loadSet(set: SampleSet) {
    const id = ++requestId.current;
    setSelected(set.id);
    setLoading(true);
    setError(null);
    try {
      const base = `${set.id}/`;
      const [bench, evals, card] = await Promise.all([
        Promise.all(set.benchmarks.map((f) => fetchJson(base + f))),
        Promise.all(set.evaluations.map((f) => fetchJson(base + f))),
        set.scorecard ? fetchJson(base + set.scorecard) : Promise.resolve(null),
      ]);
      if (id !== requestId.current) return;
      setBenchmarks(
        bench
          .map((data, i) => {
            const label = set.labels?.[set.benchmarks[i]];
            return label && isBenchmarkResult(data) ? { ...data, name: label } : data;
          })
          .filter(isBenchmarkResult),
      );
      setEvaluations(evals.filter(isEvaluationResult));
      setScorecard(isScorecard(card) ? card : null);
      setLoadedFiles([
        ...set.benchmarks,
        ...set.evaluations,
        ...(set.scorecard ? [set.scorecard] : []),
      ]);
    } catch (err) {
      if (id !== requestId.current) return;
      clearResults();
      setError(`Could not load "${set.label}": ${(err as Error).message}`);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }

  function selectSource(id: string) {
    const set = sets.find((s) => s.id === id);
    if (set) {
      void loadSet(set);
      return;
    }
    requestId.current++;
    setSelected(UPLOAD_SOURCE);
    setLoading(false);
    setError(null);
    clearResults();
  }

  useEffect(() => {
    const id = ++requestId.current;
    fetchJson("index.json")
      .then((index) => {
        if (id !== requestId.current) return;
        const available = isSampleIndex(index) ? index.sets : [];
        setSets(available);
        if (available.length > 0) {
          void loadSet(available[0]);
        } else {
          setLoading(false);
        }
      })
      .catch(() => {
        if (id !== requestId.current) return;
        setLoading(false);
        setError("No bundled result sets found — upload result files below.");
      });
  }, []);

  /** Uploading replaces a bundled set rather than mixing with it; later uploads append. */
  function recordUpload(files: LoadedFile[], accepted: unknown[]) {
    if (selected !== UPLOAD_SOURCE) {
      selectSource(UPLOAD_SOURCE);
    }
    const kept = files.filter((f) => accepted.includes(f.data)).map((f) => f.name);
    const skipped = files.filter((f) => !accepted.includes(f.data)).map((f) => f.name);
    setLoadedFiles((prev) => [...(selected === UPLOAD_SOURCE ? prev : []), ...kept]);
    setError(skipped.length ? `Skipped (not a recognized result): ${skipped.join(", ")}` : null);
  }

  function loadBenchmarks(files: LoadedFile[]) {
    const valid = files.map((f) => f.data).filter(isBenchmarkResult);
    recordUpload(files, valid);
    setBenchmarks((prev) => [...prev, ...valid]);
  }

  function loadEvaluations(files: LoadedFile[]) {
    const valid = files.map((f) => f.data).filter(isEvaluationResult);
    recordUpload(files, valid);
    setEvaluations((prev) => [...prev, ...valid]);
  }

  function loadScorecard(files: LoadedFile[]) {
    const match = files.map((f) => f.data).find(isScorecard);
    recordUpload(files, match ? [match] : []);
    if (match) setScorecard(match);
  }

  const activeSet = sets.find((s) => s.id === selected);
  const benchFindings = benchmarkFindings(benchmarks, mixedReasons(benchmarks).length > 0);
  const evalFindings = evaluationFindings(evaluations);

  return (
    <div className="app">
      <h1>AI Workload Optimization Accelerator</h1>
      <p className="subtitle">
        Thin local viewer for benchmark and evaluation results. Runs entirely in
        your browser — nothing is uploaded.
      </p>

      <SourcePicker
        sets={sets}
        selected={selected}
        loading={loading}
        error={error}
        loadedFiles={loadedFiles}
        onSelect={selectSource}
      />

      <div className="loaders">
        <FileLoader
          label="Benchmark results (*.result.json)"
          accept="application/json,.json"
          multiple
          onLoad={loadBenchmarks}
        />
        <FileLoader
          label="Evaluation results (*.eval.json)"
          accept="application/json,.json"
          multiple
          onLoad={loadEvaluations}
        />
        <FileLoader
          label="Combined scorecard (scorecard.json)"
          accept="application/json,.json"
          onLoad={loadScorecard}
        />
      </div>

      {activeSet && !loading && <AboutPanel set={activeSet} />}
      <KeyFindings benchmark={benchFindings} evaluation={evalFindings} />
      <Glossary />

      <ScorecardPanel scorecard={scorecard} />
      <BenchmarkComparison results={benchmarks} />
      <EvaluationPanel results={evaluations} />
    </div>
  );
}
