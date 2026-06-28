#!/usr/bin/env bash
#SBATCH --comment=autovla-sandbox
set -euo pipefail

: "${SANDBOX_PROJECT_ROOT:?SANDBOX_PROJECT_ROOT is required}"
: "${SANDBOX_RUN_ID:?SANDBOX_RUN_ID is required}"
: "${SANDBOX_RUN_DIR:?SANDBOX_RUN_DIR is required}"
: "${SANDBOX_CONFIG:?SANDBOX_CONFIG is required}"
: "${SANDBOX_EXPERIMENT_CONFIG:?SANDBOX_EXPERIMENT_CONFIG is required}"

umask 077
mkdir -p "$SANDBOX_RUN_DIR/logs" "$SANDBOX_RUN_DIR/outputs" "$SANDBOX_RUN_DIR/tmp" "$SANDBOX_RUN_DIR/home"
export TMPDIR="$SANDBOX_RUN_DIR/tmp"
export HOME="$SANDBOX_RUN_DIR/home"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1

cd "$SANDBOX_PROJECT_ROOT"
cat > "$SANDBOX_RUN_DIR/outputs/run_manifest.json" <<EOF
{"run_id":"$SANDBOX_RUN_ID","run_dir":"$SANDBOX_RUN_DIR","slurm_config":"$SANDBOX_CONFIG","experiment_config":"$SANDBOX_EXPERIMENT_CONFIG","slurm_job_id":"${SLURM_JOB_ID:-not_available}"}
EOF

python3 -S examples/mock_autovla_task.py \
  --config "$SANDBOX_EXPERIMENT_CONFIG" \
  --output "$SANDBOX_RUN_DIR/outputs/mock_result.json"

echo "autovla sandbox job completed: $SANDBOX_RUN_ID"
