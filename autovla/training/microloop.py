"""M3 CPU-only compute microloop 执行层。"""

from __future__ import annotations

import json
import math
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import numpy as np

from autovla.core.types import (
    ActionMask,
    FrameworkOutput,
    ImageLike,
    ModelInput,
    NumericArray,
    RawSample,
)
from autovla.dataloader import CollatedBatch, collate_raw_samples_typed
from autovla.training.checkpoint import read_checkpoint_manifest
from autovla.training.config import LocalRunnerDryRunConfig
from autovla.training.local_runner import LocalRunner
from autovla.training.losses import validate_action_mask
from autovla.training.testing import DeterministicActionFramework

MICROLOOP_MODE = "microloop"
MICROLOOP_MANIFEST_SCHEMA_VERSION = "m3-cpu-compute-microloop.v1"
MICROLOOP_MANIFEST_FILENAME = "microloop_manifest.json"
MICROLOOP_TASK_ID = "AUTOVLA-M3-CPU-COMPUTE-MICROLOOP-001"
_OLD_NAMESPACE = "genesis" + "vla"
_DEFAULT_MASK = object()
_EXTERNAL_EFFECTS_FALSE = {
    "checkpoint_weight_load": False,
    "checkpoint_weight_write": False,
    "cuda": False,
    "endpoint": False,
    "external_dataset": False,
    "gpu": False,
    "hf": False,
    "network": False,
    "real_model": False,
    "real_training": False,
    "robot": False,
    "slurm_submission": False,
    "tokenizer": False,
    "wandb": False,
}


class _MicroloopFramework(Protocol):
    """microloop 只需要框架提供单步 forward。"""

    def forward(self, batch: ModelInput) -> FrameworkOutput:
        """执行一次确定性前向。"""
        ...


@dataclass(frozen=True, slots=True)
class MicroloopResult:
    """记录一次 CPU compute microloop 的输出。"""

    microloop_manifest_path: Path
    checkpoint_manifest_path: Path
    resumed_step: int
    train_metrics: Mapping[str, float]
    eval_metrics: Mapping[str, float]


def _repo_root() -> Path:
    """返回当前 AutoVLA 源码所在仓库根目录。"""
    return Path(__file__).resolve().parents[2]


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
    """确认 microloop 只从 autovla 命名空间运行。"""
    if __name__.split(".", 1)[0] != "autovla":
        raise RuntimeError("package namespace must be autovla")
    root = _repo_root()
    tracked = _tracked_old_namespace_paths(root)
    if tracked:
        raise RuntimeError(f"tracked old namespace residue detected: {tracked[0]}")
    mentions = _active_old_namespace_mentions(root)
    if mentions:
        raise RuntimeError(f"compatibility shim residue detected: {mentions[0]}")


def _sample_actions(config: LocalRunnerDryRunConfig, *, sample_index: int) -> NumericArray:
    """构造小型 deterministic action 目标。"""
    values = np.arange(config.action_horizon * config.action_dim, dtype=np.float32)
    actions = values.reshape(config.action_horizon, config.action_dim) + float(sample_index)
    return cast(NumericArray, actions)


def _sample_mask(config: LocalRunnerDryRunConfig, *, sample_index: int) -> ActionMask:
    """构造严格 bool action mask。"""
    mask = np.ones((config.action_horizon, config.action_dim), dtype=np.bool_)
    if config.action_horizon * config.action_dim > 1 and sample_index == 1:
        mask[-1, -1] = False
    return cast(ActionMask, mask)


def _sample_image(*, sample_index: int) -> ImageLike:
    """构造不依赖真实数据集的小型图像张量。"""
    image = np.arange(12, dtype=np.float32).reshape(2, 2, 3)
    return cast(ImageLike, image + float(sample_index))


def build_microloop_batch(
    config: LocalRunnerDryRunConfig,
    *,
    action_mask: object = _DEFAULT_MASK,
) -> CollatedBatch:
    """用公开 M2 contracts 构造纯内存 microloop batch。"""
    samples: list[RawSample] = []
    for index in range(2):
        mask = _sample_mask(config, sample_index=index)
        samples.append(
            RawSample(
                images={"rgb": _sample_image(sample_index=index)},
                language=f"cpu microloop instruction {index}",
                actions=_sample_actions(config, sample_index=index),
                state=cast(
                    NumericArray,
                    np.asarray([float(config.seed), float(index)], dtype=np.float32),
                ),
                robot_tag="cpu-microloop-test-double",
                metadata={
                    "action_mask": mask,
                    "sample_source": {
                        "dataset": "in-memory-cpu-microloop",
                        "sample_index": index,
                        "sample_key": f"cpu-microloop-{index}",
                    },
                },
            )
        )
    batch = collate_raw_samples_typed(samples)
    if action_mask is _DEFAULT_MASK:
        return batch
    # 仅用于 microloop 负向测试注入, 不改变 M2 CollatedBatch 构造契约。
    object.__setattr__(batch, "action_mask", action_mask)
    return batch


