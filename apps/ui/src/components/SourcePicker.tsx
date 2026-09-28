export interface ObservedRow {
  run: string;
  transcripts: number;
  workers: number;
  wall_clock_seconds: number;
  requests: number;
  http_200: number;
  http_429: number;
  other_errors: string;
  observed_tokens_per_minute: number;
  transcripts_per_minute: number;
}

export interface SampleSet {
  id: string;
  label: string;
  description?: string;
  benchmarks: string[];
  evaluations: string[];
  scorecard?: string | null;
  /** Optional display names for benchmark files, e.g. to label live runs. */
  labels?: Record<string, string>;
  takeaways?: string[];
  caveats?: string[];
  observed?: { note: string; rows: ObservedRow[] };
}

export const UPLOAD_SOURCE = "__upload__";

interface SourcePickerProps {
  sets: SampleSet[];
  selected: string;
  loading: boolean;
  error: string | null;
  loadedFiles: string[];
  onSelect: (id: string) => void;
}

/** Dropdown for choosing a bundled result set or switching to uploaded files. */
export function SourcePicker({
  sets,
  selected,
  loading,
  error,
  loadedFiles,
  onSelect,
}: SourcePickerProps) {
  const current = sets.find((s) => s.id === selected);

  return (
    <div className="source-picker">
      <label htmlFor="result-source">Results</label>
      <select
        id="result-source"
        value={selected}
        disabled={loading}
        onChange={(event) => onSelect(event.target.value)}
      >
        {sets.map((set) => (
          <option key={set.id} value={set.id}>
            {set.label}
          </option>
        ))}
        <option value={UPLOAD_SOURCE}>Upload your own files…</option>
      </select>
      {loading && <p className="source-note">Loading…</p>}
      {error && <p className="source-note error">{error}</p>}
      {current?.description && <p className="source-note">{current.description}</p>}
      {selected === UPLOAD_SOURCE && !error && (
        <p className="source-note">
          Choose result files below. They are parsed in your browser — nothing is uploaded to a
          server.
        </p>
      )}
      {loadedFiles.length > 0 && (
        <p className="source-files">Showing: {loadedFiles.join(", ")}</p>
      )}
    </div>
  );
}
