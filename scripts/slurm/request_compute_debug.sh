#!/usr/bin/env bash
set -euo pipefail

usage(){ cat <<'USAGE'
Usage:
  scripts/slurm/request_compute_debug.sh \
    --profile <default|h800-gpu> \
    --run-id <safe_id> \
    [--profiles configs/slurm/debug_profiles.json] \
    [--partition <name>] [--cpus <n>] [--mem <size>] [--gres <gres|none>] [--time <HH:MM:SS>] \
    [--dry-run] [-- <command> [args...]]

Examples:
  scripts/slurm/request_compute_debug.sh --profile h800-gpu --run-id debug-001 --dry-run
  scripts/slurm/request_compute_debug.sh --profile h800-gpu --run-id debug-001 -- bash
USAGE
}

PROFILES="configs/slurm/debug_profiles.json"
PROFILE="default"
RUN_ID=""
DRY_RUN=0
OVERRIDE_PARTITION=""
OVERRIDE_CPUS=""
OVERRIDE_MEM=""
OVERRIDE_GRES=""
OVERRIDE_TIME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profiles) PROFILES="${2:-}"; shift 2 ;;
    --profile) PROFILE="${2:-}"; shift 2 ;;
    --run-id) RUN_ID="${2:-}"; shift 2 ;;
    --partition) OVERRIDE_PARTITION="${2:-}"; shift 2 ;;
    --cpus) OVERRIDE_CPUS="${2:-}"; shift 2 ;;
    --mem) OVERRIDE_MEM="${2:-}"; shift 2 ;;
    --gres) OVERRIDE_GRES="${2:-}"; shift 2 ;;
    --time) OVERRIDE_TIME="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) usage; exit 0 ;;
    --) shift; break ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -n "$RUN_ID" ]] || { echo "--run-id is required" >&2; usage; exit 2; }
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid run id: $RUN_ID" >&2; exit 2; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
[[ -f "$PROFILES" ]] || { echo "Profiles file not found: $PROFILES" >&2; exit 2; }

eval "$(python3 -S - "$PROFILES" "$PROFILE" <<'PYCODE'
import json, shlex, sys
from pathlib import Path
profiles = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')).get('profiles', {})
profile = profiles.get(sys.argv[2])
if profile is None:
    raise SystemExit(f'profile not found: {sys.argv[2]}')
for key in ['partition', 'cpus_per_task', 'mem', 'gres', 'time']:
    value = str(profile.get(key, ''))
    print(f'{key.upper()}={shlex.quote(value)}')
PYCODE
)"

PARTITION="${OVERRIDE_PARTITION:-$PARTITION}"
CPUS_PER_TASK="${OVERRIDE_CPUS:-$CPUS_PER_TASK}"
MEM="${OVERRIDE_MEM:-$MEM}"
GRES="${OVERRIDE_GRES:-$GRES}"
TIME="${OVERRIDE_TIME:-$TIME}"

RUN_DIR="$ROOT_DIR/runs/slurm_debug/$RUN_ID"
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/outputs" "$RUN_DIR/tmp" "$RUN_DIR/home"

CMD=("$@")
if [[ ${#CMD[@]} -eq 0 ]]; then
  CMD=(bash)
fi

if [[ -z "$PARTITION" || "$PARTITION" == "TO_FILL" ]]; then
  if [[ "$DRY_RUN" -eq 0 ]]; then
    echo "Debug profile partition is TO_FILL. Run Slurm discovery, fill config/profile, or pass --partition explicitly." >&2
    exit 2
  fi
fi

SRUN_ARGS=(
  -c "$CPUS_PER_TASK"
  --mem="$MEM"
  --time="$TIME"
  --chdir="$ROOT_DIR"
  --export="ALL,SANDBOX_PROJECT_ROOT=$ROOT_DIR,SANDBOX_RUN_ID=$RUN_ID,SANDBOX_RUN_DIR=$RUN_DIR,PYTHONNOUSERSITE=1"
)
[[ -n "$PARTITION" && "$PARTITION" != "TO_FILL" ]] && SRUN_ARGS=(-p "$PARTITION" "${SRUN_ARGS[@]}")
[[ -n "$GRES" && "$GRES" != "none" ]] && SRUN_ARGS+=(--gres="$GRES")
SRUN_ARGS+=(--pty)

{
  echo "run_id=$RUN_ID"
  echo "run_dir=$RUN_DIR"
  echo "profile=$PROFILE"
  echo "partition=$PARTITION"
  echo "cpus_per_task=$CPUS_PER_TASK"
  echo "mem=$MEM"
  echo "gres=$GRES"
  echo "time=$TIME"
  echo "reproducibility_note=Manager and agents use this helper; the raw srun command below is logged for human reproduction."
  printf 'srun'; for arg in "${SRUN_ARGS[@]}"; do printf ' %q' "$arg"; done; for arg in "${CMD[@]}"; do printf ' %q' "$arg"; done; printf '\n'
} > "$RUN_DIR/logs/srun_command.txt"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "DRY RUN: no allocation requested"
  cat "$RUN_DIR/logs/srun_command.txt"
  exit 0
fi

command -v srun >/dev/null 2>&1 || { echo "srun not found. Run on an approved Slurm login node or use --dry-run." >&2; exit 127; }
export SANDBOX_PROJECT_ROOT="$ROOT_DIR"
export SANDBOX_RUN_ID="$RUN_ID"
export SANDBOX_RUN_DIR="$RUN_DIR"
export TMPDIR="$RUN_DIR/tmp"
export HOME="$RUN_DIR/home"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
exec srun "${SRUN_ARGS[@]}" "${CMD[@]}"
