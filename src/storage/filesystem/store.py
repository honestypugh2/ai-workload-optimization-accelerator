"""Filesystem-backed result store (default, cloud-independent)."""

from __future__ import annotations

import json
from pathlib import Path


class FilesystemResultStore:
    """Persists JSON payloads to a local directory."""

    def __init__(self, root: str | Path = "workload-scenarios") -> None:
        self._root = Path(root)

    def save(self, key: str, payload: dict) -> str:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)

    def load(self, key: str) -> dict:
        path = self._root / key
        return json.loads(path.read_text(encoding="utf-8"))
