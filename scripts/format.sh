#!/usr/bin/env bash
# Auto-format the codebase with ruff.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff format .
uv run ruff check --fix .