def _stable_metrics(metrics: Mapping[str, float]) -> dict[str, float]:
    """返回按 key 稳定排序的有限 float 指标。"""
    output: dict[str, float] = {}
    for key in sorted(metrics):
        raw_value = metrics[key]
        if isinstance(raw_value, bool):
            raise TypeError(f"metric {key} must be numeric")
        value = float(raw_value)
        if not math.isfinite(value):
            raise ValueError(f"metric {key} must be finite")
        output[str(key)] = value
    return output


def _validate_output_dir(output_dir: Path) -> None:
    """确保 output_dir 可作为目录使用, 避免局部写出。"""
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("output_dir must be a directory or not exist")


def _relative_to_run_dir(config: LocalRunnerDryRunConfig, path: Path) -> str:
    """把输出路径转换为相对 run_dir 的稳定路径。"""
    run_dir = config.output_dir / config.run_id
    try:
        return path.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("microloop output must stay under run_dir") from exc


def _validate_batch_boundary(batch: CollatedBatch) -> None:
    """在 runner 前显式确认 action mask 与 action 尺寸可用。"""
    if batch.actions is None:
        raise ValueError("microloop requires actions")
    if batch.action_mask is None:
        raise ValueError("microloop requires action_mask")
    validate_action_mask(batch.action_mask, batch.actions.shape)


def _validate_external_guards(*, require_compute_node: bool) -> None:
    """确认 microloop 没有被要求触碰外部资源。"""
    if os.environ.get("AUTOVLA_ATTEMPT_EXTERNAL_EFFECT"):
        raise RuntimeError("external effects are not allowed in microloop")
    if os.environ.get("AUTOVLA_ATTEMPT_GPU"):
        raise RuntimeError("gpu use is not allowed in microloop")
    visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if visible_devices not in {"", "-1"}:
        raise RuntimeError("gpu must not be visible for microloop")
    if require_compute_node and os.environ.get("AUTOVLA_COMPUTE_NODE_VALIDATION") != "1":
        raise RuntimeError("compute node validation requires an allocated compute node")


def _prevalidate_resume(config: LocalRunnerDryRunConfig, resume_from: Path | None) -> int | None:
    """在写出本次 run 之前校验外部 resume manifest。"""
    if resume_from is None:
        return None
    manifest = read_checkpoint_manifest(resume_from)
    return manifest.validate_resume(config.to_local_runner_config().resume_spec())


def _resume_validation(
    *,
    requested_step: int | None,
    checkpoint_manifest_path: Path,
    resumed_step: int,
    config: LocalRunnerDryRunConfig,
) -> dict[str, object]:
    """构造 resume 兼容性验证摘要。"""
    return {
        "checkpoint_manifest": _relative_to_run_dir(config, checkpoint_manifest_path),
        "compatible": True,
        "requested": requested_step is not None,
        "requested_step": requested_step,
        "resumed_step": resumed_step,
    }


def _fixture_summary(batch: CollatedBatch) -> dict[str, object]:
    """从纯内存 batch 构造 fixture 摘要。"""
    datasets = {str(item.get("dataset", "unknown")) for item in batch.sample_source}
    dataset = next(iter(datasets)) if len(datasets) == 1 else "mixed"
    return {
        "batch_size": batch.batch_size,
        "dataset": dataset,
        "sample_count": batch.batch_size,
    }


def _compute_execution_manifest(*, require_compute_node: bool) -> dict[str, object]:
    """描述 compute-node 后续验证约束, 不提交 Slurm 作业。"""
    return {
        "executed_on_compute_node": os.environ.get("AUTOVLA_COMPUTE_NODE_VALIDATION") == "1",
        "login_node_runtime_allowed": False,
        "mode": "slurm_cpu",
        "require_compute_node": require_compute_node,
        "slurm_cpu": {
            "autovla_expect_no_gpu": "1",
            "cluster": "cz_hpc01",
            "cpus": 16,
            "cuda_visible_devices": "",
            "memory": "64G",
            "partition": "a100",
            "time": "04:00:00",
        },
        "slurm_submission": False,
    }


