#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VENV="$ROOT/runs/tmp/m1-tool-venv"
PY="$VENV/bin/python"
PIP_CACHE="$ROOT/runs/tmp/m1-tool-pip-cache"
PIP_TMP="$ROOT/runs/tmp/m1-tool-pip-tmp"

export PIP_CACHE_DIR="$PIP_CACHE"
export TMPDIR="$PIP_TMP"

mkdir -p "$PIP_CACHE" "$PIP_TMP" "$(dirname "$VENV")"

if [[ ! -x "$PY" ]]; then
  python -m venv "$VENV"
fi

"$PY" -m pip install -U pip
"$PY" -m pip install -e ".[dev]"
