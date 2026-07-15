#!/usr/bin/env bash
#SBATCH --comment=autovla-m9-bounded-a100-architecture-smoke
set -Eeuo pipefail

: "${SANDBOX_PROJECT_ROOT:?SANDBOX_PROJECT_ROOT is required}"
: "${SANDBOX_RUN_ID:?SANDBOX_RUN_ID is required}"
: "${SANDBOX_RUN_DIR:?SANDBOX_RUN_DIR is required}"
: "${SANDBOX_CONFIG:?SANDBOX_CONFIG is required}"
: "${SANDBOX_EXPERIMENT_CONFIG:?SANDBOX_EXPERIMENT_CONFIG is required}"
: "${SANDBOX_RUNTIME_REQUEST:?--runtime-request under project runs/ is required}"

TASK_ID="AUTOVLA-M9-ARCHITECTURE-COMPLETION-UNIFIED-SEMANTICS-UPSTREAM-INTEGRATION-001"
REQUEST_SCHEMA="autovla.m9_a100_runtime_request.v1"
ASSET_ROOT="/home/cz-jzb/workspace/vla-flywheel/base_model"
PROFILE_ID="model-gr00t-n1d6"
PROFILE_INTERPRETER="$SANDBOX_PROJECT_ROOT/envs/$PROFILE_ID/.venv/bin/python"
VALIDATED_REQUEST="$SANDBOX_RUN_DIR/outputs/validated-runtime-request.json"
ASSET_EVIDENCE="$SANDBOX_RUN_DIR/outputs/asset-verification.json"
RESOLVED_CONFIG="$SANDBOX_RUN_DIR/outputs/resolved-config.json"
CONFIG_METADATA="$SANDBOX_RUN_DIR/outputs/config-metadata.json"
OVERRIDES_EVIDENCE="$SANDBOX_RUN_DIR/outputs/canonical-overrides.json"
RUNTIME_INFO="$SANDBOX_RUN_DIR/outputs/runtime-info.json"
COMMAND_EVIDENCE="$SANDBOX_RUN_DIR/outputs/command.json"
LAUNCH_EVIDENCE="$SANDBOX_RUN_DIR/outputs/runtime-launch.json"
RESULT_EVIDENCE="$SANDBOX_RUN_DIR/outputs/runtime-result.json"
CURRENT_PHASE="bootstrap"
PRIMARY_FAILURE_COMMAND=""
PRIMARY_FAILURE_LINE=""
SOURCE_HEAD="unknown"

capture_primary_failure() {
  PRIMARY_FAILURE_COMMAND="$BASH_COMMAND"
  PRIMARY_FAILURE_LINE="${BASH_LINENO[0]:-unknown}"
}

