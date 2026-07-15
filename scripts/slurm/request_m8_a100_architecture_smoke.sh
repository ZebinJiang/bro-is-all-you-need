#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/slurm/request_m8_a100_architecture_smoke.sh \
    --target <single_gpu|same_node_ddp|same_node_zero1|same_node_zero2|same_node_zero3|cross_node_ddp|cross_node_zero3> \
    --run-id <safe_id> [--submit]

Without --submit, print the exact project-wrapper command and perform no write or submission.
USAGE
}

TARGET=""
RUN_ID=""
SUBMIT=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2 ;;
    --run-id) RUN_ID="${2:-}"; shift 2 ;;
    --submit) SUBMIT=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

case "$TARGET" in
  single_gpu|same_node_ddp|same_node_zero1|same_node_zero2|same_node_zero3|cross_node_ddp|cross_node_zero3) ;;
  *) echo "unsupported M8 target: $TARGET" >&2; exit 2 ;;
esac
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "invalid run id: $RUN_ID" >&2; exit 2; }

case "$TARGET" in
  same_node_zero1|same_node_zero2|same_node_zero3|cross_node_zero3)
    RUNTIME_PROFILE=training-deepspeed
    ;;
  *) RUNTIME_PROFILE=model-gr00t-n1d6 ;;
esac

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
CONFIG="configs/slurm/m8_a100_${TARGET}.json"
EXPERIMENT="configs/experiments/m8_a100_architecture_smoke.json"
JOB_SCRIPT="scripts/slurm/m8_a100_architecture_smoke.sbatch"
COMMAND=(
  bash scripts/slurm/submit_sandbox_job.sh
  --config "$CONFIG"
  --experiment-config "$EXPERIMENT"
  --job-script "$JOB_SCRIPT"
  --run-id "$RUN_ID"
)

if [[ "$SUBMIT" -eq 0 ]]; then
  printf 'target=%s\nconfig=%s\npartition=a100\nruntime_profile=%s\noutput_root=runs/slurm\n' \
    "$TARGET" "$CONFIG" "$RUNTIME_PROFILE"
  printf 'rendered_command='
  printf '%q ' "${COMMAND[@]}"
  printf '\nsubmission=not_requested\n'
  exit 0
fi

PROFILE_INTERPRETER="$ROOT_DIR/envs/$RUNTIME_PROFILE/.venv/bin/python"
case "$PROFILE_INTERPRETER" in
  "$ROOT_DIR"/envs/*/.venv/bin/python) ;;
  *) echo "runtime interpreter escaped project-managed env profile: $PROFILE_INTERPRETER" >&2; exit 2 ;;
esac
if [[ ! -x "$PROFILE_INTERPRETER" ]]; then
  cat >&2 <<ERROR
M8 runtime profile is unavailable: $RUNTIME_PROFILE
Expected project-managed interpreter: $PROFILE_INTERPRETER
Wave 8 must manually authorize and prepare this uv profile, generate/verify its lock,
then collect the versioned environment fingerprint before submission. No fallback is allowed.
ERROR
  exit 127
fi

exec "${COMMAND[@]}"
