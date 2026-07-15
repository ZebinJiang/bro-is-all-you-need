#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --target {gpu|ddp|fsdp2} --request PATH --run-id ID [--execute]" >&2
}

TARGET=""
REQUEST=""
RUN_ID=""
EXECUTE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2 ;;
    --request) REQUEST="${2:-}"; shift 2 ;;
    --run-id) RUN_ID="${2:-}"; shift 2 ;;
    --execute) EXECUTE=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done
case "$TARGET" in gpu|ddp|fsdp2) ;; *) echo "unsupported target: $TARGET" >&2; exit 2 ;; esac
[[ -n "$REQUEST" && -n "$RUN_ID" ]] || { usage; exit 2; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
RUNTIME_PYTHON="$(python3 -S - "$REQUEST" "$TARGET" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    request = json.load(stream)
if request.get("target") != sys.argv[2]:
    raise SystemExit("runtime request target does not match --target")
if request.get("max_steps") != 2 or request.get("offline") is not True:
    raise SystemExit("runtime request must remain offline with max_steps=2")
runtime_python = request.get("runtime_python")
if not isinstance(runtime_python, str) or not runtime_python:
    raise SystemExit("runtime request requires runtime_python")
print(runtime_python)
PY
)"
"$RUNTIME_PYTHON" scripts/runtime/render_m6_runtime_command.py \
  --request "$REQUEST" >/dev/null

WRAPPER_ARGS=(
  --config "configs/slurm/m6_runtime_${TARGET}.json"
  --experiment-config configs/experiments/m6_runtime.json
  --job-script scripts/slurm/m6_runtime_job.sbatch
  --run-id "$RUN_ID"
  --runtime-request "$REQUEST"
)
if [[ "$EXECUTE" -eq 0 ]]; then
  WRAPPER_ARGS+=(--dry-run)
fi
exec bash scripts/slurm/submit_sandbox_job.sh "${WRAPPER_ARGS[@]}"