write_result_evidence() {
  local primary_status="$1"
  python3 -S - "$RESULT_EVIDENCE" "$primary_status" "$CURRENT_PHASE" \
    "$PRIMARY_FAILURE_COMMAND" "$PRIMARY_FAILURE_LINE" "$SOURCE_HEAD" \
    "$VALIDATED_REQUEST" "$ASSET_EVIDENCE" "$CONFIG_METADATA" \
    "$RUNTIME_INFO" "$COMMAND_EVIDENCE" "$SANDBOX_RUN_DIR/logs/stderr.log" \
    "${SLURM_JOB_ID:-unknown}" "${SLURMD_NODENAME:-${HOSTNAME:-unknown}}" <<'PY'
import json
import sys
from pathlib import Path

(
    output_path,
    status_text,
    phase,
    failed_command,
    failed_line,
    source_head,
    request_path,
    asset_path,
    config_path,
    runtime_path,
    command_path,
    stderr_path,
    job_id,
    node,
) = sys.argv[1:]


def load_mapping(path_text):
    """读取已存在的映射证据,失败时返回空映射。"""
    path = Path(path_text)
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def load_command(path_text):
    """读取精确 argv 证据,失败时返回空列表。"""
    value = load_mapping(path_text).get("argv", [])
    return value if isinstance(value, list) else []


request = load_mapping(request_path)
assets = load_mapping(asset_path)
config = load_mapping(config_path)
runtime = load_mapping(runtime_path)
stderr_line = None
stderr = Path(stderr_path)
if stderr.is_file():
    try:
        stderr_line = next(
            (line.strip()[:2000] for line in stderr.read_text(encoding="utf-8").splitlines() if line.strip()),
            None,
        )
    except OSError:
        stderr_line = None
status = int(status_text)
payload = {
    "schema_version": "autovla.m9_a100_runtime_evidence.v1",
    "status": "bounded_success" if status == 0 else "failed",
    "phase": phase,
    "source_head": source_head,
    "candidate_digest": request.get("candidate_digest"),
    "config_fingerprint": config.get("config_fingerprint"),
    "fixture": {
        "identity": request.get("fixture_identity"),
        "root": request.get("fixture_root"),
        "sample_count": request.get("fixture_sample_count"),
    },
    "asset_bundle": assets,
    "runtime": runtime,
    "command": load_command(command_path),
    "slurm": {"job_id": job_id, "node": node},
    "offline": True,
    "exit_code": status,
    "first_causal_failure": (
        None
        if status == 0
        else {
            "phase": phase,
            "command": failed_command or None,
            "line": failed_line or None,
            "stderr": stderr_line,
        }
    ),
}
target = Path(output_path)
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

record_result() {
  local primary_status="$?"
  trap - ERR EXIT
  set +e
  write_result_evidence "$primary_status"
  exit "$primary_status"
}

trap capture_primary_failure ERR
trap record_result EXIT

CURRENT_PHASE="validate_runtime_request"
python3 -S - "$SANDBOX_RUNTIME_REQUEST" "$SANDBOX_PROJECT_ROOT" \
  "$VALIDATED_REQUEST" "$TASK_ID" "$REQUEST_SCHEMA" <<'PY'
import json
import re
import sys
from pathlib import Path

request_path, project_root, output_path, task_id, expected_schema = sys.argv[1:]
root = Path(project_root).resolve(strict=True)
request_file = Path(request_path).resolve(strict=True)
try:
    request_file.relative_to(root / "runs")
except ValueError as exc:
    raise SystemExit("runtime request must resolve below current worktree runs/") from exc
try:
    request = json.loads(request_file.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"runtime request is not valid JSON: {exc}") from exc
required = {
    "schema_version",
    "candidate_digest",
    "fixture_root",
    "fixture_identity",
    "fixture_sample_count",
    "model_profile",
    "max_steps",
    "embodiment",
    "base_asset_spec_identity",
    "base_asset_revision",
    "eagle_asset_spec_identity",
    "eagle_asset_revision",
}
if not isinstance(request, dict) or set(request) != required:
    actual = set(request) if isinstance(request, dict) else set()
    raise SystemExit(
        f"runtime request keys mismatch; missing={sorted(required - actual)}; "
        f"unknown={sorted(actual - required)}"
    )
if request["schema_version"] != expected_schema:
    raise SystemExit("runtime request schema_version mismatch")
if not isinstance(request["candidate_digest"], str) or re.fullmatch(
    r"[0-9a-f]{64}", request["candidate_digest"]
) is None:
    raise SystemExit("candidate_digest must be exactly 64 lowercase hex characters")
if request["model_profile"] != "model-gr00t-n1d6":
    raise SystemExit("model_profile must be exactly model-gr00t-n1d6")
if type(request["max_steps"]) is not int or request["max_steps"] != 1:
    raise SystemExit("max_steps must be exactly integer 1")
if type(request["fixture_sample_count"]) is not int or request["fixture_sample_count"] <= 0:
    raise SystemExit("fixture_sample_count must be a positive integer")
for field in ("fixture_identity", "embodiment"):
    value = request[field]
    if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
        raise SystemExit(f"{field} must be a non-empty string without control characters")
expected_assets = {
    "base_asset_spec_identity": "a44b62e1217f603cbf5fc423c7f1b5c204e569ed97670cfb12736b166e9940ed",
    "base_asset_revision": "d0814e7ecb19202e7c8468b46098b0b7ef3a6d61",
    "eagle_asset_spec_identity": "cefdb0e85a6745990862fa1a8d1698d273582bfaae389651dc3e503434261496",
    "eagle_asset_revision": "5dc80c4afd726b34faad1d8f7e007a13b34e4c88",
}
for field, expected in expected_assets.items():
    if request[field] != expected:
        raise SystemExit(f"runtime request {field} does not match the pinned local specification")
fixture = Path(request["fixture_root"]).expanduser().resolve(strict=True)
if not fixture.is_dir():
    raise SystemExit("fixture_root must resolve to an existing directory")
allowed_roots = (
    root / "runs" / "tmp" / task_id,
    root / "datasets" / "working",
)
if not any(fixture == allowed or allowed in fixture.parents for allowed in allowed_roots):
    raise SystemExit(
        "fixture_root must resolve below the current worktree task runs/tmp root "
        "or datasets/working"
    )
request["fixture_root"] = str(fixture)
Path(output_path).write_text(
    json.dumps(request, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

CURRENT_PHASE="validate_wrapper_contract"
PROJECT_ROOT_REAL="$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$SANDBOX_PROJECT_ROOT")"
EXPECTED_CONFIG="$PROJECT_ROOT_REAL/configs/slurm/m9_a100_single_gpu.json"
EXPECTED_EXPERIMENT="$PROJECT_ROOT_REAL/configs/experiments/gr00t_n1d6_webdataset.yaml"
[[ "$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$SANDBOX_CONFIG")" == "$EXPECTED_CONFIG" ]] || {
  echo "M9 smoke requires configs/slurm/m9_a100_single_gpu.json" >&2
  exit 2
}
[[ "$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$SANDBOX_EXPERIMENT_CONFIG")" == "$EXPECTED_EXPERIMENT" ]] || {
  echo "M9 smoke requires tracked configs/experiments/gr00t_n1d6_webdataset.yaml" >&2
  exit 2
}
git ls-files --error-unmatch -- configs/experiments/gr00t_n1d6_webdataset.yaml >/dev/null
[[ "${SLURM_JOB_NUM_NODES:-}" == "1" && "${SLURM_NTASKS:-}" == "1" ]] || {
  echo "M9 smoke requires exactly one Slurm node and one task" >&2
  exit 2
}
SOURCE_HEAD="$(git rev-parse HEAD)"

CURRENT_PHASE="prepare_offline_environment"
umask 077
export HOME="$SANDBOX_RUN_DIR/home"
export TMPDIR="$SANDBOX_RUN_DIR/tmp"
export XDG_CACHE_HOME="$SANDBOX_RUN_DIR/home/.cache"
export HF_HOME="$SANDBOX_RUN_DIR/home/huggingface"
export HUGGINGFACE_HUB_CACHE="$HF_HOME/hub"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"
export HF_DATASETS_CACHE="$HF_HOME/datasets"
export WANDB_DIR="$SANDBOX_RUN_DIR/outputs/wandb-disabled"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export WANDB_MODE=disabled
export WANDB_DISABLED=true
export TOKENIZERS_PARALLELISM=false
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy NO_PROXY no_proxy

case "$PROFILE_INTERPRETER" in
  "$PROJECT_ROOT_REAL"/envs/model-gr00t-n1d6/.venv/bin/python) ;;
  *) echo "runtime interpreter escaped the required project profile" >&2; exit 2 ;;
