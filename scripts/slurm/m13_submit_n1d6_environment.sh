#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/slurm/m13_submit_n1d6_environment.sh \
    --runtime-request runs/<task>/requests/<request>.json \
    --run-id <safe-id> [--dry-run]
USAGE
}

RUNTIME_REQUEST=""
RUN_ID=""
DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime-request) RUNTIME_REQUEST="${2:-}"; shift 2 ;;
    --run-id) RUN_ID="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done
[[ -n "$RUNTIME_REQUEST" && -n "$RUN_ID" ]] || {
  echo "--runtime-request and --run-id are required" >&2
  exit 2
}

COMMAND=(
  scripts/slurm/submit_sandbox_job.sh
  --config configs/slurm/m13_n1d6_environment_a100.json
  --experiment-config configs/experiments/m13_n1d6_environment.json
  --job-script scripts/slurm/m13_n1d6_environment.sbatch
  --runtime-request "$RUNTIME_REQUEST"
  --run-id "$RUN_ID"
)
[[ "$DRY_RUN" -eq 1 ]] && COMMAND+=(--dry-run)
printf 'wrapper command:'
printf ' %q' "${COMMAND[@]}"
printf '\n'
exec "${COMMAND[@]}"
