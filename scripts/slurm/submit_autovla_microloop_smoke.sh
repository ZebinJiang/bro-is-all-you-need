#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/slurm/submit_autovla_microloop_smoke.sh --script <path>

Submit a pre-rendered AutoVLA microloop smoke sbatch script.
USAGE
}

SCRIPT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --script)
      SCRIPT_PATH="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

[[ -n "$SCRIPT_PATH" ]] || { echo "--script is required" >&2; usage; exit 2; }
[[ -f "$SCRIPT_PATH" ]] || { echo "sbatch script not found: $SCRIPT_PATH" >&2; exit 2; }
command -v sbatch >/dev/null 2>&1 || {
  echo "sbatch not found. Run this submit action on an approved Slurm login node." >&2
  exit 127
}

exec sbatch "$SCRIPT_PATH"
