#!/usr/bin/env bash
#SBATCH --comment=autovla-m13-n1d6-environment
set -Eeuo pipefail

: "${SANDBOX_PROJECT_ROOT:?SANDBOX_PROJECT_ROOT is required}"
: "${SANDBOX_RUN_ID:?SANDBOX_RUN_ID is required}"
: "${SANDBOX_RUN_DIR:?SANDBOX_RUN_DIR is required}"
: "${SANDBOX_CONFIG:?SANDBOX_CONFIG is required}"
: "${SANDBOX_EXPERIMENT_CONFIG:?SANDBOX_EXPERIMENT_CONFIG is required}"
: "${SANDBOX_RUNTIME_REQUEST:?--runtime-request under project runs/ is required}"

TASK_ID="AUTOVLA-M13-ARCHITECTURE-FIRST-OFFICIAL-FAMILY-RUNTIME-REALIZATION-001"
PROFILE_ID="gr00t_n1d6_runtime"
VALIDATED_REQUEST="$SANDBOX_RUN_DIR/outputs/validated-runtime-request.json"
CUDA_INTENT="$SANDBOX_RUN_DIR/outputs/cuda-intent.json"
LOCK_RESULT="$SANDBOX_RUN_DIR/outputs/resolve-result.json"
RESOLVED_LOCK="$SANDBOX_RUN_DIR/outputs/resolved-lock.json"
ENVIRONMENT_RESULT="$SANDBOX_RUN_DIR/outputs/environment-command-result.json"
ENVIRONMENT_RECEIPT="$SANDBOX_RUN_DIR/outputs/environment-receipt.json"
RAW_COMMANDS="$SANDBOX_RUN_DIR/outputs/raw-commands.txt"
RESULT="$SANDBOX_RUN_DIR/outputs/result.json"
CURRENT_PHASE="bootstrap"
PRIMARY_STATUS=0

write_result() {
  local status="$?"
  trap - EXIT
  PRIMARY_STATUS="$status"
  python3 -S - "$RESULT" "$CURRENT_PHASE" "$PRIMARY_STATUS" "$VALIDATED_REQUEST" \
    "$RESOLVED_LOCK" "$ENVIRONMENT_RECEIPT" "$RAW_COMMANDS" \
    "${SLURM_JOB_ID:-unknown}" "${SLURMD_NODENAME:-${HOSTNAME:-unknown}}" <<'PY'
import json
import sys
from pathlib import Path

output, phase, status, request_path, lock_path, receipt_path, commands_path, job_id, node = sys.argv[1:]


def load(path_text):
    """读取存在的 JSON 证据,失败时保留空对象。"""
    path = Path(path_text)
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


payload = {
    "schema_version": "autovla.m13_n1d6_environment_result.v1",
    "phase": phase,
    "status": "pass" if int(status) == 0 else "fail",
    "exit_code": int(status),
    "request": load(request_path),
    "resolved_lock": load(lock_path),
    "environment_receipt": load(receipt_path),
    "raw_commands_path": str(Path(commands_path)),
    "network_on_compute": False,
    "cache_prime_performed": False,
    "slurm": {"job_id": job_id, "node": node},
}
Path(output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  exit "$PRIMARY_STATUS"
}
trap write_result EXIT

PROJECT_ROOT_REAL="$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$SANDBOX_PROJECT_ROOT")"
COMMON_GIT_DIR="$(git -C "$PROJECT_ROOT_REAL" rev-parse --path-format=absolute --git-common-dir)"
WORKSPACE_ROOT="$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True).parent)' "$COMMON_GIT_DIR")"
EXPECTED_CONFIG="$PROJECT_ROOT_REAL/configs/slurm/m13_n1d6_environment_a100.json"
EXPECTED_EXPERIMENT="$PROJECT_ROOT_REAL/configs/experiments/m13_n1d6_environment.json"
[[ "$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$SANDBOX_CONFIG")" == "$EXPECTED_CONFIG" ]] || {
  echo "M13 environment harness requires configs/slurm/m13_n1d6_environment_a100.json" >&2
  exit 2
}
[[ "$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$SANDBOX_EXPERIMENT_CONFIG")" == "$EXPECTED_EXPERIMENT" ]] || {
  echo "M13 environment harness requires configs/experiments/m13_n1d6_environment.json" >&2
  exit 2
}
[[ "${SLURM_JOB_NUM_NODES:-}" == "1" && "${SLURM_NTASKS:-}" == "1" ]] || {
  echo "M13 environment harness requires exactly one node and one task" >&2
  exit 2
}

