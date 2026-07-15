"""M10 变换图约束与共享 SE(3) 往返测试。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import numpy as np
import pytest

from autovla.core.semantics import MaskKind, MaskSemantics, TensorLayout
from autovla.data.transforms import (
    CurrentStateReference,
    FeatureContract,
    FeatureRenameStage,
    RotationRepresentation,
    SE3FrameConvention,
    SE3RelativeActionTransform,
    SE3TypedParameter,
    SemanticMask,
    StageDescriptor,
    TransformPlan,
)


@dataclass(frozen=True, slots=True)
class _DescriptorStage:
    """为图校验提供无数值副作用的聚焦阶段。"""

    name: str
    descriptor: StageDescriptor
    stage_id: str

    def forward(self, features: Mapping[str, object]) -> dict[str, object]:
        """复制输入映射。"""

        return dict(features)

    def inverse(self, features: Mapping[str, object]) -> dict[str, object]:
        """复制输入映射。"""

        return dict(features)

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定测试描述。"""

        return {
            "name": self.name,
            "stage_id": self.stage_id,
            "descriptor": self.descriptor.to_json_dict(),
        }


def test_transform_plan_rejects_duplicate_order_collision_and_inverse_gap() -> None:
    """图构造阶段关闭重复身份、逆序依赖、无消费覆盖和不可逆计划。"""

    repeated_type = TransformPlan(
        (
            FeatureRenameStage("a", "b", stage_id="rename_a_to_b"),
            FeatureRenameStage("b", "c", stage_id="rename_b_to_c"),
        )
    )
    assert [stage.stage_id for stage in repeated_type.stages] == [
        "rename_a_to_b",
        "rename_b_to_c",
    ]
    with pytest.raises(ValueError, match="identifiers must be unique"):
        TransformPlan(
            (
                FeatureRenameStage("a", "b", stage_id="duplicate"),
                FeatureRenameStage("b", "c", stage_id="duplicate"),
            )
        )
    with pytest.raises(ValueError, match="before it is produced"):
        TransformPlan(
            (
                FeatureRenameStage("b", "c", stage_id="consume_b"),
                FeatureRenameStage("a", "b", stage_id="produce_b"),
            )
        )

    producer = _DescriptorStage(
        "descriptor",
        StageDescriptor((), (FeatureContract("x", TensorLayout.feature()),), True),
        "first",
    )
    collision = _DescriptorStage(
        "descriptor",
        StageDescriptor((), (FeatureContract("x", TensorLayout.feature()),), True),
        "second",
    )
    with pytest.raises(ValueError, match="collides with output"):
        TransformPlan((producer, collision))

    incompatible = _DescriptorStage(
        "descriptor",
        StageDescriptor(
            (FeatureContract("x", TensorLayout.feature(4)),),
            (FeatureContract("y", TensorLayout.feature(4)),),
            True,
        ),
        "incompatible",
    )
    sized_producer = _DescriptorStage(
        "descriptor",
        StageDescriptor((), (FeatureContract("x", TensorLayout.feature(3)),), True),
        "sized_producer",
    )
    with pytest.raises(ValueError, match="incompatible semantic-key sizes"):
        TransformPlan((sized_producer, incompatible))

    irreversible = _DescriptorStage(
        "descriptor",
        StageDescriptor((), (FeatureContract("x", None),), False),
        "irreversible",
    )
    with pytest.raises(ValueError, match="not inverse-eligible"):
        TransformPlan((irreversible,)).inverse({})


