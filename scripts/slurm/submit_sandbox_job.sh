#!/usr/bin/env bash
set -euo pipefail

usage(){ cat <<'USAGE'
Usage:
  scripts/slurm/submit_sandbox_job.sh \
    --config configs/slurm/default_sandbox.json \
    --experiment-config configs/experiments/example_experiment.json \
    --job-script scripts/slurm/template_job.sbatch \
    --run-id <safe_id> \
    [--dry-run]
USAGE
}

CONFIG=""
EXPERIMENT_CONFIG="configs/experiments/example_experiment.json"
JOB_SCRIPT="scripts/slurm/template_job.sbatch"
RUN_ID=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG="${2:-}"; shift 2 ;;
    --experiment-config) EXPERIMENT_CONFIG="${2:-}"; shift 2 ;;
    --job-script) JOB_SCRIPT="${2:-}"; shift 2 ;;
    --run-id) RUN_ID="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -n "$CONFIG" && -n "$JOB_SCRIPT" && -n "$RUN_ID" ]] || { echo "--config, --job-script, and --run-id are required" >&2; usage; exit 2; }
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid run id: $RUN_ID" >&2; exit 2; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

resolve_path(){ python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$1"; }
CONFIG_REAL="$(resolve_path "$CONFIG")"
EXPERIMENT_REAL="$(resolve_path "$EXPERIMENT_CONFIG")"
JOB_REAL="$(resolve_path "$JOB_SCRIPT")"
ROOT_REAL="$(python3 -S -c 'import pathlib; print(pathlib.Path(".").resolve())')"

case "$CONFIG_REAL" in "$ROOT_REAL"/configs/slurm/*) ;; *) echo "Config must be under configs/slurm/: $CONFIG" >&2; exit 2 ;; esac
case "$EXPERIMENT_REAL" in "$ROOT_REAL"/configs/experiments/*) ;; *) echo "Experiment config must be under configs/experiments/: $EXPERIMENT_CONFIG" >&2; exit 2 ;; esac
case "$JOB_REAL" in "$ROOT_REAL"/scripts/slurm/*) ;; *) echo "Job script must be under scripts/slurm/: $JOB_SCRIPT" >&2; exit 2 ;; esac
[[ -f "$CONFIG_REAL" ]] || { echo "Config not found: $CONFIG" >&2; exit 2; }
[[ -f "$EXPERIMENT_REAL" ]] || { echo "Experiment config not found: $EXPERIMENT_CONFIG" >&2; exit 2; }
[[ -f "$JOB_REAL" ]] || { echo "Job script not found: $JOB_SCRIPT" >&2; exit 2; }

RUN_DIR="$ROOT_REAL/runs/slurm/$RUN_ID"
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/outputs" "$RUN_DIR/tmp" "$RUN_DIR/home"

read_config(){ python3 -S - "$CONFIG_REAL" "$1" <<'PYCODE'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as file_obj:
    data=json.load(file_obj)
value=data.get(sys.argv[2], '')
print('' if value is None else value)
PYCODE
}

JOB_NAME="$(read_config job_name)"
PARTITION="$(read_config partition)"
NODES="$(read_config nodes)"
NTASKS="$(read_config ntasks)"
CPUS="$(read_config cpus_per_task)"
MEM="$(read_config mem)"
GRES="$(read_config gres)"
MAX_MINUTES="$(read_config max_minutes)"
APPROVED_CLUSTER="$(read_config approved_cluster)"

: "${JOB_NAME:=genesisvla-sandbox}"
: "${NODES:=1}"
: "${NTASKS:=1}"
: "${CPUS:=1}"
: "${MEM:=4G}"
: "${GRES:=none}"
: "${MAX_MINUTES:=30}"

NEEDS_DISCOVERY=0
for value in "$APPROVED_CLUSTER" "$PARTITION"; do
  if [[ -z "$value" || "$value" == "TO_FILL" ]]; then
    NEEDS_DISCOVERY=1
  fi
done

if [[ "$NEEDS_DISCOVERY" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
  cat >&2 <<ERR
Active Slurm config still contains TO_FILL values. Run discovery first:
  python3 -S scripts/slurm/discover_slurm_environment.py --config $CONFIG --run-id slurm-discovery-<timestamp> --write-config
ERR
  exit 2
fi

# 清理会影响 Slurm 客户端路由/配置的输入环境，同时保留 PATH 等普通环境。
SLURM_CLIENT_SANITIZED_ENV=(env)
while IFS= read -r env_name; do
  [[ "$env_name" == SBATCH_* ]] && SLURM_CLIENT_SANITIZED_ENV+=(-u "$env_name")
done < <(compgen -e)
SLURM_CLIENT_SANITIZED_ENV+=(
  -u SLURM_CLUSTERS
  -u SLURM_CLUSTER_NAME
  -u SLURM_CONF
  -u SLURM_CONF_SERVER
  -u SLURM_DEBUG_FLAGS
  -u SLURM_EXIT_ERROR
  -u SLURM_UMASK
)

# 仅在正式提交时读取 Slurm 元数据，避免 dry-run 依赖 Slurm 命令。
detect_active_cluster(){
  command -v scontrol >/dev/null 2>&1 || return 1

  # 正式集群判断只信任 scontrol；环境变量只能作为后续一致性校验。
  local config_text active_cluster
  config_text="$("${SLURM_CLIENT_SANITIZED_ENV[@]}" scontrol show config 2>/dev/null)" || return 1
  active_cluster="$(awk -F= '
    $1 ~ /^[[:space:]]*ClusterName[[:space:]]*$/ {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
      print $2
      exit
    }
  ' <<<"$config_text")"
  [[ -n "$active_cluster" && "$active_cluster" != "(null)" ]] || return 1
  printf '%s\n' "$active_cluster"
}

ACTIVE_CLUSTER="not_checked_dry_run"
CLUSTER_CHECK_STATUS="not_checked_dry_run"
CLUSTER_CHECK_MESSAGE=""
if [[ "$DRY_RUN" -eq 0 ]]; then
  ACTIVE_CLUSTER=""
  CLUSTER_CHECK_STATUS="not_required"
  if [[ -n "$APPROVED_CLUSTER" && "$APPROVED_CLUSTER" != "TO_FILL" ]]; then
    if ! ACTIVE_CLUSTER="$(detect_active_cluster)"; then
      ACTIVE_CLUSTER="undetermined"
      CLUSTER_CHECK_STATUS="failed"
      CLUSTER_CHECK_MESSAGE="Unable to determine active Slurm cluster for approved_cluster=$APPROVED_CLUSTER because scontrol show config did not report ClusterName. Refusing to trust SLURM_CLUSTER_NAME alone."
    elif [[ -n "${SLURM_CLUSTER_NAME:-}" && "$SLURM_CLUSTER_NAME" != "$ACTIVE_CLUSTER" ]]; then
      CLUSTER_CHECK_STATUS="failed"
      CLUSTER_CHECK_MESSAGE="SLURM_CLUSTER_NAME '$SLURM_CLUSTER_NAME' does not match scontrol ClusterName '$ACTIVE_CLUSTER' for approved_cluster '$APPROVED_CLUSTER'. Refusing to submit."
    elif [[ "$ACTIVE_CLUSTER" != "$APPROVED_CLUSTER" ]]; then
      CLUSTER_CHECK_STATUS="failed"
      CLUSTER_CHECK_MESSAGE="Active Slurm cluster '$ACTIVE_CLUSTER' does not match approved_cluster '$APPROVED_CLUSTER'."
    else
      CLUSTER_CHECK_STATUS="passed"
    fi
  fi
fi

# 仅导出作业必需变量，避免继承登录环境中的凭据。
EXPORT_ITEMS=(
  "SANDBOX_PROJECT_ROOT=$ROOT_REAL"
  "SANDBOX_RUN_ID=$RUN_ID"
  "SANDBOX_RUN_DIR=$RUN_DIR"
  "SANDBOX_CONFIG=$CONFIG_REAL"
  "SANDBOX_EXPERIMENT_CONFIG=$EXPERIMENT_REAL"
  "PYTHONNOUSERSITE=1"
  "PYTHONDONTWRITEBYTECODE=1"
)
EXPORT_ARG=""
for export_item in "${EXPORT_ITEMS[@]}"; do
  if [[ -z "$EXPORT_ARG" ]]; then
    EXPORT_ARG="$export_item"
  else
    EXPORT_ARG="$EXPORT_ARG,$export_item"
  fi
done

SBATCH_ARGS=(
  --job-name="$JOB_NAME"
  --nodes="$NODES"
  --ntasks="$NTASKS"
  --cpus-per-task="$CPUS"
  --mem="$MEM"
  --time="$MAX_MINUTES"
  --chdir="$ROOT_REAL"
  --output="$RUN_DIR/logs/stdout.log"
  --error="$RUN_DIR/logs/stderr.log"
  --export="$EXPORT_ARG"
)
[[ -n "$PARTITION" && "$PARTITION" != "TO_FILL" ]] && SBATCH_ARGS+=(--partition="$PARTITION")
[[ -n "$GRES" && "$GRES" != "none" ]] && SBATCH_ARGS+=(--gres="$GRES")
[[ -n "$APPROVED_CLUSTER" && "$APPROVED_CLUSTER" != "TO_FILL" ]] && SBATCH_ARGS+=(--clusters="$APPROVED_CLUSTER")

{
  echo "run_id=$RUN_ID"
  echo "run_dir=$RUN_DIR"
  echo "config=$CONFIG_REAL"
  echo "experiment_config=$EXPERIMENT_REAL"
  echo "job_script=$JOB_REAL"
  echo "approved_cluster=$APPROVED_CLUSTER"
  echo "active_cluster=$ACTIVE_CLUSTER"
  echo "cluster_check_status=$CLUSTER_CHECK_STATUS"
  [[ -n "$CLUSTER_CHECK_MESSAGE" ]] && echo "cluster_check_message=$CLUSTER_CHECK_MESSAGE"
  echo "needs_discovery=$NEEDS_DISCOVERY"
  if [[ "$NEEDS_DISCOVERY" -eq 1 ]]; then
    echo "warning=Slurm config contains TO_FILL. Dry-run is allowed, but formal submission requires discovery and config fill."
  fi
  echo "reproducibility_note=Manager and agents use this wrapper; the raw sbatch command below is logged for human reproduction."
  printf 'sbatch'; for arg in "${SBATCH_ARGS[@]}"; do printf ' %q' "$arg"; done; printf ' %q\n' "$JOB_REAL"
} > "$RUN_DIR/logs/submission_command.txt"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "DRY RUN: no job submitted"
  cat "$RUN_DIR/logs/submission_command.txt"
  exit 0
fi

if [[ "$CLUSTER_CHECK_STATUS" == "failed" ]]; then
  echo "$CLUSTER_CHECK_MESSAGE" >&2
  exit 2
fi

command -v sbatch >/dev/null 2>&1 || { echo "sbatch not found. Run on an approved Slurm server or use --dry-run." >&2; exit 127; }
SUBMIT_OUTPUT="$("${SLURM_CLIENT_SANITIZED_ENV[@]}" sbatch "${SBATCH_ARGS[@]}" "$JOB_REAL")"
echo "$SUBMIT_OUTPUT" | tee "$RUN_DIR/logs/submission.txt"
python3 -S - "$RUN_DIR" "$SUBMIT_OUTPUT" <<'PYCODE'
import json, re, sys
from pathlib import Path
run_dir = Path(sys.argv[1])
submit_output = sys.argv[2]
match = re.search(r'(\d+)', submit_output)
manifest = {
    'submit_output': submit_output,
    'slurm_job_id': match.group(1) if match else None,
    'run_dir': str(run_dir),
}
with (run_dir / 'outputs' / 'submission_manifest.json').open('w', encoding='utf-8') as file_obj:
    json.dump(manifest, file_obj, indent=2, sort_keys=True)
    file_obj.write('\n')
PYCODE
