#!/usr/bin/env bash
# Static type-check with pyright.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pyright
