"""PR31 Core 契约、能力和导入边界集中回归测试。"""

from __future__ import annotations

import inspect
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from autovla.config.loader import load_yaml
from autovla.core.reporting import PerformanceTable as CorePerformanceTable
from autovla.core.reporting import stable_json_dumps as core_stable_json_dumps
from autovla.core.types import TrainingBatch
from autovla.models.capabilities import (
    ComponentDescriptor,
    ComponentRole,
    ExecutionMode,
    NormalizationMode,
    SideEffectPermissions,
    SupportState,
)
from autovla.models.registry import get_model_family_spec
from autovla.training.checkpointing import (
    CheckpointCompatibilitySpec,
    TrainingCheckpointManifest,
)
from autovla.training.contracts import (
    ActionPolicy,
    BatchAdapter,
    CheckpointAdapter,
    LossAdapter,
    TrainablePolicy,
)
from autovla.training.registry import (
    create_action_policy,
    create_batch_adapter,
    create_checkpoint_adapter,
    create_loss_adapter,
)
from autovla.training.runner import (
    require_logical_batch_fingerprint_for_parity,
    run_modular_training_dry_run,
    write_backend_parity_evidence,
)
from autovla.training.test_components import TestDoubleBatchAdapter as _TestDoubleBatchAdapter


def _test_double_batch(*, metadata: dict[str, object] | None = None) -> TrainingBatch:
    """构造满足精确 test-double 输入约束的规范批。"""
    actions = np.ones((2, 2, 3), dtype=np.float32)
    return TrainingBatch(
        images={
            "camera.rgb_0": np.zeros((2, 4, 4, 3), dtype=np.float32),
            "camera.rgb_1": np.ones((2, 4, 4, 3), dtype=np.float32),
            "camera.rgb_2": np.full((2, 4, 4, 3), 2.0, dtype=np.float32),
        },
        language=("pick cube", "place cube"),
        actions=actions,
        action_mask=np.ones_like(actions, dtype=np.bool_),
        state=np.zeros((2, 7), dtype=np.float32),
        sample_source=({"episode": "e0"}, {"episode": "e1"}),
        dataset_fingerprint="dataset",
        transform_fingerprint="identity-transform",
        statistics_fingerprint="identity-statistics",
        metadata={} if metadata is None else metadata,
    )


def test_cold_backend_import_should_not_load_training_or_implementation_roots() -> None:
    """验证 find_spec 和实际后端导入都保持轻量边界。"""
    script = """
import importlib.util
import sys

assert importlib.util.find_spec("autovla.dataloader.backends") is not None
import autovla.dataloader.backends

forbidden = {
    "autovla.dataloader.format_pipeline.pipeline",
    "autovla.dataloader.perf.synthetic",
    "autovla.dataloader.stores.training_batch_readers",
    "webdataset",
}
loaded = set(sys.modules)
assert not any(name.startswith("autovla.training") for name in loaded), sorted(loaded)
assert not (forbidden & loaded), sorted(forbidden & loaded)
print("PASS_COLD_BACKEND_IMPORT_BOUNDARY")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PASS_COLD_BACKEND_IMPORT_BOUNDARY"


def test_cold_model_metadata_import_should_not_load_heavy_runtime_roots() -> None:
    """验证公开模型元数据查询不加载训练、部署或重型模型运行时。"""
    script = """
import sys

import autovla.models as models

required = {"test_double", "gr00t_n1d6_metadata", "pi0_metadata", "pi05_metadata"}
assert required.issubset(models.list_model_family_keys())
heavy = {"torch", "transformers", "gr00t", "jax", "flax", "openpi", "huggingface_hub", "wandb"}
loaded = set(sys.modules)
assert not any(name == root or name.startswith(root + ".") for root in heavy for name in loaded)
assert "autovla.training.runner" not in loaded
assert "autovla.training.registry" not in loaded
assert not any(name.startswith("autovla.deployment") for name in loaded)
print("PASS_COLD_MODEL_METADATA_IMPORT_BOUNDARY")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PASS_COLD_MODEL_METADATA_IMPORT_BOUNDARY"


def test_reporting_and_training_compatibility_exports_should_preserve_identity() -> None:
    """验证 neutral Core 报告对象与 Training 兼容路径身份一致。"""
    from autovla.training.metrics import stable_json_dumps as metrics_stable_json_dumps
    from autovla.training.performance_tables import PerformanceTable, stable_json_dumps

    assert PerformanceTable is CorePerformanceTable
    assert stable_json_dumps is core_stable_json_dumps
    assert metrics_stable_json_dumps is core_stable_json_dumps


