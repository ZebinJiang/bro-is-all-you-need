#!/usr/bin/env bash
#SBATCH --comment=autovla-m6-bounded-runtime
set -euo pipefail

: "${SANDBOX_PROJECT_ROOT:?SANDBOX_PROJECT_ROOT is required}"
: "${SANDBOX_RUN_DIR:?SANDBOX_RUN_DIR is required}"
: "${SANDBOX_RUNTIME_REQUEST:?SANDBOX_RUNTIME_REQUEST is required}"

umask 077
mkdir -p "$SANDBOX_RUN_DIR/logs" "$SANDBOX_RUN_DIR/outputs/checkpoints" \
  "$SANDBOX_RUN_DIR/tmp" "$SANDBOX_RUN_DIR/home"
export HOME="$SANDBOX_RUN_DIR/home"
export TMPDIR="$SANDBOX_RUN_DIR/tmp"
export HF_DATASETS_OFFLINE=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export WANDB_MODE=disabled
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1

cd "$SANDBOX_PROJECT_ROOT"
RUNTIME_PYTHON="$(python3 -S - "$SANDBOX_RUNTIME_REQUEST" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    value = json.load(stream).get("runtime_python")
if not isinstance(value, str) or not value:
    raise SystemExit("runtime request requires runtime_python")
print(value)
PY
)"
"$RUNTIME_PYTHON" scripts/runtime/run_m6_runtime_request.py \
  --request "$SANDBOX_RUNTIME_REQUEST" \
  --output-dir "$SANDBOX_RUN_DIR/outputs/checkpoints" \
  --evidence-json "$SANDBOX_RUN_DIR/outputs/runtime_evidence.json"
