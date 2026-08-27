import { useRef } from "react";

interface FileLoaderProps {
  label: string;
  accept: string;
  multiple?: boolean;
  onLoad: (files: { name: string; data: unknown }[]) => void;
}

/** A thin file picker that parses selected JSON files in the browser. */
export function FileLoader({ label, accept, multiple, onLoad }: FileLoaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    const parsed: { name: string; data: unknown }[] = [];
    for (const file of files) {
      try {
        const text = await file.text();
        parsed.push({ name: file.name, data: JSON.parse(text) });
      } catch {
        parsed.push({ name: file.name, data: null });
      }
    }
    onLoad(parsed);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  return (
    <div className="loader">
      <h2>{label}</h2>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleChange}
      />
    </div>
  );
}