esac
[[ -x "$PROFILE_INTERPRETER" ]] || {
  echo "required runtime interpreter is unavailable: $PROFILE_INTERPRETER; no fallback is allowed" >&2
  exit 127
}

CURRENT_PHASE="verify_local_asset_bundle"
"$PROFILE_INTERPRETER" - "$ASSET_ROOT" "$VALIDATED_REQUEST" "$ASSET_EVIDENCE" <<'PY'
import json
import sys
from pathlib import Path

from autovla.assets import Gr00tModelAssetBundle, ModelAssetStore
from autovla.assets.registry import GR00T_N1D6_ASSET_SPEC, GR00T_N1D6_EAGLE_SUPPORT_SPEC

asset_root, request_path, output_path = sys.argv[1:]
request = json.loads(Path(request_path).read_text(encoding="utf-8"))
bundle = Gr00tModelAssetBundle.resolve(ModelAssetStore(Path(asset_root)))
expected = {
    "base_asset_spec_identity": GR00T_N1D6_ASSET_SPEC.identity,
    "base_asset_revision": GR00T_N1D6_ASSET_SPEC.revision,
    "eagle_asset_spec_identity": GR00T_N1D6_EAGLE_SUPPORT_SPEC.identity,
    "eagle_asset_revision": GR00T_N1D6_EAGLE_SUPPORT_SPEC.revision,
}
for field, value in expected.items():
    if request[field] != value:
        raise SystemExit(f"validated runtime request mismatch for {field}")