@pytest.mark.parametrize(
    "frame",
    (SE3FrameConvention.REFERENCE_LOCAL, SE3FrameConvention.WORLD_DELTA),
)
def test_se3_axis_angle_roundtrip_mask_and_fingerprint(frame: SE3FrameConvention) -> None:
    """共享 NumPy SE(3) 在两种坐标约定下往返并绑定全部参数。"""

    stage = SE3RelativeActionTransform(
        frame_convention=frame,
        mask_feature="action_mask",
        parameters=(SE3TypedParameter("embodiment", "robot_a"),),
    )
    actions = np.asarray(
        [[1.2, -0.4, 0.7, 0.1, -0.2, 0.05], [0.8, 0.3, -0.5, -0.1, 0.2, 0.3]],
        dtype=np.float32,
    )
    state = np.asarray([0.4, -0.1, 0.2, 0.05, 0.1, -0.08], dtype=np.float32)
    mask = SemanticMask(
        np.ones_like(actions, dtype=np.bool_),
        MaskSemantics(MaskKind.ACTION_DIMENSION, TensorLayout.time_feature()),
    )
    plan = TransformPlan((stage,))
    relative = plan.forward({"actions": actions, "reference_state": state, "action_mask": mask})
    restored = plan.inverse(relative)
    np.testing.assert_allclose(
        np.asarray(restored["actions"], dtype=np.float64),
        actions,
        atol=stage.tolerances.roundtrip_atol,
    )
    stages_value = plan.to_json_dict()["stages"]
    assert isinstance(stages_value, list) and stages_value
    payload_value = cast(list[object], stages_value)[0]
    assert isinstance(payload_value, dict)
    payload = cast(dict[str, object], payload_value)
    assert payload["order"] == 0 and payload["stage_id"] == "se3_relative_action"
    assert (
        plan.fingerprint
        != TransformPlan(
            (SE3RelativeActionTransform(frame_convention=frame, dtype="float64"),)
        ).fingerprint
    )


def test_se3_quaternion_roundtrip_and_fail_closed_inputs() -> None:
    """四元数往返保持单位旋转, 并拒绝无效 norm、静态 mask 与动态 mask。"""

    stage = SE3RelativeActionTransform(
        action_rotation_indices=(3, 4, 5, 6),
        state_rotation_indices=(3, 4, 5, 6),
        rotation_representation=RotationRepresentation.QUATERNION_XYZW,
        valid_dimension_mask=(True,) * 7,
    )
    actions = np.asarray([[1.0, 2.0, 3.0, 0.0, 0.0, 0.2, 0.98]], dtype=np.float64)
    state = np.asarray([0.5, 0.0, 1.0, 0.1, 0.0, 0.0, 0.995], dtype=np.float64)
    restored = stage.inverse(stage.forward({"actions": actions, "reference_state": state}))
    restored_actions = np.asarray(restored["actions"], dtype=np.float64)
    np.testing.assert_allclose(restored_actions[:, :3], actions[:, :3], atol=1e-5)
    restored_quaternion = restored_actions[0, 3:]
    expected_quaternion = actions[0, 3:] / np.linalg.norm(actions[0, 3:])
    np.testing.assert_allclose(restored_quaternion, expected_quaternion, atol=1e-5)

    broken = actions.copy()
    broken[0, 3:] = 0.0
    with pytest.raises(ValueError, match="quaternion norm"):
        stage.forward({"actions": broken, "reference_state": state})
    with pytest.raises(ValueError, match="statically valid"):
        SE3RelativeActionTransform(valid_dimension_mask=(True, True, True, False, True, True))

    masked_stage = SE3RelativeActionTransform(mask_feature="action_mask")
    invalid_mask_values = np.ones((1, 6), dtype=np.bool_)
    invalid_mask_values[0, 5] = False
    invalid_mask = SemanticMask(
        invalid_mask_values,
        MaskSemantics(MaskKind.ACTION_DIMENSION, TensorLayout.time_feature()),
    )
    with pytest.raises(ValueError, match="valid at every transformed step"):
        masked_stage.forward(
            {
                "actions": np.zeros((1, 6), dtype=np.float32),
                "reference_state": np.zeros((6,), dtype=np.float32),
                "action_mask": invalid_mask,
            }
        )


def test_se3_rejects_unsupported_reference_complex_data_and_invalid_parameter() -> None:
    """共享 SE3 对未实现语义、复数物理量和越界参数类型 fail closed。"""

    with pytest.raises(ValueError, match="only explicit_feature"):
        SE3RelativeActionTransform(
            current_state_reference=CurrentStateReference.LAST_OBSERVED_STATE
        )
    stage = SE3RelativeActionTransform()
    with pytest.raises(ValueError, match="finite numeric data"):
        stage.forward(
            {
                "actions": np.zeros((1, 6), dtype=np.complex64),
                "reference_state": np.zeros((6,), dtype=np.float32),
            }
        )
    invalid_value = cast(str | int | float | bool, object())
    with pytest.raises(TypeError, match="exact JSON scalar"):
        SE3TypedParameter("invalid", invalid_value)
