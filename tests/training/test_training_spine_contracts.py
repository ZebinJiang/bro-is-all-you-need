"""AutoVLA 训练主干契约测试。"""

from __future__ import annotations

import json
from typing import cast

import numpy as np
import pytest

from autovla.core.types import ActionMask
from autovla.training import (
    CheckpointCompatibilitySpec,
    EfficiencyTelemetry,
    EnvProfile,
    RuntimePlan,
    TrainingBatch,
    TrainingCheckpointManifest,
    masked_action_mse,
)


def _training_batch() -> TrainingBatch:
    """构造最小合法训练批。"""
    actions = np.ones((2, 4, 3), dtype=np.float32)
    return TrainingBatch(
        images={
            "front": np.zeros((2, 4, 4, 3), dtype=np.float32),
            "left": np.ones((2, 4, 4, 3), dtype=np.float32),
            "right": np.full((2, 4, 4, 3), 2.0, dtype=np.float32),
        },
        language=("pick cube", "place cube"),
        actions=actions,
        action_mask=np.ones_like(actions, dtype=np.bool_),
        state=np.zeros((2, 7), dtype=np.float32),
        sample_source=({"episode": "e0"}, {"episode": "e1"}),
        dataset_fingerprint="dataset-fp",
        transform_fingerprint="transform-fp",
        statistics_fingerprint="stats-fp",
    )


def test_training_batch_should_validate_generic_handoff_contract() -> None:
    """验证 TrainingBatch 是模型族无关的通用 handoff。"""
    batch = _training_batch()

    assert batch.batch_size == 2
    assert batch.action_horizon == 4
    assert batch.action_dim == 3
    assert set(batch.images) == {"front", "left", "right"}
    assert batch.actions.flags.writeable is False
    assert batch.action_mask.flags.writeable is False


def test_training_batch_should_own_metadata_and_provenance_mappings() -> None:
    """验证 batch 构造后外部 metadata/provenance 变更不会污染 handoff。"""
    image_map = {
        "front": np.zeros((1, 4, 4, 3), dtype=np.float32),
        "left": np.ones((1, 4, 4, 3), dtype=np.float32),
        "right": np.full((1, 4, 4, 3), 2.0, dtype=np.float32),
    }
    source = {"episode": "e0"}
    metadata = {"tag": "before"}
    actions = np.ones((1, 2, 3), dtype=np.float32)

    batch = TrainingBatch(
        images=image_map,
        language=("pick cube",),
        actions=actions,
        action_mask=np.ones_like(actions, dtype=np.bool_),
        sample_source=(source,),
        dataset_fingerprint="dataset-fp",
        transform_fingerprint="transform-fp",
        statistics_fingerprint="stats-fp",
        metadata=metadata,
    )

    image_map["rear"] = np.full((1, 4, 4, 3), 3.0, dtype=np.float32)
    source["episode"] = "mutated"
    metadata["tag"] = "after"

    assert set(batch.images) == {"front", "left", "right"}
    assert batch.sample_source[0]["episode"] == "e0"
    assert batch.metadata["tag"] == "before"
    with pytest.raises(TypeError):
        cast(dict[str, object], batch.images)["rear"] = np.zeros((1, 4, 4, 3), dtype=np.float32)
    with pytest.raises(TypeError):
        cast(dict[str, object], batch.sample_source[0])["episode"] = "mutated-again"
    with pytest.raises(TypeError):
        cast(dict[str, object], batch.metadata)["tag"] = "mutated-again"


def test_training_batch_should_reject_bad_masks_and_missing_fingerprints() -> None:
    """验证 action mask 和 fingerprint fail closed。"""
    actions = np.ones((1, 2, 3), dtype=np.float32)

    with pytest.raises(TypeError, match="action_mask"):
        TrainingBatch(
            images={"front": np.zeros((1, 2, 2, 3), dtype=np.float32)},
            language=("x",),
            actions=actions,
            action_mask=cast(ActionMask, np.ones((1, 2, 3), dtype=np.float32)),
            sample_source=({"episode": "e0"},),
            dataset_fingerprint="dataset",
            transform_fingerprint="transform",
            statistics_fingerprint="stats",
        )
    with pytest.raises(ValueError, match="dataset_fingerprint"):
        TrainingBatch(
            images={"front": np.zeros((1, 2, 2, 3), dtype=np.float32)},
            language=("x",),
            actions=actions,
            action_mask=np.ones((1, 2, 3), dtype=np.bool_),
            sample_source=({"episode": "e0"},),
            dataset_fingerprint="",
            transform_fingerprint="transform",
            statistics_fingerprint="stats",
        )