payload = {
    "verified": True,
    "bundle_fingerprint": bundle.fingerprint,
    "base_checkpoint": {
        "key": bundle.base_checkpoint.manifest.key,
        "root": str(bundle.base_checkpoint.root),
        "spec_identity": bundle.base_checkpoint.identity,
        "revision": bundle.base_checkpoint.manifest.revision,
    },
    "eagle_support": {
        "key": bundle.eagle_support.manifest.key,
        "root": str(bundle.eagle_support.root),
        "eagle_root": str(bundle.eagle_root),
        "spec_identity": bundle.eagle_support.identity,
        "revision": bundle.eagle_support.manifest.revision,
    },
}
Path(output_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

CURRENT_PHASE="materialize_resolved_config"
"$PROFILE_INTERPRETER" - "$SANDBOX_EXPERIMENT_CONFIG" "$VALIDATED_REQUEST" \
  "$ASSET_EVIDENCE" "$RESOLVED_CONFIG" "$CONFIG_METADATA" \
  "$OVERRIDES_EVIDENCE" "$SANDBOX_RUN_ID" <<'PY'
import json
import sys
from pathlib import Path

from autovla.config import load_yaml, to_resolved_dict

(
    experiment_path,
    request_path,
    asset_path,
    resolved_path,
    metadata_path,
    overrides_path,
    run_id,
) = sys.argv[1:]
request = json.loads(Path(request_path).read_text(encoding="utf-8"))
assets = json.loads(Path(asset_path).read_text(encoding="utf-8"))
if assets.get("verified") is not True:
    raise SystemExit("complete local asset bundle verification is required")
camera_keys = ["camera.rgb_0", "camera.rgb_1", "camera.rgb_2"]
dataset = {
    "name": "m9-runtime-fixture",
    "backend": "webdataset",
    "root": request["fixture_root"],
    "split": "train",
    "weight": 1.0,
    "embodiment": request["embodiment"],
    "sample_count": request["fixture_sample_count"],
    "image_keys": camera_keys,
    "language_key": "language",
    "state_key": "state",
    "action_key": "action",
    "action_mask_key": "action_mask",
    "access_mode": "streaming",
    "stream_mode": "finite_epoch",
    "nominal_epoch_size": request["fixture_sample_count"],
    "temporal_query": None,
}
run_root = f"runs/slurm/{run_id}/outputs"


def encoded(value):
    """把动态值编码成严格 dotted override 标量。"""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


overrides = [
    "run.name=m9_a100_architecture_smoke",
    f"run.output_dir={encoded(run_root + '/training')}",
    "run.intent=training",
    "model.asset_key=gr00t_n1d6",
    f"model.eagle_asset_path={encoded(assets['eagle_support']['eagle_root'])}",
    "data.name=m9-a100-webdataset-fixture",
    "data.backend=null",
    f"data.root={encoded(request['fixture_root'])}",
    f"data.required_modalities={encoded(camera_keys)}",
    f"data.datasets={encoded([dataset])}",
    "data.loader.batch_size=1",
    "data.loader.num_workers=0",
    "topology.distributed.strategy_key=single_gpu",
    "topology.distributed.world_size=1",
    "topology.distributed.device=cuda",
    "topology.precision.mode=bfloat16",
    "training.max_steps=1",
    f"checkpoint.directory={encoded(run_root + '/checkpoints')}",
    "checkpoint.save_every_steps=null",
    "checkpoint.save_final=false",
    "checkpoint.save_optimizer=true",
    f"telemetry.logging.jsonl_path={encoded(run_root + '/metrics.jsonl')}",
    "telemetry.remote_logging=false",
]
config = load_yaml(experiment_path, overrides=tuple(overrides))
resolved = to_resolved_dict(config)
if "distributed" in resolved["training"]:
    raise SystemExit("resolved config contains obsolete training.distributed duplicate")
if len(config.data.datasets) != 1 or config.data.datasets[0].backend != "webdataset":
    raise SystemExit("resolved config must contain exactly one WebDataset source")
if config.data.backend is not None:
    raise SystemExit("resolved config must clear the data.backend compatibility field")
if config.topology.distributed.strategy_key != "single_gpu":
    raise SystemExit("resolved config strategy must be single_gpu")
if config.topology.distributed.world_size != 1 or config.training.max_steps != 1:
    raise SystemExit("resolved config must remain world_size=1 and max_steps=1")
if config.checkpoint.save_final or config.checkpoint.save_every_steps is not None:
    raise SystemExit("resolved config must disable final and periodic checkpoints")
if not config.checkpoint.save_optimizer:
    raise SystemExit("resolved production config must retain save_optimizer=true")
Path(resolved_path).write_text(
    json.dumps(resolved, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
Path(metadata_path).write_text(
    json.dumps(
        {
            "base_experiment": str(Path(experiment_path).resolve()),
            "candidate_digest": request["candidate_digest"],
            "config_fingerprint": config.fingerprint,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
Path(overrides_path).write_text(
    json.dumps({"overrides": overrides}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

CURRENT_PHASE="probe_single_a100_runtime"
"$PROFILE_INTERPRETER" - "$RUNTIME_INFO" <<'PY'
import importlib.metadata
import json
import sys
from pathlib import Path

import torch

if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable for the bounded M9 smoke")
if torch.cuda.device_count() != 1:
    raise SystemExit("bounded M9 smoke requires exactly one visible CUDA device")
device_name = torch.cuda.get_device_name(0)
if "A100" not in device_name.upper():
    raise SystemExit(f"bounded M9 smoke requires an A100, got {device_name!r}")
packages = {}
for distribution in (
    "autovla",
    "torch",
    "transformers",
    "datasets",
    "webdataset",
    "safetensors",
    "huggingface-hub",
):
    try:
        packages[distribution] = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        packages[distribution] = "not-installed"
payload = {
    "python": sys.version,
    "packages": packages,
    "cuda_runtime": torch.version.cuda,
    "cuda_available": True,
    "visible_device_count": 1,
    "device_name": device_name,
    "device_capability": list(torch.cuda.get_device_capability(0)),
}
Path(sys.argv[1]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

TRAIN_COMMAND=("$PROFILE_INTERPRETER" -m autovla.cli.train "$RESOLVED_CONFIG")
python3 -S - "$COMMAND_EVIDENCE" "${TRAIN_COMMAND[@]}" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    json.dumps({"argv": sys.argv[2:]}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
python3 -S - "$LAUNCH_EVIDENCE" "$SOURCE_HEAD" "$VALIDATED_REQUEST" \
  "$CONFIG_METADATA" "$ASSET_EVIDENCE" "$RUNTIME_INFO" "$COMMAND_EVIDENCE" <<'PY'
import json
import sys
from pathlib import Path

output, source_head, request_path, config_path, asset_path, runtime_path, command_path = sys.argv[1:]


def load(path):
    """读取已校验的单个 JSON 证据。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


request = load(request_path)
config = load(config_path)
payload = {
    "schema_version": "autovla.m9_a100_runtime_evidence.v1",
    "phase": "launch",
    "source_head": source_head,
    "candidate_digest": request["candidate_digest"],
    "config_fingerprint": config["config_fingerprint"],
    "fixture_identity": request["fixture_identity"],
    "asset_bundle": load(asset_path),
    "runtime": load(runtime_path),
    "command": load(command_path)["argv"],
    "offline": True,
}
Path(output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

CURRENT_PHASE="production_train_one_step"
"${TRAIN_COMMAND[@]}"
CURRENT_PHASE="bounded_success"