def test_canonical_protocols_and_products_should_share_one_identity() -> None:
    """验证规范协议签名、旧名称身份和注册产品结构一致。"""
    assert TrainablePolicy is ActionPolicy
    assert "forward_loss" not in ActionPolicy.__dict__
    assert tuple(inspect.signature(BatchAdapter.to_model_input).parameters) == ("self", "batch")
    assert tuple(inspect.signature(ActionPolicy.predict_actions).parameters) == ("self", "batch")
    assert tuple(inspect.signature(LossAdapter.compute).parameters) == (
        "self",
        "prediction",
        "target",
        "action_mask",
    )
    assert tuple(inspect.signature(CheckpointAdapter.write_manifest).parameters) == (
        "self",
        "path",
        "manifest",
    )
    assert tuple(inspect.signature(CheckpointAdapter.validate_resume).parameters) == (
        "self",
        "manifest",
        "expected",
    )

    assert isinstance(
        create_batch_adapter("test_double_batch_v1", action_horizon=2, action_dim=3), BatchAdapter
    )
    assert isinstance(create_action_policy("deterministic_test_policy_v1", seed=11), ActionPolicy)
    assert isinstance(create_loss_adapter("masked_action_mse_v1"), LossAdapter)
    assert isinstance(create_checkpoint_adapter("manifest_only_v1"), CheckpointAdapter)


def test_capability_profiles_should_be_immutable_complete_and_distinct() -> None:
    """验证四个 profile 的结构化能力值和 metadata-only 权限。"""
    test_double = get_model_family_spec("test_double")
    gr00t = get_model_family_spec("gr00t_n1d6_metadata")
    pi0 = get_model_family_spec("pi0_metadata")
    pi05 = get_model_family_spec("pi05_metadata")

    assert test_double.capabilities.execution.executable_test_double is True
    assert test_double.capabilities.inputs.required_cameras == (
        "camera.rgb_0",
        "camera.rgb_1",
        "camera.rgb_2",
    )
    assert test_double.capabilities.normalization.mode is NormalizationMode.IDENTITY
    assert test_double.capabilities.normalization.statistics_required is False
    assert test_double.capabilities.execution.permissions.any_enabled() is False
    assert {mode.value for mode in ExecutionMode} == {
        "deterministic_test_only",
        "metadata_only",
    }
    assert gr00t.capabilities.normalization.mode is NormalizationMode.STATISTICS_GOVERNED
    assert gr00t.capabilities.normalization.statistics_required is True
    assert pi0.capabilities.processor.identity == "pi0_processor"
    assert pi05.capabilities.processor.identity == "pi05_processor"
    for profile in (gr00t, pi0, pi05):
        assert profile.capabilities.execution.mode is ExecutionMode.METADATA_ONLY
        assert profile.capabilities.execution.executable_test_double is False
        assert profile.capabilities.execution.permissions.any_enabled() is False
        assert profile.capabilities.processor.support is SupportState.UNVERIFIED

    with pytest.raises(FrozenInstanceError):
        cast(object, test_double.capabilities).__setattr__(
            "processor", gr00t.capabilities.processor
        )
    with pytest.raises(ValueError, match="metadata-only profiles"):
        replace(
            gr00t.capabilities,
            processor=ComponentDescriptor(
                ComponentRole.PROCESSOR,
                "invalid-supported-processor",
                SupportState.SUPPORTED,
            ),
        )


@pytest.mark.parametrize("support", (SupportState.UNVERIFIED, SupportState.UNSUPPORTED))
def test_deterministic_capability_should_require_supported_execution(
    support: SupportState,
) -> None:
    """验证所有确定性执行记录都必须声明受支持。"""
    capabilities = get_model_family_spec("test_double").capabilities

    with pytest.raises(ValueError, match="exact test_double tuple"):
        replace(capabilities, execution=replace(capabilities.execution, support=support))


def test_deterministic_capability_should_reject_altered_tuple() -> None:
    """验证确定性执行记录拒绝任何非规范元组字段。"""
    capabilities = get_model_family_spec("test_double").capabilities

    with pytest.raises(ValueError, match="exact test_double tuple"):
        replace(
            capabilities,
            processor=replace(capabilities.processor, identity="altered_processor"),
        )


def test_deterministic_capability_should_reject_enabled_permission() -> None:
    """验证确定性执行记录拒绝任一副作用权限。"""
    capabilities = get_model_family_spec("test_double").capabilities

    with pytest.raises(ValueError, match="exact test_double tuple"):
        replace(
            capabilities,
            execution=replace(
                capabilities.execution,
                permissions=SideEffectPermissions(runtime_import=True),
            ),
        )