def test_masked_loss_should_reject_all_zero_mask() -> None:
    """验证损失函数拒绝全零 mask。"""
    prediction = np.ones((1, 2, 3), dtype=np.float32)
    target = np.zeros((1, 2, 3), dtype=np.float32)
    mask = np.zeros((1, 2, 3), dtype=np.bool_)

    with pytest.raises(ValueError, match="valid action elements"):
        masked_action_mse(prediction, target, mask)


def test_runtime_plan_and_env_profile_should_fail_closed() -> None:
    """验证运行计划和环境 profile 默认不激活重型能力。"""
    plan = RuntimePlan(mode="metadata_only", device_policy="metadata_only")
    assert plan.to_json_dict()["distributed_enabled"] is False

    with pytest.raises(ValueError, match="slurm_enabled"):
        RuntimePlan(mode="local_cpu_smoke", slurm_enabled=True)

    profile = EnvProfile.model_gr00t_n1d6_future()
    with pytest.raises(RuntimeError, match="AUTOVLA_GR00T_SOURCE_ROOT"):
        profile.validate({})
    with pytest.raises(RuntimeError, match="WANDB_API_KEY"):
        EnvProfile.metadata_only().validate({"WANDB_API_KEY": "secret-like-but-not-real"})


def test_checkpoint_manifest_should_roundtrip_compatibility() -> None:
    """验证 checkpoint manifest 只记录兼容性元数据。"""
    spec = CheckpointCompatibilitySpec(
        model_family_key="gr00t-n1d6",
        model_registry_key="gr00t-n1d6",
        dataset_fingerprint="dataset",
        transform_fingerprint="transform",
        statistics_fingerprint="stats",
        action_horizon=4,
        action_dim=3,
    )
    manifest = TrainingCheckpointManifest(run_id="run-a", step=7, compatibility=spec)

    assert manifest.validate_resume(spec) == 7
    payload = manifest.to_json_dict()
    assert payload["schema_version"] == "autovla.training_checkpoint_manifest.v1"
    assert payload["compatibility"] == {
        "model_family_key": "gr00t-n1d6",
        "model_registry_key": "gr00t-n1d6",
        "dataset_fingerprint": "dataset",
        "transform_fingerprint": "transform",
        "statistics_fingerprint": "stats",
        "action_horizon": 4,
        "action_dim": 3,
    }
    with pytest.raises(ValueError, match="compatibility mismatch"):
        manifest.validate_resume(
            CheckpointCompatibilitySpec(
                model_family_key="gr00t-n1d6",
                model_registry_key="gr00t-n1d6",
                dataset_fingerprint="other",
                transform_fingerprint="transform",
                statistics_fingerprint="stats",
                action_horizon=4,
                action_dim=3,
            )
        )


def test_efficiency_telemetry_should_serialize_deterministically() -> None:
    """验证效率遥测 JSON 稳定且字段覆盖 data/compute split。"""
    telemetry = EfficiencyTelemetry(
        samples_per_second=8.0,
        batches_per_second=2.0,
        batch_latency_ms_p50=11.0,
        batch_latency_ms_p95=19.0,
        data_wait_time_ms=3.0,
        collate_time_ms=1.0,
        adapter_time_ms=2.0,
        forward_time_ms=4.0,
        loss_time_ms=0.5,
        checkpoint_manifest_time_ms=0.25,
        memory_envelope_mb=128.0,
    )

    first = telemetry.to_stable_json()
    second = telemetry.to_stable_json()

    assert first == second
    payload = json.loads(first)
    assert payload["data_wait_time_ms"] == 3.0
    assert payload["forward_time_ms"] == 4.0
    assert payload["checkpoint_manifest_time_ms"] == 0.25
