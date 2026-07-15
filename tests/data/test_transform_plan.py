"""R3 有序可逆变换计划测试。"""

from __future__ import annotations

import numpy as np

from autovla.core.semantics import (
    AlignmentMode,
    AlignmentPolicy,
    MaskKind,
    TensorLayout,
)
from autovla.data.normalization import FeatureStatistics
from autovla.data.transforms import (
    ExecutionSide,
    FeatureRenameStage,
    NormalizeStage,
    PaddingStage,
    RelativeActionStage,
    SemanticMask,
    TemporalAlignmentStage,
    TransformPlan,
)


def test_should_execute_relative_then_normalize_and_inverse_in_reverse_order() -> None:
    """验证相对动作正序和反归一化/绝对动作逆序严格配对。"""
    stats = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([0.0, 0.0]),
        std=np.asarray([2.0, 4.0]),
    )
    plan = TransformPlan(
        (
            RelativeActionStage(
                action_dimensions=(0, 1),
                state_indices=(1, 2),
            ),
            NormalizeStage(
                "actions",
                stats,
                TensorLayout.time_feature(),
                AlignmentPolicy(AlignmentMode.BROADCAST),
            ),
        )
    )
    sample = {
        "actions": np.asarray([[12.0, 24.0], [14.0, 28.0]], dtype=np.float32),
        "state": np.asarray([1.0, 10.0, 20.0], dtype=np.float32),
    }
    transformed = plan.forward(sample)
    np.testing.assert_allclose(np.asarray(transformed["actions"]), [[1.0, 1.0], [2.0, 2.0]])
    restored = plan.inverse(transformed)
    np.testing.assert_allclose(np.asarray(restored["actions"]), sample["actions"])


def test_should_roundtrip_previous_action_delta() -> None:
    """验证 previous-action delta 首步保留绝对值并可逆。"""
    stage = RelativeActionStage(mode="previous_delta")
    actions = np.asarray([[1.0, 2.0], [3.0, 5.0], [6.0, 9.0]], dtype=np.float32)
    relative = stage.forward({"actions": actions})
    np.testing.assert_allclose(
        np.asarray(relative["actions"]), [[1.0, 2.0], [2.0, 3.0], [3.0, 4.0]]
    )
    np.testing.assert_allclose(np.asarray(stage.inverse(relative)["actions"]), actions)


def test_should_keep_temporal_and_padding_masks_distinct() -> None:
    """验证时间有效性和 padding 有效性保持不同类别与布局。"""
    temporal = TemporalAlignmentStage(
        feature="actions",
        source_layout=TensorLayout.time_feature(),
        indices=(1, 0),
        source_length=2,
        mask_feature="temporal_mask",
    )
    padding = PaddingStage(
        feature="actions",
        layout=TensorLayout.time_feature(),
        source_shape=(2, 2),
        target_shape=(2, 3),
        mask_feature="padding_mask",
    )
    plan = TransformPlan((temporal, padding))
    output = plan.forward({"actions": np.asarray([[1.0, 2.0], [3.0, 4.0]])})
    temporal_mask = output["temporal_mask"]
    padding_mask = output["padding_mask"]
    assert isinstance(temporal_mask, SemanticMask)
    assert isinstance(padding_mask, SemanticMask)
    assert temporal_mask.semantics.kind is MaskKind.TEMPORAL
    assert padding_mask.semantics.kind is MaskKind.PADDING
    assert temporal_mask.values.shape == (2,)
    assert padding_mask.values.shape == (2, 3)
    restored = plan.inverse(output)
    np.testing.assert_allclose(np.asarray(restored["actions"]), [[1.0, 2.0], [3.0, 4.0]])


def test_plan_fingerprint_should_include_order_parameters_and_statistics() -> None:
    """验证计划指纹确定且对顺序、参数和统计内容敏感。"""
    first = TransformPlan((FeatureRenameStage("a", "b"),))
    same = TransformPlan((FeatureRenameStage("a", "b"),))
    changed = TransformPlan((FeatureRenameStage("a", "c"),))
    assert first.fingerprint == same.fingerprint
    assert first.fingerprint != changed.fingerprint
    assert first.to_json_dict()["stages"][0]["name"] == "feature_rename"  # type: ignore[index]


def test_stage_descriptor_should_publish_complete_shared_contract() -> None:
    """验证阶段统一声明输入输出、可逆性、依赖、掩码和执行侧。"""
    stage = RelativeActionStage(
        action_dimensions=(0,),
        state_indices=(1,),
        execution_side=ExecutionSide.FAMILY_PROCESSOR,
    )
    descriptor = stage.to_json_dict()["descriptor"]
    assert isinstance(descriptor, dict)
    assert descriptor["required_inputs"][0]["name"] == "actions"
    assert descriptor["produced_outputs"][0]["name"] == "actions"
    assert descriptor["reversible"] is True
    assert descriptor["state_dependencies"] == ["state"]
    assert descriptor["statistics_dependencies"] == []
    assert descriptor["mask_behavior"] == []
    assert descriptor["execution_side"] == "family_processor"