def test_test_double_adapter_should_enforce_exact_inputs_and_optional_fingerprint() -> None:
    """验证适配器精确输入约束并保持通用 fingerprint 可选。"""
    adapter = _TestDoubleBatchAdapter(action_horizon=2, action_dim=3)
    model_input = adapter.to_model_input(_test_double_batch())

    assert "logical_batch_fingerprint" not in model_input.metadata
    assert model_input.metadata["normalization_mode"] == "identity"
    assert model_input.metadata["statistics_fingerprint"] == "identity-statistics"
    assert model_input.metadata["action_horizon"] == 2
    assert model_input.metadata["action_dim"] == 3

    with pytest.raises(ValueError, match="cameras must be exactly"):
        bad_cameras = _test_double_batch()
        adapter.to_model_input(
            TrainingBatch(
                images={"camera.rgb_0": bad_cameras.images["camera.rgb_0"]},
                language=bad_cameras.language,
                actions=bad_cameras.actions,
                action_mask=bad_cameras.action_mask,
                state=bad_cameras.state,
                sample_source=bad_cameras.sample_source,
                dataset_fingerprint=bad_cameras.dataset_fingerprint,
                transform_fingerprint=bad_cameras.transform_fingerprint,
                statistics_fingerprint=bad_cameras.statistics_fingerprint,
            )
        )
    with pytest.raises(ValueError, match="state is required"):
        batch = _test_double_batch()
        adapter.to_model_input(
            TrainingBatch(
                images=batch.images,
                language=batch.language,
                actions=batch.actions,
                action_mask=batch.action_mask,
                state=None,
                sample_source=batch.sample_source,
                dataset_fingerprint=batch.dataset_fingerprint,
                transform_fingerprint=batch.transform_fingerprint,
                statistics_fingerprint=batch.statistics_fingerprint,
            )
        )
    with pytest.raises(ValueError, match=r"configured \[B,H,D\]"):
        _TestDoubleBatchAdapter(action_horizon=4, action_dim=3).to_model_input(_test_double_batch())


def test_parity_fingerprint_should_be_required_only_by_parity_validation() -> None:
    """验证 fingerprint 缺失只在 parity 路径产生稳定 ValueError。"""
    with pytest.raises(ValueError, match="backend parity requires logical_batch_fingerprint"):
        require_logical_batch_fingerprint_for_parity(_test_double_batch())
    assert (
        require_logical_batch_fingerprint_for_parity(
            _test_double_batch(metadata={"logical_batch_fingerprint": "batch-fp"})
        )
        == "batch-fp"
    )


@pytest.mark.parametrize(
    "profile_key",
    ("gr00t_n1d6_metadata", "pi0_metadata", "pi05_metadata"),
)
def test_metadata_profiles_should_fail_before_output_creation(
    tmp_path: Path,
    profile_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 metadata-only profile 在任何输出或运行工厂前失败。"""
    import autovla.training.runner as runner_module

    def forbidden_factory(*args: object, **kwargs: object) -> object:
        """在 metadata-only gate 之后标记任何意外工厂调用。"""
        raise AssertionError(f"factory must not run: args={args}, kwargs={kwargs}")

    for name in (
        "create_action_policy",
        "create_batch_adapter",
        "create_checkpoint_adapter",
        "create_loss_adapter",
    ):
        monkeypatch.setattr(runner_module, name, forbidden_factory)
    output_dir = tmp_path / profile_key
    config = load_yaml(
        "configs/training/modular_skeleton_webdataset.yaml",
        overrides=(f"model.registry_key={profile_key}",),
    )
    with pytest.raises(ValueError, match="metadata-only"):
        runner_module.run_modular_training_dry_run(config, output_dir=output_dir)
    assert not output_dir.exists()


def test_checkpoint_adapter_should_roundtrip_strict_file_schema(tmp_path: Path) -> None:
    """验证规范 checkpoint 写入、严格读取和恢复校验。"""
    compatibility = CheckpointCompatibilitySpec(
        model_family_key="test_double",
        model_registry_key="test_double",
        dataset_fingerprint="dataset",
        transform_fingerprint="transform",
        statistics_fingerprint="statistics",
        action_horizon=2,
        action_dim=3,
    )
    manifest = TrainingCheckpointManifest(run_id="run", step=2, compatibility=compatibility)
    adapter = create_checkpoint_adapter("manifest_only_v1")
    path = adapter.write_manifest(tmp_path / "checkpoint.json", manifest)
    restored = TrainingCheckpointManifest.read(path)
    assert adapter.validate_resume(restored, compatibility) == 2

    payload = restored.to_json_dict()
    payload["weights_written"] = 0
    with pytest.raises(ValueError, match="weights_written must be a bool"):
        TrainingCheckpointManifest.from_json_dict(payload)


def test_canonical_presets_should_keep_two_step_parity_and_no_winner(tmp_path: Path) -> None:
    """验证两个规范 preset、两步路径、parity 和无后端胜者语义。"""
    root = tmp_path / "dry-run"
    results = (
        run_modular_training_dry_run(
            load_yaml("configs/training/modular_skeleton_webdataset.yaml"),
            output_dir=root / "webdataset",
        ),
        run_modular_training_dry_run(
            load_yaml("configs/training/modular_skeleton_robodm.yaml"),
            output_dir=root / "robodm",
        ),
    )
    assert tuple(result.step_count for result in results) == (2, 2)
    assert results[0].canonical_batch_fingerprints == results[1].canonical_batch_fingerprints
    _, parity_path, side_effect_path = write_backend_parity_evidence(root)
    assert "PASS_EQUIVALENT_CANONICAL_BATCHES" in parity_path.read_text(encoding="utf-8")
    assert "NO_BACKEND_WINNER" in parity_path.read_text(encoding="utf-8")
    assert "NO_BACKEND_WINNER" in side_effect_path.read_text(encoding="utf-8")
