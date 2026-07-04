"""AutoVLA CPU-only 训练 runner dry-run harness。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

import numpy as np

from autovla.core.types import FrameworkOutput, ModelInput, NumericArray
from autovla.models.gr00t import Gr00tN1D6DryRunBatchAdapter
from autovla.models.registry import get as get_model_family
from autovla.training.checkpointing import (
    CheckpointCompatibilitySpec,
    TrainingCheckpointManifest,
)
from autovla.training.contracts import TrainingBatch
from autovla.training.efficiency import EfficiencyTelemetry
from autovla.training.fixtures import build_tiny_training_batch
from autovla.training.losses import MaskedActionLoss, masked_action_mse
from autovla.training.metrics import write_stable_json

CPU_DRY_RUN_MODE = "cpu_dry_run"


def _require_positive_int(value: int, name: str) -> None:
    """校验正整数且拒绝 bool。"""
    if type(value) is not int:
        raise TypeError(f"{name} must be an int")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _require_non_negative_int(value: int, name: str) -> None:
    """校验非负整数且拒绝 bool。"""
    if type(value) is not int:
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class DryRunConfig:
    """CPU-only runner dry-run 配置。"""

    family_key: str
    fixture: str
    output_dir: Path
    run_id: str = "autovla-runner-dryrun"
    seed: int = 0
    steps: int = 2

    def __post_init__(self) -> None:
        """校验配置保持本地 dry-run 边界。"""
        if not self.family_key.strip():
            raise ValueError("family must not be empty")
        if self.fixture != "tiny":
            raise ValueError("fixture must be tiny")
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty")
        _require_non_negative_int(self.seed, "seed")
        _require_positive_int(self.steps, "steps")
        if self.output_dir.exists() and not self.output_dir.is_dir():
            raise ValueError("output_dir must be a directory")


@dataclass(frozen=True, slots=True)
class RunnerState:
    """CPU dry-run runner 状态。"""

    run_id: str
    model_family_key: str
    seed: int
    step: int
    sample_count: int

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "model_family_key": self.model_family_key,
            "run_id": self.run_id,
            "sample_count": self.sample_count,
            "seed": self.seed,
            "step": self.step,
        }


@dataclass(frozen=True, slots=True)
class DryRunResult:
    """runner dry-run 的输出索引。"""

    output_dir: Path
    files: Mapping[str, Path]
    model_input: ModelInput
    resume_validation: Mapping[str, object]
    resumed_step: int


class DeterministicCpuPolicy:
    """确定性 CPU 策略 test double, 不加载真实模型。"""

    def __init__(self, *, seed: int) -> None:
        """记录 seed 并保持无外部副作用。"""
        self.seed = seed
        self._setup = False

    def setup(self) -> None:
        """标记 setup 完成, 不下载、不初始化真实模型。"""
        self._setup = True

    def forward_loss(self, batch: ModelInput) -> FrameworkOutput:
        """执行一次轻量前向占位, 仅返回确定性指标。"""
        if not self._setup:
            raise RuntimeError("policy setup must run before forward_loss")
        actions = np.asarray(batch.tensors["actions"], dtype=np.float64)
        return FrameworkOutput(
            loss=None,
            losses={},
            metrics={
                "action_mean": float(np.mean(actions)),
                "policy_seed": float(self.seed),
            },
        )

    def predict_actions(self, batch: ModelInput) -> NumericArray:
        """返回与目标同形状的确定性预测。"""
        self.forward_loss(batch)
        actions = np.asarray(batch.tensors["actions"], dtype=np.float32)
        prediction: NumericArray = np.array(actions + np.float32(0.1), dtype=np.float32)
        prediction.setflags(write=False)
        return prediction


class NumpyMaskedLossAdapter:
    """基于 numpy 的 masked action MSE loss adapter。"""

    def compute(self, prediction: object, target: object, action_mask: object) -> MaskedActionLoss:
        """计算严格 action mask 下的均方误差。"""
        return masked_action_mse(prediction, target, action_mask)


def _adapter_for_family(family_key: str) -> Gr00tN1D6DryRunBatchAdapter:
    """按模型族选择 dry-run adapter。"""
    try:
        spec = get_model_family(family_key)
    except KeyError as exc:
        raise ValueError(f"family {family_key!r} is not registered") from exc
    if spec.family_key != "gr00t-n1d6":
        raise ValueError(f"family {family_key!r} is metadata-only and has no dry-run adapter")
    return Gr00tN1D6DryRunBatchAdapter(expected_camera_count=3)


def _batch_for_fixture(fixture: str) -> TrainingBatch:
    """按 fixture 名构造内存训练批。"""
    if fixture != "tiny":
        raise ValueError("fixture must be tiny")
    return build_tiny_training_batch()


def _compatibility(config: DryRunConfig, batch: TrainingBatch) -> CheckpointCompatibilitySpec:
    """从配置和 batch 构造 checkpoint 兼容性描述。"""
    return CheckpointCompatibilitySpec(
        model_family_key=config.family_key,
        model_registry_key=config.family_key,
        dataset_fingerprint=batch.dataset_fingerprint,
        transform_fingerprint=batch.transform_fingerprint,
        statistics_fingerprint=batch.statistics_fingerprint,
        action_horizon=batch.action_horizon,
        action_dim=batch.action_dim,
    )


def _field_errors(
    *,
    manifest: TrainingCheckpointManifest,
    expected: CheckpointCompatibilitySpec,
) -> dict[str, dict[str, object]]:
    """返回 checkpoint resume 字段级 mismatch。"""
    actual = manifest.compatibility
    errors: dict[str, dict[str, object]] = {}
    for name in (
        "model_family_key",
        "model_registry_key",
        "dataset_fingerprint",
        "transform_fingerprint",
        "statistics_fingerprint",
        "action_horizon",
        "action_dim",
    ):
        actual_value = getattr(actual, name)
        expected_value = getattr(expected, name)
        if actual_value != expected_value:
            errors[name] = {"actual": actual_value, "expected": expected_value}
    return errors


def validate_resume_manifest(
    manifest: TrainingCheckpointManifest,
    expected: CheckpointCompatibilitySpec,
) -> dict[str, object]:
    """执行字段级 resume 兼容性校验。"""
    errors = _field_errors(manifest=manifest, expected=expected)
    if errors:
        return {"compatible": False, "field_errors": errors}
    return {"compatible": True, "compatible_step": manifest.step, "field_errors": {}}


def _deterministic_telemetry(batch: TrainingBatch, steps: int) -> EfficiencyTelemetry:
    """根据 batch/steps 生成稳定的 CPU dry-run 遥测。"""
    sample_count = batch.batch_size * steps
    total_step_ms = 7.5
    return EfficiencyTelemetry(
        samples_per_second=float(sample_count) / (total_step_ms / 1000.0 * steps),
        batches_per_second=1000.0 / total_step_ms,
        batch_latency_ms_p50=total_step_ms,
        batch_latency_ms_p95=total_step_ms,
        data_wait_time_ms=1.0,
        collate_time_ms=0.5,
        adapter_time_ms=2.0,
        forward_time_ms=3.0,
        loss_time_ms=0.25,
        checkpoint_manifest_time_ms=0.75,
        memory_envelope_mb=64.0,
    )


def _step_metrics(
    *,
    steps: int,
    loss: MaskedActionLoss,
    batch: TrainingBatch,
) -> list[dict[str, object]]:
    """构造稳定 step metrics。"""
    return [
        {
            "action_dim": batch.action_dim,
            "action_horizon": batch.action_horizon,
            "loss": round(loss.value, 8),
            "sample_count": batch.batch_size,
            "step": step,
            "valid_action_elements": loss.valid_count,
        }
        for step in range(1, steps + 1)
    ]


def run_training_dry_run(config: DryRunConfig) -> DryRunResult:
    """执行 CPU-only training runner dry-run 并写出稳定 JSON 产物。"""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    batch = _batch_for_fixture(config.fixture)
    adapter = _adapter_for_family(config.family_key)
    model_input = adapter.to_model_input(batch)
    policy = DeterministicCpuPolicy(seed=config.seed)
    policy.setup()
    prediction = policy.predict_actions(model_input)
    loss = NumpyMaskedLossAdapter().compute(prediction, batch.actions, batch.action_mask)
    state = RunnerState(
        run_id=config.run_id,
        model_family_key=config.family_key,
        seed=config.seed,
        step=config.steps,
        sample_count=batch.batch_size * config.steps,
    )
    compatibility = _compatibility(config, batch)
    manifest = TrainingCheckpointManifest(
        run_id=config.run_id,
        step=config.steps,
        compatibility=compatibility,
    )
    incompatible_expected = CheckpointCompatibilitySpec(
        model_family_key=config.family_key,
        model_registry_key=config.family_key,
        dataset_fingerprint="wrong-dataset",
        transform_fingerprint=batch.transform_fingerprint,
        statistics_fingerprint=batch.statistics_fingerprint,
        action_horizon=batch.action_horizon,
        action_dim=batch.action_dim,
    )
    resume_validation = {
        "compatible": True,
        "compatible_step": manifest.validate_resume(compatibility),
        "incompatible": validate_resume_manifest(manifest, incompatible_expected),
    }
    telemetry = _deterministic_telemetry(batch, config.steps)
    files = {
        "run_manifest": write_stable_json(
            config.output_dir / "run_manifest.json",
            {
                "family_key": config.family_key,
                "fixture": config.fixture,
                "mode": CPU_DRY_RUN_MODE,
                "run_id": config.run_id,
                "seed": config.seed,
                "steps": config.steps,
            },
        ),
        "runner_state": write_stable_json(
            config.output_dir / "runner_state.json",
            state.to_json_dict(),
        ),
        "efficiency_telemetry": write_stable_json(
            config.output_dir / "efficiency_telemetry.json",
            telemetry.to_json_dict(),
        ),
        "step_metrics": write_stable_json(
            config.output_dir / "step_metrics.json",
            _step_metrics(steps=config.steps, loss=loss, batch=batch),
        ),
        "checkpoint_manifest": write_stable_json(
            config.output_dir / "checkpoint_manifest.json",
            manifest.to_json_dict(),
        ),
        "resume_validation": write_stable_json(
            config.output_dir / "resume_validation.json",
            cast(dict[str, object], resume_validation),
        ),
    }
    return DryRunResult(
        output_dir=config.output_dir,
        files=MappingProxyType(files),
        model_input=model_input,
        resume_validation=MappingProxyType(resume_validation),
        resumed_step=config.steps,
    )


def build_default_config(
    *,
    family_key: str,
    fixture: str,
    steps: int,
    output_dir: Path,
) -> DryRunConfig:
    """从 CLI 参数构造默认 dry-run 配置。"""
    return DryRunConfig(
        family_key=family_key,
        fixture=fixture,
        output_dir=output_dir,
        steps=steps,
    )