def build_microloop_manifest(
    config: LocalRunnerDryRunConfig,
    *,
    batch: CollatedBatch,
    train_metrics: Mapping[str, float],
    eval_metrics: Mapping[str, float],
    checkpoint_manifest_path: Path,
    resumed_step: int,
    requested_step: int | None,
    require_compute_node: bool,
) -> dict[str, object]:
    """构造 deterministic CPU compute microloop manifest。"""
    train = _stable_metrics(train_metrics)
    evaluation = _stable_metrics(eval_metrics)
    manifest: dict[str, object] = {
        "action_dim": config.action_dim,
        "action_horizon": config.action_horizon,
        "checkpoint_manifest": _relative_to_run_dir(config, checkpoint_manifest_path),
        "compatibility_shim_present": False,
        "compute_execution": _compute_execution_manifest(
            require_compute_node=require_compute_node,
        ),
        "dataset_fingerprint": config.dataset_fingerprint,
        "determinism": {
            "no_generated_at": True,
            "stable_json_key_order": True,
            "stable_metrics": True,
        },
        "eval_metrics": evaluation,
        "external_effects": dict(_EXTERNAL_EFFECTS_FALSE),
        "fixture_summary": _fixture_summary(batch),
        "max_steps": config.max_steps,
        "mode": MICROLOOP_MODE,
        "model_registry_key": config.model_registry_key,
        "package_name": "autovla",
        "resume_validation": _resume_validation(
            requested_step=requested_step,
            checkpoint_manifest_path=checkpoint_manifest_path,
            resumed_step=resumed_step,
            config=config,
        ),
        "run_id": config.run_id,
        "runner_state": {
            "epoch": 0,
            "setup_complete": True,
            "step": resumed_step,
        },
        "schema_version": MICROLOOP_MANIFEST_SCHEMA_VERSION,
        "seed": config.seed,
        "statistics_fingerprint": config.statistics_fingerprint,
        "task_id": MICROLOOP_TASK_ID,
        "train_metrics": train,
        "transform_fingerprint": config.transform_fingerprint,
    }
    if any(value is not False for value in _EXTERNAL_EFFECTS_FALSE.values()):
        raise RuntimeError("microloop external effects must all be false")
    return manifest


def write_microloop_manifest(
    config: LocalRunnerDryRunConfig,
    manifest: Mapping[str, object],
) -> Path:
    """写入稳定排序的 microloop manifest 并校验 roundtrip。"""
    output_path = config.output_dir / config.run_id / MICROLOOP_MANIFEST_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    expected_text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output_path.write_text(expected_text, encoding="utf-8")
    loaded: object = json.loads(output_path.read_text(encoding="utf-8"))
    if loaded != manifest:
        raise RuntimeError("microloop manifest roundtrip failed")
    return output_path


def run_microloop(
    config: LocalRunnerDryRunConfig,
    *,
    batch: CollatedBatch | None = None,
    framework: _MicroloopFramework | None = None,
    resume_from: Path | None = None,
    require_compute_node: bool = False,
) -> MicroloopResult:
    """执行 deterministic CPU-only microloop 并写出 manifest。"""
    _validate_output_dir(config.output_dir)
    _validate_namespace_boundary()
    _validate_external_guards(require_compute_node=require_compute_node)
    requested_step = _prevalidate_resume(config, resume_from)

    selected_batch = batch if batch is not None else build_microloop_batch(config)
    _validate_batch_boundary(selected_batch)
    selected_framework = (
        framework if framework is not None else DeterministicActionFramework(prediction_value=1.0)
    )
    runner = LocalRunner(
        config=config.to_local_runner_config(),
        framework=selected_framework,
        batches=(selected_batch,),
    )
    runner.setup()
    train_metrics = runner.train()
    eval_metrics = runner.evaluate()
    _stable_metrics(train_metrics)
    _stable_metrics(eval_metrics)
    checkpoint_manifest_path = runner.save_checkpoint(runner.state.step)
    resumed_step = runner.resume(checkpoint_manifest_path)
    manifest = build_microloop_manifest(
        config,
        batch=selected_batch,
        train_metrics=train_metrics,
        eval_metrics=eval_metrics,
        checkpoint_manifest_path=checkpoint_manifest_path,
        resumed_step=resumed_step,
        requested_step=requested_step,
        require_compute_node=require_compute_node,
    )
    microloop_manifest_path = write_microloop_manifest(config, manifest)
    return MicroloopResult(
        microloop_manifest_path=microloop_manifest_path,
        checkpoint_manifest_path=checkpoint_manifest_path,
        resumed_step=resumed_step,
        train_metrics=_stable_metrics(train_metrics),
        eval_metrics=_stable_metrics(eval_metrics),
    )