# Compute 节点始终离线;cache prime 只能走独立显式脚本。
umask 077
export HOME="$SANDBOX_RUN_DIR/home"
export TMPDIR="$SANDBOX_RUN_DIR/tmp"
export XDG_CACHE_HOME="$SANDBOX_RUN_DIR/home/.cache"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export PIP_NO_INDEX=1
export UV_OFFLINE=1
export WANDB_MODE=disabled
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy NO_PROXY no_proxy

CURRENT_PHASE="validate_runtime_request"
python3 -S scripts/validation/m13_n1d6_harness.py validate-environment-request \
  --request "$SANDBOX_RUNTIME_REQUEST" \
  --project-root "$PROJECT_ROOT_REAL" \
  --output "$VALIDATED_REQUEST"

ACTION="$(python3 -S -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["action"])' "$VALIDATED_REQUEST")"
python3 -S - "$VALIDATED_REQUEST" "$CUDA_INTENT" <<'PY'
import json
import sys
from pathlib import Path

request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
Path(sys.argv[2]).write_text(
    json.dumps(request["cuda_intent"], indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

CURRENT_PHASE="verify_a100_intent"
GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -n 1)"
[[ "${GPU_NAME^^}" == *A100* ]] || {
  echo "M13 N1D6 environment harness requires an A100, got: $GPU_NAME" >&2
  exit 2
}

record_command() {
  local label="$1"
  shift
  printf '%s:' "$label" >> "$RAW_COMMANDS"
  printf ' %q' "$@" >> "$RAW_COMMANDS"
  printf '\n' >> "$RAW_COMMANDS"
}

extract_result() {
  local source="$1"
  local destination="$2"
  python3 -S - "$source" "$destination" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not isinstance(payload, dict) or payload.get("ok") is not True or not isinstance(payload.get("result"), dict):
    raise SystemExit("autovla environment command did not return a successful result object")
Path(sys.argv[2]).write_text(
    json.dumps(payload["result"], indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
}

CURRENT_PHASE="resolve_exact_lock"
RESOLVE_COMMAND=(
  python3 -S -m autovla.cli.env
  --checkout-root "$PROJECT_ROOT_REAL"
  resolve "$PROFILE_ID"
  --cuda-intent-receipt "$(realpath --relative-to="$PROJECT_ROOT_REAL" "$CUDA_INTENT")"
)
record_command resolve "${RESOLVE_COMMAND[@]}"
"${RESOLVE_COMMAND[@]}" > "$LOCK_RESULT"
extract_result "$LOCK_RESULT" "$RESOLVED_LOCK"

if [[ "$ACTION" == "preflight" ]]; then
  CURRENT_PHASE="preflight_complete"
  exit 0
fi

LOCK_RELATIVE="$(realpath --relative-to="$PROJECT_ROOT_REAL" "$RESOLVED_LOCK")"
if [[ "$ACTION" == "materialize" ]]; then
  NONCE="$(python3 -S -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["nonce"])' "$VALIDATED_REQUEST")"
  CURRENT_PHASE="offline_materialize"
  ENV_COMMAND=(
    python3 -S -m autovla.cli.env
    --checkout-root "$PROJECT_ROOT_REAL"
    --workspace-root "$WORKSPACE_ROOT"
    create "$PROFILE_ID"
    --lock-receipt "$LOCK_RELATIVE"
    --nonce "$NONCE"
    --allow-create
  )
else
  CURRENT_PHASE="verify_existing_environment"
  ENV_COMMAND=(
    python3 -S -m autovla.cli.env
    --checkout-root "$PROJECT_ROOT_REAL"
    --workspace-root "$WORKSPACE_ROOT"
    verify "$PROFILE_ID"
    --lock-receipt "$LOCK_RELATIVE"
  )
fi
record_command "$ACTION" "${ENV_COMMAND[@]}"
"${ENV_COMMAND[@]}" > "$ENVIRONMENT_RESULT"
extract_result "$ENVIRONMENT_RESULT" "$ENVIRONMENT_RECEIPT"
CURRENT_PHASE="${ACTION}_complete"
