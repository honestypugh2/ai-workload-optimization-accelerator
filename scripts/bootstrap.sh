#!/usr/bin/env bash
# Bootstrap a local development environment (offline-capable).
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "error: 'uv' is required. Install from https://docs.astral.sh/uv/" >&2
  exit 1
fi

echo "==> Syncing dependencies (dev extra)"
uv sync --extra dev

echo "==> Verifying the CLI is wired up"
uv run aiwoa scenario list

echo
echo "Bootstrap complete. Try:"
echo "  ./scripts/benchmark.sh"
echo "  ./scripts/evaluate.sh"
