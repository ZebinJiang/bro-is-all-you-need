#!/usr/bin/env bash
#SBATCH --comment=autovla-m8-a100-architecture-smoke
set -euo pipefail

: "${SANDBOX_PROJECT_ROOT:?SANDBOX_PROJECT_ROOT is required}"
: "${SANDBOX_RUN_DIR:?SANDBOX_RUN_DIR is required}"
: "${SANDBOX_CONFIG:?SANDBOX_CONFIG is required}"

umask 077
mkdir -p "$SANDBOX_RUN_DIR/logs" "$SANDBOX_RUN_DIR/outputs" \
  "$SANDBOX_RUN_DIR/outputs/checkpoints" "$SANDBOX_RUN_DIR/tmp" "$SANDBOX_RUN_DIR/home"
export HOME="$SANDBOX_RUN_DIR/home"
export TMPDIR="$SANDBOX_RUN_DIR/tmp"
export AUTOVLA_MODEL_HOME=/home/cz-jzb/workspace/vla-flywheel/base_model
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export WANDB_MODE=disabled
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1

cd "$SANDBOX_PROJECT_ROOT"
TARGET="$(basename "$SANDBOX_CONFIG" .json)"
TARGET="${TARGET#m8_a100_}"
PROFILE_ID="model-gr00t-n1d6"

case "$TARGET" in
  single_gpu)
    EXPERIMENT=configs/experiments/gr00t_n1d6_webdataset.yaml
    NODES=1
    NTASKS=1
    LOCAL_WORLD_SIZE=1
    ;;
  same_node_ddp)
    EXPERIMENT=configs/experiments/gr00t_n1d6_webdataset_ddp.yaml
    NODES=1
    NTASKS=2
    LOCAL_WORLD_SIZE=2
    ;;
  same_node_zero1|same_node_zero2|same_node_zero3)
    EXPERIMENT="configs/experiments/gr00t_n1d6_webdataset_${TARGET#same_node_}.yaml"
    NODES=1
    NTASKS=2
    LOCAL_WORLD_SIZE=2
    PROFILE_ID=training-deepspeed
    ;;
  cross_node_ddp)
    EXPERIMENT=configs/experiments/gr00t_n1d6_webdataset_ddp.yaml
    NODES=2
    NTASKS=4
    LOCAL_WORLD_SIZE=2
    ;;
  cross_node_zero3)
    EXPERIMENT=configs/experiments/gr00t_n1d6_webdataset_zero3.yaml
    NODES=2
    NTASKS=4
    LOCAL_WORLD_SIZE=2
    PROFILE_ID=training-deepspeed
    ;;
  *) echo "unsupported M8 target from config: $TARGET" >&2; exit 2 ;;
esac

