import { useState } from "react";
import { FileLoader } from "./components/FileLoader";
import { BenchmarkComparison } from "./components/BenchmarkComparison";
import { EvaluationPanel } from "./components/EvaluationPanel";
import { ScorecardPanel } from "./components/ScorecardPanel";
import {
  isBenchmarkResult,
  isEvaluationResult,
  isScorecard,
  type BenchmarkResult,
  type EvaluationResult,
  type Scorecard,
} from "./types";

export function App() {
  const [benchmarks, setBenchmarks] = useState<BenchmarkResult[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationResult[]>([]);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);

  function loadBenchmarks(files: { name: string; data: unknown }[]) {
    const valid = files
      .map((f) => f.data)
      .filter(isBenchmarkResult);
    setBenchmarks((prev) => [...prev, ...valid]);
  }

  function loadEvaluations(files: { name: string; data: unknown }[]) {
    const valid = files
      .map((f) => f.data)
      .filter(isEvaluationResult);
    setEvaluations((prev) => [...prev, ...valid]);
  }

  function loadScorecard(files: { name: string; data: unknown }[]) {
    const match = files.map((f) => f.data).find(isScorecard);
    if (match) setScorecard(match);
  }

  return (
    <div className="app">
      <h1>AI Workload Optimization Accelerator</h1>
      <p className="subtitle">
        Thin local viewer for benchmark and evaluation results. Runs entirely in
        your browser — nothing is uploaded.
      </p>

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

      <ScorecardPanel scorecard={scorecard} />
      <BenchmarkComparison results={benchmarks} />
      <EvaluationPanel results={evaluations} />
    </div>
  );
}
