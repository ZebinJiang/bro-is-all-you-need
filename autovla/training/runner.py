"""AutoVLA CPU-only 训练 runner dry-run harness。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

import numpy as np

from autovla.config.loader import resolved_config_fingerprint, to_resolved_dict
from autovla.config.schema import ExperimentConfig, RunnerBackend
from autovla.core.types import FrameworkOutput, ModelInput, NumericArray, TrainingBatch
from autovla.dataloader.backends import create_training_batch_source, get_backend_spec
from autovla.dataloader.stores.common import stable_checksum
from autovla.models.gr00t import Gr00tN1D6DryRunBatchAdapter
from autovla.models.registry import get as get_model_family
from autovla.training.checkpointing import (
    CheckpointCompatibilitySpec,
    TrainingCheckpointManifest,
)
from autovla.training.efficiency import EfficiencyTelemetry
from autovla.training.fixtures import build_tiny_training_batch
from autovla.training.losses import MaskedActionLoss, masked_action_mse
from autovla.training.metrics import write_stable_json
from autovla.training.registry import (
    BATCH_ADAPTER_FACTORIES,
    CHECKPOINT_FACTORIES,
    DEPLOYMENT_HOOK_FACTORIES,
    LOSS_FACTORIES,
    MODEL_FAMILY_FACTORIES,
    POLICY_FACTORIES,
    RUNTIME_PLAN_FACTORIES,
)

CPU_DRY_RUN_MODE = "cpu_dry_run"
MODULAR_DRY_RUN_MODE = "modular_skeleton_dry_run"


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


@dataclass(frozen=True, slots=True)
class ModularDryRunResult:
    """M4 模块化 dry-run 的稳定输出索引。"""

    output_dir: Path
    backend_key: str
    model_metadata_key: str
    config_fingerprint: str
    step_count: int
    manifest_path: Path
    telemetry_path: Path
    checkpoint_manifest_path: Path
    logical_fixture_manifest_path: Path
    canonical_batch_fingerprints: tuple[str, ...]
    status: str = "PASS_DRY_RUN"


def _validate_modular_config(config: ExperimentConfig) -> None:
    """在产生任何输出前拒绝未实现或有外部副作用的设置。"""
    if config.data.backend is None:
        raise ValueError("data.backend must be explicit; no backend is default")
    if config.runner.backend is not RunnerBackend.LOCAL:
        raise ValueError("modular dry-run requires runner.backend=local")
    if config.runner.device != "cpu":
        raise ValueError("modular dry-run requires runner.device=cpu")
    if config.runner.batch_size not in {2, 4}:
        raise ValueError("modular dry-run batch_size must be 2 or 4")
    if config.runner.max_steps < 2:
        raise ValueError("modular dry-run requires at least two steps")
    if config.seed != 11:
        raise ValueError("modular dry-run fixture seed must be 11")
    if config.deployment.enabled:
        raise ValueError("deployment.enabled must remain false")
    if config.acceleration.enabled:
        raise ValueError("acceleration.enabled must remain false")
    if config.model.registry_key != "test_double":
        raise ValueError("metadata-only model profiles cannot execute")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    """写出按输入顺序稳定排列的 JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def run_modular_training_dry_run(
    config: ExperimentConfig,
    *,
    output_dir: Path,
) -> ModularDryRunResult:
    """执行同一注册表路径上的双后端 M4 本地模块化 dry-run。

    该函数只执行确定性 numpy 测试策略和 metadata-only checkpoint manifest,
    不执行真实训练、梯度、模型/资产加载、网络、GPU、Slurm 或端点调用。
    """
    _validate_modular_config(config)
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("output_dir must be a directory")
    backend_key = get_backend_spec(cast(str, config.data.backend)).backend_key
    model_spec = MODEL_FAMILY_FACTORIES.get(config.model.registry_key)()
    adapter = BATCH_ADAPTER_FACTORIES.get(config.runner.batch_adapter)()
    policy = POLICY_FACTORIES.get(config.runner.policy)(config.seed)
    loss_adapter = LOSS_FACTORIES.get(config.runner.loss)()
    checkpoint_adapter = CHECKPOINT_FACTORIES.get(config.runner.checkpoint_adapter)()
    runtime_plan = RUNTIME_PLAN_FACTORIES.get(config.runner.runtime_plan)()
    deployment_hook = DEPLOYMENT_HOOK_FACTORIES.get(config.runner.deployment_hook)()
    config_fingerprint = resolved_config_fingerprint(config)
    dataset_fingerprint = stable_checksum(
        {"fixture": "autovla-m4-logical-fixture-v1", "seed": config.seed}
    )
    source = create_training_batch_source(
        backend_key,
        root=output_dir / "fixture",
        seed=config.seed,
        action_horizon=config.runner.action_horizon,
        action_dim=config.runner.action_dim,
        dataset_fingerprint=dataset_fingerprint,
        transform_fingerprint="autovla-m4-identity-transform-v1",
        statistics_fingerprint="autovla-m4-identity-statistics-v1",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_config_path = write_stable_json(
        output_dir / "resolved-config.json",
        to_resolved_dict(config),
    )
    telemetry_rows: list[dict[str, object]] = []
    batch_fingerprints: list[str] = []
    losses: list[float] = []
    valid_counts: list[int] = []
    fixture_manifest: dict[str, object]
    policy.setup()
    try:
        fixture_manifest = source.prepare()
        for step in range(1, config.runner.max_steps + 1):
            start = (step - 1) * config.runner.batch_size
            indices = tuple(range(start, start + config.runner.batch_size))
            batch = source.read_batch(indices)
            fingerprint = cast(str, batch.metadata["logical_batch_fingerprint"])
            batch_fingerprints.append(fingerprint)
            telemetry_rows.append(
                {"stage": "data", "step": step, "synthetic": True, "sample_count": batch.batch_size}
            )
            model_input = adapter.to_model_input(batch)
            telemetry_rows.append(
                {"stage": "batch_adapter", "step": step, "synthetic": True, "status": "PASS"}
            )
            prediction = policy.predict_actions(model_input)
            telemetry_rows.append(
                {"stage": "test_policy", "step": step, "synthetic": True, "status": "PASS"}
            )
            loss = loss_adapter.compute(prediction, batch.actions, batch.action_mask)
            losses.append(round(loss.value, 8))
            valid_counts.append(loss.valid_count)
            telemetry_rows.append(
                {
                    "loss": round(loss.value, 8),
                    "stage": "masked_loss",
                    "step": step,
                    "synthetic": True,
                    "valid_action_elements": loss.valid_count,
                }
            )
            telemetry_rows.append(
                {
                    "stage": "checkpoint_manifest",
                    "step": step,
                    "synthetic": True,
                    "status": "metadata_only",
                }
            )
    finally:
        source.close()

    logical_fixture_manifest_path = write_stable_json(
        output_dir / "logical-fixture-manifest.json",
        fixture_manifest,
    )
    compatibility = CheckpointCompatibilitySpec(
        model_family_key=model_spec.family_key,
        model_registry_key=config.model.registry_key,
        dataset_fingerprint=dataset_fingerprint,
        transform_fingerprint="autovla-m4-identity-transform-v1",
        statistics_fingerprint="autovla-m4-identity-statistics-v1",
        action_horizon=config.runner.action_horizon,
        action_dim=config.runner.action_dim,
    )
    checkpoint_manifest = TrainingCheckpointManifest(
        run_id=config.name,
        step=config.runner.max_steps,
        compatibility=compatibility,
    )
    checkpoint_manifest_path = checkpoint_adapter.write(
        output_dir / "checkpoint-manifest.json",
        checkpoint_manifest,
    )
    telemetry_path = _write_jsonl(output_dir / "telemetry.jsonl", telemetry_rows)
    write_stable_json(
        output_dir / "deployment-manifest.json",
        deployment_hook.to_json_dict(),
    )
    write_stable_json(
        output_dir / "runtime-plan.json",
        runtime_plan.to_json_dict(),
    )
    manifest_path = write_stable_json(
        output_dir / "dry-run-manifest.json",
        {
            "backend": backend_key,
            "canonical_batch_fingerprints": batch_fingerprints,
            "checkpoint_manifest_path": str(checkpoint_manifest_path),
            "component_keys": {
                "batch_adapter": config.runner.batch_adapter,
                "checkpoint_adapter": config.runner.checkpoint_adapter,
                "deployment_hook": config.runner.deployment_hook,
                "loss": config.runner.loss,
                "policy": config.runner.policy,
                "runtime_plan": config.runner.runtime_plan,
            },
            "config_fingerprint": config_fingerprint,
            "external_effects": {
                "checkpoint_or_weights_loaded": False,
                "gpu_or_slurm": False,
                "model_or_tokenizer_loaded": False,
                "network_hf_wandb": False,
                "robot_or_endpoint": False,
            },
            "fixture_logical_fingerprint": fixture_manifest["logical_fingerprint"],
            "losses": losses,
            "mode": MODULAR_DRY_RUN_MODE,
            "model_metadata_key": model_spec.family_key,
            "native_compatible": get_backend_spec(backend_key).capabilities.native_compatible,
            "resolved_config_path": str(resolved_config_path),
            "schema_version": "autovla.modular_dry_run_manifest.v1",
            "status": "PASS_DRY_RUN",
            "step_count": config.runner.max_steps,
            "valid_action_elements": valid_counts,
            "weights_written": False,
        },
    )
    return ModularDryRunResult(
        output_dir=output_dir,
        backend_key=backend_key,
        model_metadata_key=model_spec.family_key,
        config_fingerprint=config_fingerprint,
        step_count=config.runner.max_steps,
        manifest_path=manifest_path,
        telemetry_path=telemetry_path,
        checkpoint_manifest_path=checkpoint_manifest_path,
        logical_fixture_manifest_path=logical_fixture_manifest_path,
        canonical_batch_fingerprints=tuple(batch_fingerprints),
    )


def write_backend_parity_evidence(dry_run_root: Path) -> tuple[Path, Path, Path]:
    """比较两个 dry-run manifest 并写出任务要求的全局 parity 证据。"""
    webdataset_root = dry_run_root / "webdataset"
    robodm_root = dry_run_root / "robodm"
    webdataset_manifest = json.loads(
        (webdataset_root / "dry-run-manifest.json").read_text(encoding="utf-8")
    )
    robodm_manifest = json.loads(
        (robodm_root / "dry-run-manifest.json").read_text(encoding="utf-8")
    )
    compared_fields = (
        "canonical_batch_fingerprints",
        "fixture_logical_fingerprint",
        "losses",
        "model_metadata_key",
        "status",
        "step_count",
        "valid_action_elements",
        "weights_written",
    )
    mismatches = {
        field: {
            "webdataset_tar": webdataset_manifest.get(field),
            "robodm_container_v1": robodm_manifest.get(field),
        }
        for field in compared_fields
        if webdataset_manifest.get(field) != robodm_manifest.get(field)
    }
    if mismatches:
        raise ValueError(f"canonical backend parity mismatch: {sorted(mismatches)}")
    logical_fixture = json.loads(
        (webdataset_root / "logical-fixture-manifest.json").read_text(encoding="utf-8")
    )
    logical_fixture_path = write_stable_json(
        dry_run_root / "logical-fixture-manifest.json",
        cast(dict[str, object], logical_fixture),
    )
    parity_path = dry_run_root / "backend-parity-summary.md"
    parity_path.write_text(
        "# Backend Parity Summary\n\n"
        "- conclusion: `PASS_EQUIVALENT_CANONICAL_BATCHES`\n"
        "- backends: `webdataset_tar`, `robodm_container_v1`\n"
        "- compared: ordered semantic batch fingerprints, fixture fingerprint, masked loss, "
        "valid mask counts, step count, model metadata, and metadata-only checkpoint status\n"
        "- interpretation: integration equivalence only; no performance comparison\n"
        "- decision: `NO_BACKEND_WINNER`\n",
        encoding="utf-8",
    )
    side_effect_path = dry_run_root / "no-runtime-side-effect-check.md"
    side_effect_path.write_text(
        "# No Runtime Side Effect Check\n\n"
        "- model/checkpoint/tokenizer load: no\n"
        "- real training or gradients: no\n"
        "- network, Hugging Face, or W&B: no\n"
        "- GPU or Slurm: no\n"
        "- endpoint or robot action: no\n"
        "- weights or optimizer state written: no\n"
        "- telemetry: deterministic synthetic integration counters only\n"
        "- backend decision: `NO_BACKEND_WINNER`\n",
        encoding="utf-8",
    )
    return logical_fixture_path, parity_path, side_effect_path


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