PROFILE_INTERPRETER="$SANDBOX_PROJECT_ROOT/envs/$PROFILE_ID/.venv/bin/python"
case "$PROFILE_INTERPRETER" in
  "$SANDBOX_PROJECT_ROOT"/envs/*/.venv/bin/python) ;;
  *) echo "runtime interpreter escaped project-managed env profile: $PROFILE_INTERPRETER" >&2; exit 2 ;;
esac
if [[ ! -x "$PROFILE_INTERPRETER" ]]; then
  cat >&2 <<ERROR
M8 runtime profile is unavailable: $PROFILE_ID
Expected project-managed interpreter: $PROFILE_INTERPRETER
Wave 8 must manually authorize and prepare this uv profile, generate/verify its lock,
then collect the versioned environment fingerprint before submission. No fallback is allowed.
ERROR
  exit 127
fi

ASSET_EVIDENCE="$SANDBOX_RUN_DIR/outputs/asset-verification.json"
"$PROFILE_INTERPRETER" -m autovla.cli.assets \
  --root "$AUTOVLA_MODEL_HOME" --json verify gr00t_n1d6 > "$ASSET_EVIDENCE"

CHECKPOINT_DIR="$SANDBOX_RUN_DIR/outputs/checkpoints"
METRICS_PATH="$SANDBOX_RUN_DIR/logs/metrics.jsonl"
LAUNCH_MANIFEST="$SANDBOX_RUN_DIR/outputs/runtime-launch.json"
RESULT_MANIFEST="$SANDBOX_RUN_DIR/outputs/runtime-result.json"
SOURCE_SHA="$(git rev-parse HEAD)"

TRAIN_COMMAND=(
  "$PROFILE_INTERPRETER" -m autovla.cli.train "$EXPERIMENT"
  --set "training.max_steps=2"
  --set "training.distributed.world_size=$NTASKS"
  --set "training.checkpoint.directory=$CHECKPOINT_DIR"
  --set "training.logging.jsonl_path=$METRICS_PATH"
)

write_runtime_manifest() {
  local output_path="$1"
  local phase="$2"
  local exit_status="$3"
  "$PROFILE_INTERPRETER" - "$output_path" "$phase" "$exit_status" \
    "$SOURCE_SHA" "$TARGET" "$NODES" "$NTASKS" "$LOCAL_WORLD_SIZE" \
    "$PROFILE_ID" "$PROFILE_INTERPRETER" "$ASSET_EVIDENCE" \
    "$CHECKPOINT_DIR" "$METRICS_PATH" "$SANDBOX_RUN_DIR/logs" -- \
    "${TRAIN_COMMAND[@]}" <<'PY'
import importlib.metadata
import json
import sys
from pathlib import Path

(
    output_path,
    phase,
    exit_status,
    source_sha,
    target,
    nodes,
    tasks,
    local_world_size,
    profile_id,
    interpreter,
    asset_evidence_path,
    checkpoint_dir,
    metrics_path,
    logs_path,
    separator,
    *command,
) = sys.argv[1:]
if separator != "--":
    raise SystemExit("runtime manifest command separator is invalid")
asset_evidence = json.loads(Path(asset_evidence_path).read_text(encoding="utf-8"))
if asset_evidence.get("ok") is not True:
    raise SystemExit("offline model asset verification did not pass")
result = asset_evidence.get("result")
if not isinstance(result, dict) or not isinstance(result.get("identity"), str):
    raise SystemExit("offline model asset verification identity is missing")
packages = {}
for distribution in (
    "autovla",
    "numpy",
    "omegaconf",
    "torch",
    "transformers",
    "safetensors",
    "huggingface-hub",
    "webdataset",
    "deepspeed",
):
    try:
        packages[distribution] = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        packages[distribution] = "not-installed"
payload = {
    "schema_version": "autovla.m8_runtime_evidence.v1",
    "phase": phase,
    "source_sha": source_sha,
    "target": target,
    "topology": {
        "nodes": int(nodes),
        "tasks": int(tasks),
        "tasks_per_node": int(local_world_size),
    },
    "runtime_profile": profile_id,
    "interpreter": str(Path(interpreter).resolve()),
    "package_versions": packages,
    "offline_asset_verification": {
        "key": result.get("key"),
        "identity": result["identity"],
        "revision": result.get("revision"),
        "verification_state": result.get("verification_state"),
        "evidence_path": asset_evidence_path,
    },
    "command": command,
    "exit_status": None if exit_status == "not_finished" else int(exit_status),
    "outputs": {
        "checkpoint_dir": checkpoint_dir,
        "metrics_path": metrics_path,
        "logs_dir": logs_path,
    },
}
Path(output_path).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
}

write_runtime_manifest "$LAUNCH_MANIFEST" launch not_finished

record_result() {
  local status="$?"
  trap - EXIT
  write_runtime_manifest "$RESULT_MANIFEST" result "$status"
  exit "$status"
}
trap record_result EXIT

if [[ "$NTASKS" -eq 1 ]]; then
  "${TRAIN_COMMAND[@]}"
  exit $?
fi

export MASTER_ADDR="$(scontrol show hostnames "$SLURM_JOB_NODELIST" | sed -n '1p')"
export MASTER_PORT="$((20000 + SLURM_JOB_ID % 10000))"
srun --nodes="$NODES" --ntasks="$NTASKS" --ntasks-per-node="$LOCAL_WORLD_SIZE" \
  --distribution=block:block --kill-on-bad-exit=1 \
  "${TRAIN_COMMAND[@]}"
