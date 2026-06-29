"""M3 runner readiness manifest。"""

from __future__ import annotations

import json
import math
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from autovla.training.checkpoint import read_checkpoint_manifest
from autovla.training.cli_execution import LocalSmokeExecutionResult, run_local_smoke
from autovla.training.config import LocalRunnerDryRunConfig

READINESS_MODE = "readiness"
READINESS_MANIFEST_SCHEMA_VERSION = "m3-runner-readiness.v1"
READINESS_MANIFEST_FILENAME = "readiness_manifest.json"
_OLD_NAMESPACE = "genesis" + "vla"
_EXTERNAL_EFFECTS_FALSE = {
    "checkpoint_weight_load": False,
    "endpoint": False,
    "external_dataset": False,
    "gpu": False,
    "hf": False,
    "network": False,
    "real_model": False,
    "real_training": False,
    "robot": False,
    "slurm": False,
    "wandb": False,
}


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """记录 readiness 命令的可验证输出。"""

    readiness_manifest_path: Path
    execution_manifest_path: Path
    checkpoint_manifest_path: Path
    resumed_step: int
    metrics: Mapping[str, Mapping[str, float]]


def _repo_root() -> Path:
    """返回当前 AutoVLA 源码所在仓库根目录。"""
    return Path(__file__).resolve().parents[2]


def _stable_metrics(metrics: Mapping[str, float]) -> dict[str, float]:
    """返回按 key 稳定排序的有限 float 指标。"""
    output: dict[str, float] = {}
    for key in sorted(metrics):
        value = metrics[key]
        if isinstance(value, bool):
            raise TypeError(f"metric {key} must be numeric")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"metric {key} must be finite")
        output[str(key)] = number
    return output


def _relative_to_output(config: LocalRunnerDryRunConfig, path: Path) -> str:
    """把输出路径转换为相对 output_dir 的稳定路径。"""
    try:
        return path.resolve().relative_to(config.output_dir.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("readiness output must stay under output_dir") from exc


def _validate_output_dir(output_dir: Path) -> None:
    """确保 output_dir 可作为目录使用, 避免局部写出。"""
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("output_dir must be a directory or not exist")


def _tracked_old_namespace_paths(root: Path) -> tuple[str, ...]:
    """检查仓库是否追踪旧命名空间路径。"""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", f"{_OLD_NAMESPACE}/**"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError("failed to inspect tracked namespace residue")
    return tuple(line for line in result.stdout.splitlines() if line)


def _active_old_namespace_mentions(root: Path) -> tuple[str, ...]:
    """扫描 autovla 源码中是否存在旧命名空间兼容痕迹。"""
    package_root = root / "autovla"
    mentions: list[str] = []
    for path in sorted(package_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if _OLD_NAMESPACE in text:
            mentions.append(path.relative_to(root).as_posix())
    return tuple(mentions)


def _validate_namespace_boundary() -> None:
    """确认 readiness 只从 autovla 命名空间运行。"""
    if __name__.split(".", 1)[0] != "autovla":
        raise RuntimeError("package namespace must be autovla")
    root = _repo_root()
    tracked = _tracked_old_namespace_paths(root)
    if tracked:
        raise RuntimeError(f"tracked old namespace residue detected: {tracked[0]}")
    mentions = _active_old_namespace_mentions(root)
    if mentions:
        raise RuntimeError(f"compatibility shim residue detected: {mentions[0]}")


def _fixture_summary(sample_source: tuple[Mapping[str, object], ...]) -> dict[str, object]:
    """从 checkpoint sample_source 构造小型 fixture 摘要。"""
    datasets = {str(item.get("dataset", "unknown")) for item in sample_source}
    dataset = next(iter(datasets)) if len(datasets) == 1 else "mixed"
    return {
        "batch_size": len(sample_source),
        "dataset": dataset,
        "sample_count": len(sample_source),
    }


def _validate_external_effects(manifest: Mapping[str, object]) -> None:
    """确认 readiness manifest 不声明外部效果。"""
    effects = manifest.get("external_effects")
    if effects != _EXTERNAL_EFFECTS_FALSE:
        raise RuntimeError("readiness external effects must all be false")


def build_readiness_manifest(
    config: LocalRunnerDryRunConfig,
    result: LocalSmokeExecutionResult,
) -> dict[str, object]:
    """构造 deterministic runner readiness manifest。"""
    checkpoint = read_checkpoint_manifest(result.checkpoint_manifest_path)
    train_metrics = _stable_metrics(result.train_metrics)
    eval_metrics = _stable_metrics(result.eval_metrics)
    manifest: dict[str, object] = {
        "action_dim": config.action_dim,
        "action_horizon": config.action_horizon,
        "checkpoint_manifest_path": _relative_to_output(
            config,
            result.checkpoint_manifest_path,
        ),
        "cli_module": "autovla.training.cli",
        "compatibility_shim_present": False,
        "dataset_fingerprint": config.dataset_fingerprint,
        "execution_manifest_path": _relative_to_output(
            config,
            result.execution_manifest_path,
        ),
        "external_effects": dict(_EXTERNAL_EFFECTS_FALSE),
        "fixture_summary": _fixture_summary(checkpoint.sample_source),
        "metrics": {
            "eval": eval_metrics,
            "train": train_metrics,
        },
        "mode": READINESS_MODE,
        "model_registry_key": config.model_registry_key,
        "package_name": "autovla",
        "readiness": True,
        "run_id": config.run_id,
        "runner_state": {
            "epoch": checkpoint.epoch,
            "setup_complete": True,
            "step": result.resumed_step,
        },
        "schema_version": READINESS_MANIFEST_SCHEMA_VERSION,
        "seed": config.seed,
        "statistics_fingerprint": config.statistics_fingerprint,
        "transform_fingerprint": config.transform_fingerprint,
    }
    _validate_external_effects(manifest)
    return manifest


def write_readiness_manifest(
    config: LocalRunnerDryRunConfig,
    result: LocalSmokeExecutionResult,
) -> Path:
    """写入稳定排序的 readiness manifest 并校验 roundtrip。"""
    output_path = config.output_dir / config.run_id / READINESS_MANIFEST_FILENAME
    manifest = build_readiness_manifest(config, result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    expected_text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output_path.write_text(expected_text, encoding="utf-8")
    loaded: object = json.loads(output_path.read_text(encoding="utf-8"))
    if loaded != manifest:
        raise RuntimeError("readiness manifest roundtrip failed")
    return output_path


def run_readiness(config: LocalRunnerDryRunConfig) -> ReadinessResult:
    """执行 CPU-only readiness smoke 并写出 readiness manifest。"""
    _validate_output_dir(config.output_dir)
    _validate_namespace_boundary()
    local_smoke = run_local_smoke(config)
    manifest_path = write_readiness_manifest(config, local_smoke)
    return ReadinessResult(
        readiness_manifest_path=manifest_path,
        execution_manifest_path=local_smoke.execution_manifest_path,
        checkpoint_manifest_path=local_smoke.checkpoint_manifest_path,
        resumed_step=local_smoke.resumed_step,
        metrics={
            "eval": _stable_metrics(local_smoke.eval_metrics),
            "train": _stable_metrics(local_smoke.train_metrics),
        },
    )
