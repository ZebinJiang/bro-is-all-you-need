"""M6 本地运行请求、输入校验和命令渲染的历史实现。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import yaml

TASK_ID = "AUTOVLA-M6-PRODUCTION-DATA-PLANE-GR00T-RUNTIME-BRINGUP-001"
TARGETS = {
    "cpu": ("single_device", 1, "cpu"),
    "gpu": ("single_device", 1, "cuda"),
    "ddp": ("distributed_data_parallel", 2, "cuda"),
    "fsdp2": ("fully_sharded_data_parallel", 2, "cuda"),
}
OFFLINE_ENV = {
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "WANDB_MODE": "disabled",
}
REDUCED_STATUS_TOKENS = (
    "NO_BACKEND_WINNER",
    "OFFICIAL_GR00T_CHECKPOINT_VALIDATION_DEFERRED_LOCAL_ASSET_ABSENT",
    "OFFICIAL_ASSET_PARITY_NOT_RUN_LOCAL_ASSET_ABSENT",
)
REQUIRED_EAGLE_MEMBERS = (
    "chat_template.json",
    "config.json",
    "merges.txt",
    "preprocessor_config.json",
    "processor_config.json",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "vocab.json",
)
REQUEST_KEYS = frozenset(
    {
        "asset_root",
        "config_path",
        "data_root",
        "evidence_json",
        "local_only",
        "max_steps",
        "offline",
        "output_dir",
        "runtime_python",
        "schema_version",
        "target",
        "task_id",
    }
)


def project_root() -> Path:
    """返回脚本所属 AutoVLA checkout 根。"""
    return Path(__file__).resolve().parents[2]


def _mapping(path: Path) -> dict[str, Any]:
    """读取 JSON 或 YAML object 并拒绝非映射顶层。"""
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError(f"runtime document must be a mapping: {path}")
    return cast(dict[str, Any], payload)


def _absolute_existing(path_text: object, field: str, *, directory: bool = False) -> Path:
    """要求请求路径为已存在绝对本地路径。"""
    if not isinstance(path_text, str) or not path_text:
        raise ValueError(f"{field} must be a non-empty absolute path")
    path = Path(path_text)
    if not path.is_absolute():
        raise ValueError(f"{field} must be an absolute path: {path}")
    resolved = path.resolve(strict=True)
    if directory and not resolved.is_dir():
        raise ValueError(f"{field} must be a directory: {resolved}")
    if not directory and not resolved.is_file():
        raise ValueError(f"{field} must be a file: {resolved}")
    return resolved


def _governed_output(path_text: object, field: str) -> Path:
    """要求输出目录已生成且位于当前 checkout 的 runs 根。"""
    path = _absolute_existing(path_text, field, directory=True)
    runs_root = (project_root() / "runs").resolve()
    if path != runs_root and runs_root not in path.parents:
        raise ValueError(f"{field} must remain under project runs/: {path}")
    return path


def load_runtime_request(path: str | Path) -> dict[str, Any]:
    """读取并严格校验生成的 M6 运行请求。"""
    request_path = Path(path).expanduser().resolve(strict=True)
    request = _mapping(request_path)
    if set(request) != REQUEST_KEYS:
        missing = sorted(REQUEST_KEYS - set(request))
        unknown = sorted(set(request) - REQUEST_KEYS)
        raise ValueError(f"runtime request keys mismatch; missing={missing}; unknown={unknown}")
    if request["schema_version"] != 1 or request["task_id"] != TASK_ID:
        raise ValueError("runtime request schema/task identity mismatch")
    target = request["target"]
    if target not in TARGETS:
        raise ValueError(f"runtime request target must be one of: {tuple(TARGETS)}")
    if request["local_only"] is not True or request["offline"] is not True:
        raise ValueError("runtime request must remain local_only=true and offline=true")
    if request["max_steps"] != 2:
        raise ValueError("runtime request max_steps must be exactly 2")
    runtime_value = request["runtime_python"]
    if not isinstance(runtime_value, str) or not runtime_value:
        raise ValueError("runtime_python must be a non-empty absolute path")
    runtime_python = Path(runtime_value).expanduser()
    if not runtime_python.is_absolute() or not runtime_python.is_file():
        raise ValueError("runtime_python must be an existing absolute file")
    if runtime_python.stat().st_mode & 0o111 == 0:
        raise ValueError("runtime_python must be executable")
    return request


def validate_runtime_request(
    request: dict[str, Any],
    *,
    output_dir: str | Path | None = None,
    evidence_json: str | Path | None = None,
) -> dict[str, Path]:
    """在执行前验证配置、资产、数据和所有输出边界。"""
    config_path = _absolute_existing(request["config_path"], "config_path")
    asset_root = _absolute_existing(request["asset_root"], "asset_root", directory=True)
    data_root = _absolute_existing(request["data_root"], "data_root", directory=True)
    missing = tuple(name for name in REQUIRED_EAGLE_MEMBERS if not (asset_root / name).is_file())
    if missing:
        raise ValueError(f"generated Eagle asset tree is incomplete: {missing}")
    if not (data_root / "sample_index.jsonl").is_file():
        raise ValueError("RoboDM validation data requires sample_index.jsonl")
    _governed_output(request["output_dir"], "request.output_dir")
    selected_output = request["output_dir"] if output_dir is None else str(output_dir)
    output_path = _governed_output(selected_output, "output_dir")
    selected_evidence = request["evidence_json"] if evidence_json is None else str(evidence_json)
    evidence_path = Path(cast(str, selected_evidence)).expanduser()
    if not evidence_path.is_absolute():
        raise ValueError("evidence_json must be an absolute path")
    evidence_parent = evidence_path.parent.resolve(strict=True)
    runs_root = (project_root() / "runs").resolve()
    if evidence_parent != runs_root and runs_root not in evidence_parent.parents:
        raise ValueError("evidence_json must remain under project runs/")

    config = _mapping(config_path)
    if "__AUTOVLA_" in config_path.read_text(encoding="utf-8"):
        raise ValueError("runtime config contains unresolved template placeholders")
    model = config.get("model")
    if not isinstance(model, dict):
        raise ValueError("runtime config model must be a mapping")
    if model.get("architecture_variant") != "reduced_runtime":
        raise ValueError("M6 generated runtime config must select reduced_runtime")
    if model.get("checkpoint_path") is not None:
        raise ValueError("reduced_runtime must use random initialization without checkpoint_path")
    if model.get("eagle_asset_path") != str(asset_root):
        raise ValueError("runtime config eagle_asset_path differs from generated request")
    if model.get("local_files_only") is not True:
        raise ValueError("runtime config must keep model.local_files_only=true")
    data = config.get("data")
    if not isinstance(data, dict) or data.get("root") != str(data_root):
        raise ValueError("runtime config data.root differs from generated request")
    datasets = data.get("datasets")
    if (
        not isinstance(datasets, list)
        or len(datasets) != 1
        or not isinstance(datasets[0], dict)
        or datasets[0].get("root") != str(data_root)
    ):
        raise ValueError("runtime config requires one generated local dataset root")
    training = config.get("training")
    if not isinstance(training, dict) or training.get("max_steps") != 2:
        raise ValueError("runtime config training.max_steps must be exactly 2")
    checkpoint = training.get("checkpoint")
    if not isinstance(checkpoint, dict):
        raise ValueError("runtime config training.checkpoint must be a mapping")
    _governed_output(checkpoint.get("directory"), "config checkpoint directory")
    return {
        "asset_root": asset_root,
        "config_path": config_path,
        "data_root": data_root,
        "evidence_json": evidence_path,
        "output_dir": output_path,
    }


def render_runtime_command(
    request: dict[str, Any],
    paths: dict[str, Path],
) -> tuple[str, ...]:
    """返回显式 CPU/CUDA 策略和最多两步的 argv。"""
    target = cast(str, request["target"])
    strategy, world_size, device = TARGETS[target]
    runtime_python = str(Path(cast(str, request["runtime_python"])).expanduser().absolute())
    training_args = (
        str(paths["config_path"]),
        "--set",
        "training.max_steps=2",
        "--set",
        f"training.distributed.strategy_key={strategy}",
        "--set",
        f"training.distributed.world_size={world_size}",
        "--set",
        f"training.distributed.device={device}",
        "--set",
        f"training.checkpoint.directory={paths['output_dir']}",
        "--set",
        f"training.logging.jsonl_path={paths['evidence_json'].with_suffix('.metrics.jsonl')}",
    )
    if world_size == 2:
        torchrun = str(Path(runtime_python).parent / "torchrun")
        return (
            torchrun,
            "--standalone",
            "--nproc-per-node",
            "2",
            "--module",
            "autovla.cli.train",
            *training_args,
        )
    return (runtime_python, "-m", "autovla.cli.train", *training_args)


__all__ = [
    "OFFLINE_ENV",
    "REDUCED_STATUS_TOKENS",
    "REQUIRED_EAGLE_MEMBERS",
    "TARGETS",
    "TASK_ID",
    "load_runtime_request",
    "project_root",
    "render_runtime_command",
    "validate_runtime_request",
]
