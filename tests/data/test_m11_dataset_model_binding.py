"""M11 数据集—模型物理语义绑定的聚焦契约测试。"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from autovla.data.binding import (
    ActionBinding,
    CameraBinding,
    DatasetCompatibilityLevel,
    DatasetModelBinding,
    DatasetSchema,
    EmbodimentSchema,
    LanguageBinding,
    ModelInputSchema,
    NormalizationBinding,
    PhysicalFeatureSpec,
    StateBinding,
    TemporalBinding,
    canonical_serialize,
    evaluate_compatibility,
)

DATASET_FINGERPRINT = "a" * 64
STATISTICS_FINGERPRINT = "b" * 64


def _feature(
    key: str,
    *,
    modality: str,
    units: str = "rad",
    required: bool = True,
) -> PhysicalFeatureSpec:
    """创建已知或故意未知的二维物理特征。"""
    return PhysicalFeatureSpec(
        semantic_key=key,
        dimension=2,
        units=units,
        coordinate_frame="robot_base",
        reference_frame="joint_zero",
        ordering=(f"{key}.0", f"{key}.1"),
        modality=modality,
        representation="joint_position",
        source_indices=(0, 1),
        required=required,
        valid_range=(-3.2, 3.2),
    )


def build_binding_fixture(
    level: DatasetCompatibilityLevel,
    *,
    projected: bool = False,
    unknown_units: bool = False,
    filled_fields: tuple[str, ...] = (),
) -> DatasetModelBinding:
    """构造小型、后端中立且物理语义完整的绑定。"""
    state = _feature(
        "joint_state",
        modality="state",
        units="unknown" if unknown_units else "rad",
    )
    action = _feature("joint_action", modality="action")
    embodiment = EmbodimentSchema(
        embodiment_id="demo-arm",
        version="1",
        physical_features=(state, action),
        joint_order=("shoulder", "elbow"),
        eef_order=("tool_center",),
        camera_mounts=(("front", "base_front"), ("wrist", "right_wrist")),
        coordinate_conventions=("right_handed", "xyzw_quaternion"),
        projector_id="demo-projector-v1" if projected else "identity",
    )
    dataset = DatasetSchema(
        dataset_id="fixture-dataset",
        version="1",
        source_format="in_memory_contract",
        immutable_dataset_fingerprint=DATASET_FINGERPRINT,
        embodiment=embodiment,
        features=(state, action),
        camera_names=("front", "wrist"),
        language_semantics="task_instruction",
        sample_rate_hz=30.0,
        history=1,
        horizon=3,
        action_mode="absolute_joint_position",
        normalization_axes=(0,),
        normalization_stats_fingerprint=STATISTICS_FINGERPRINT,
        padding_policy="masked_right_padding",
        mask_fields=("camera_mask", "state_mask", "action_mask", "temporal_mask"),
    )
    model = ModelInputSchema(
        family_id="fixture-family",
        version="1",
        source_pin="0123456789abcdef",
        embodiment_id="demo-arm",
        projector_id="demo-projector-v1" if projected else "identity",
        camera_names=("primary", "wrist") if projected else ("front", "wrist"),
        language_semantics="task_instruction",
        state_features=(state,),
        action_features=(action,),
        state_dimension=4,
        action_dimension=4,
        sample_rate_hz=30.0,
        history=1,
        horizon=3,
        action_mode="absolute_joint_position",
        normalization_axes=(0,),
        normalization_stats_fingerprint=STATISTICS_FINGERPRINT,
        padding_policy="masked_right_padding",
        mask_fields=("camera_mask", "state_mask", "action_mask", "temporal_mask"),
    )
    return DatasetModelBinding(
        binding_id=f"fixture-{level.value}",
        schema_version="autovla.dataset_model_binding.v1",
        dataset_schema=dataset,
        model_schema=model,
        embodiment_id="demo-arm",
        projector_id="demo-projector-v1" if projected else "identity",
        camera_bindings=(
            CameraBinding(
                dataset_camera="front",
                model_camera="primary" if projected else "front",
                dataset_index=0,
                model_index=0,
                mount="base_front",
                projection="resize_224" if projected else "identity",
            ),
            CameraBinding(
                dataset_camera="wrist",
                model_camera="wrist",
                dataset_index=1,
                model_index=1,
                mount="right_wrist",
            ),
        ),
        language_binding=LanguageBinding(
            dataset_key="task",
            model_key="prompt",
            semantics="task_instruction",
            formatter_id="identity",
            tokenizer_owner="family",
            truncation_limit=128,
        ),
        state_binding=StateBinding(
            source_features=("joint_state",),
            target_features=("joint_state",),
            source_indices=(0, 1),
            target_indices=(0, 1),
            projector_id="demo-projector-v1" if projected else "identity",
            projected_fields=("joint_state",) if projected else (),
            filled_fields=filled_fields,
        ),
        action_binding=ActionBinding(
            source_features=("joint_action",),
            target_features=("joint_action",),
            source_indices=(2, 3),
            target_indices=(0, 1),
            action_mode="absolute_joint_position",
            projector_id="identity",
            inverse_mapping="identity",
        ),
        temporal_binding=TemporalBinding(
            source_sample_rate_hz=30.0,
            model_sample_rate_hz=30.0,
            history=1,
            horizon=3,
            source_offsets=(0, 1, 2),
            model_offsets=(0, 1, 2),
            anchor="observation_time",
            boundary_policy="mask_and_forbid_cross_episode",
            mask_key="temporal_mask",
        ),
        normalization_binding=NormalizationBinding(
            method="mean_std",
            statistics_fingerprint=STATISTICS_FINGERPRINT,
            axes=(0,),
            feature_names=("joint_state", "joint_action"),
            owner="dataset_binding",
            scope="immutable_dataset",
            constant_policy="identity",
            padding_identity=True,
        ),
        accepted_level=level,
        filled_fields=filled_fields,
        projected_fields=("joint_state",) if projected else (),
    )


def test_all_four_compatibility_levels_are_exact_and_reachable() -> None:
    """四个规范值必须保持精确拼写并由确定性判定覆盖。"""
    assert tuple(item.value for item in DatasetCompatibilityLevel) == (
        "exact",
        "explicit_projection",
        "contract_fixture_only",
        "incompatible",
    )
    assert evaluate_compatibility(build_binding_fixture(DatasetCompatibilityLevel.EXACT)).level is (
        DatasetCompatibilityLevel.EXACT
    )
    projected = evaluate_compatibility(
        build_binding_fixture(DatasetCompatibilityLevel.EXPLICIT_PROJECTION, projected=True)
    )
    assert projected.level is DatasetCompatibilityLevel.EXPLICIT_PROJECTION
    assert projected.projected_fields == ("joint_state",)
    assert any(item.startswith("camera:front->primary") for item in projected.transforms)
    fixture = evaluate_compatibility(
        build_binding_fixture(DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY)
    )
    assert fixture.level is DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY
    assert fixture.real_data_validated is False
    incompatible = evaluate_compatibility(
        build_binding_fixture(DatasetCompatibilityLevel.INCOMPATIBLE)
    )
    assert incompatible.level is DatasetCompatibilityLevel.INCOMPATIBLE
    assert "DECLARED_INCOMPATIBLE" in incompatible.reason_codes


def test_unknown_required_physical_semantics_fail_closed() -> None:
    """未知必需单位不得被 padding、零值或声明等级掩盖。"""
    report = evaluate_compatibility(
        build_binding_fixture(DatasetCompatibilityLevel.EXACT, unknown_units=True)
    )
    assert report.level is DatasetCompatibilityLevel.INCOMPATIBLE
    assert any(code.startswith("UNKNOWN_REQUIRED_SEMANTICS") for code in report.reason_codes)
    assert report.batch_factory_allowed is False
    assert report.real_data_validated is False


def test_required_field_fill_is_incompatible_not_projection() -> None:
    """必需字段的零值/填充合成不能伪装成显式投影。"""
    report = evaluate_compatibility(
        build_binding_fixture(
            DatasetCompatibilityLevel.EXPLICIT_PROJECTION,
            projected=True,
            filled_fields=("joint_state",),
        )
    )
    assert report.level is DatasetCompatibilityLevel.INCOMPATIBLE
    assert "REQUIRED_FIELD_SYNTHESIS_FORBIDDEN:joint_state" in report.reason_codes


def test_serialization_and_fingerprints_are_canonical_and_immutable() -> None:
    """同一不可变契约应产生完全相同的规范 JSON 和 SHA-256。"""
    first = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    second = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    assert canonical_serialize(first) == canonical_serialize(second)
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
    assert first.immutable_dataset_fingerprint == DATASET_FINGERPRINT
    with pytest.raises(FrozenInstanceError):
        first.binding_id = "mutated"  # type: ignore[misc]


def test_strict_validation_rejects_bool_nonfinite_duplicate_and_unknown_values() -> None:
    """构造边界必须拒绝模糊 int/bool、非有限值、重复项和未知等级。"""
    with pytest.raises(ValueError, match="dimension"):
        PhysicalFeatureSpec(
            semantic_key="bad",
            dimension=True,  # type: ignore[arg-type]
            units="rad",
            coordinate_frame="base",
            reference_frame="zero",
            ordering=("x",),
        )
    with pytest.raises(ValueError, match="valid_range"):
        PhysicalFeatureSpec(
            semantic_key="bad",
            dimension=1,
            units="rad",
            coordinate_frame="base",
            reference_frame="zero",
            ordering=("x",),
            valid_range=(0.0, float("inf")),
        )
    with pytest.raises(ValueError, match="duplicates"):
        PhysicalFeatureSpec(
            semantic_key="bad",
            dimension=2,
            units="rad",
            coordinate_frame="base",
            reference_frame="zero",
            ordering=("x", "x"),
        )
    with pytest.raises(ValueError, match="unknown compatibility"):
        replace(
            build_binding_fixture(DatasetCompatibilityLevel.EXACT),
            accepted_level="projected",  # type: ignore[arg-type]
        )
