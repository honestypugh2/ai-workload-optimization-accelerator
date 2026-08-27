#!/usr/bin/env bash
# Lint the codebase with ruff.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff check .
