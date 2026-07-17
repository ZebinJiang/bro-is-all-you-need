"""数据集—模型物理契约的确定性、失败关闭兼容性判定。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from autovla.data.binding.contracts import (
    DatasetCompatibilityLevel,
    DatasetCompatibilityReport,
    DatasetModelBinding,
    PhysicalFeatureSpec,
    semantics_unknown,
)


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    """按首次出现顺序去重原因和变换。"""
    return tuple(dict.fromkeys(values))


def _physical_semantics_equal(left: PhysicalFeatureSpec, right: PhysicalFeatureSpec) -> bool:
    """比较会影响物理解释的字段,不比较物理存储索引。"""
    return (
        left.semantic_key == right.semantic_key
        and left.dimension == right.dimension
        and left.units == right.units
        and left.coordinate_frame == right.coordinate_frame
        and left.reference_frame == right.reference_frame
        and left.ordering == right.ordering
        and left.modality == right.modality
        and left.dtype == right.dtype
        and left.representation == right.representation
    )


def _unknown_required_semantics(binding: DatasetModelBinding) -> tuple[str, ...]:
    """收集所有必需但未知的物理、语言、动作、安装和时序语义。"""
    unknown: list[str] = []
    for namespace, specs in (
        ("dataset", binding.dataset_schema.features),
        ("model.state", binding.model_schema.state_features),
        ("model.action", binding.model_schema.action_features),
    ):
        unknown.extend(
            f"{namespace}:{spec.semantic_key}"
            for spec in specs
            if spec.has_unknown_required_semantics
        )
    textual = (
        ("dataset.language", binding.dataset_schema.language_semantics),
        ("model.language", binding.model_schema.language_semantics),
        ("language.binding", binding.language_binding.semantics),
        ("dataset.action_mode", binding.dataset_schema.action_mode),
        ("model.action_mode", binding.model_schema.action_mode),
        ("action.binding", binding.action_binding.action_mode),
        ("temporal.anchor", binding.temporal_binding.anchor),
        ("temporal.boundary", binding.temporal_binding.boundary_policy),
        ("normalization.method", binding.normalization_binding.method),
    )
    unknown.extend(name for name, value in textual if semantics_unknown(value))
    for camera in binding.camera_bindings:
        if camera.required and semantics_unknown(camera.mount):
            unknown.append(f"camera.mount:{camera.dataset_camera}")
    return _ordered_unique(unknown)


def _mapping_errors(binding: DatasetModelBinding) -> tuple[str, ...]:
    """验证字段存在、相机顺序、维度范围以及禁止的必需字段合成/丢弃。"""
    errors: list[str] = []
    dataset_features = {item.semantic_key: item for item in binding.dataset_schema.features}
    embodiment_features = {
        item.semantic_key: item for item in binding.dataset_schema.embodiment.physical_features
    }
    model_state = {item.semantic_key: item for item in binding.model_schema.state_features}
    model_action = {item.semantic_key: item for item in binding.model_schema.action_features}

    for key in binding.state_binding.source_features:
        if key not in dataset_features:
            errors.append(f"UNKNOWN_STATE_SOURCE:{key}")
    for key in binding.action_binding.source_features:
        if key not in dataset_features:
            errors.append(f"UNKNOWN_ACTION_SOURCE:{key}")
    for key in binding.state_binding.target_features:
        if key not in model_state:
            errors.append(f"UNKNOWN_STATE_TARGET:{key}")
    for key in binding.action_binding.target_features:
        if key not in model_action:
            errors.append(f"UNKNOWN_ACTION_TARGET:{key}")
    for key, feature in dataset_features.items():
        embodiment_feature = embodiment_features.get(key)
        if embodiment_feature is None:
            errors.append(f"FEATURE_MISSING_FROM_EMBODIMENT:{key}")
        elif not _physical_semantics_equal(feature, embodiment_feature):
            errors.append(f"EMBODIMENT_FEATURE_SEMANTICS_MISMATCH:{key}")

    dataset_width = sum(item.dimension for item in binding.dataset_schema.features)
    if max(binding.state_binding.source_indices) >= dataset_width:
        errors.append("STATE_SOURCE_INDEX_OUT_OF_RANGE")
    if max(binding.action_binding.source_indices) >= dataset_width:
        errors.append("ACTION_SOURCE_INDEX_OUT_OF_RANGE")
    if max(binding.state_binding.target_indices) >= binding.model_schema.state_dimension:
        errors.append("STATE_TARGET_INDEX_OUT_OF_RANGE")
    if max(binding.action_binding.target_indices) >= binding.model_schema.action_dimension:
        errors.append("ACTION_TARGET_INDEX_OUT_OF_RANGE")

    dataset_cameras = binding.dataset_schema.camera_names
    model_cameras = binding.model_schema.camera_names
    for camera in binding.camera_bindings:
        if camera.dataset_camera not in dataset_cameras:
            errors.append(f"UNKNOWN_DATASET_CAMERA:{camera.dataset_camera}")
        elif camera.dataset_index >= len(dataset_cameras):
            errors.append(f"DATASET_CAMERA_INDEX_OUT_OF_RANGE:{camera.dataset_camera}")
        elif dataset_cameras[camera.dataset_index] != camera.dataset_camera:
            errors.append(f"DATASET_CAMERA_ORDER_MISMATCH:{camera.dataset_camera}")
        if camera.model_camera not in model_cameras:
            errors.append(f"UNKNOWN_MODEL_CAMERA:{camera.model_camera}")
        elif camera.model_index >= len(model_cameras):
            errors.append(f"MODEL_CAMERA_INDEX_OUT_OF_RANGE:{camera.model_camera}")
        elif model_cameras[camera.model_index] != camera.model_camera:
            errors.append(f"MODEL_CAMERA_ORDER_MISMATCH:{camera.model_camera}")
    required_model_cameras = set(model_cameras)
    bound_model_cameras = {item.model_camera for item in binding.camera_bindings if item.required}
    if required_model_cameras != bound_model_cameras:
        errors.append("REQUIRED_CAMERA_BINDING_INCOMPLETE")

    mounts = dict(binding.dataset_schema.embodiment.camera_mounts)
    for camera in binding.camera_bindings:
        expected_mount = mounts.get(camera.dataset_camera)
        if expected_mount is None:
            errors.append(f"CAMERA_MOUNT_UNREGISTERED:{camera.dataset_camera}")
        elif expected_mount != camera.mount:
            errors.append(f"CAMERA_MOUNT_MISMATCH:{camera.dataset_camera}")

    dropped = set(binding.dropped_fields)
    dropped.update(binding.state_binding.dropped_fields)
    dropped.update(binding.action_binding.dropped_fields)
    filled = set(binding.filled_fields)
    filled.update(binding.state_binding.filled_fields)
    filled.update(binding.action_binding.filled_fields)
    for key in dropped:
        source = dataset_features.get(key)
        if source is None:
            errors.append(f"UNKNOWN_DROPPED_FIELD:{key}")
        elif source.required:
            errors.append(f"REQUIRED_FIELD_DROP_FORBIDDEN:{key}")
    for key in filled:
        target = model_state.get(key) or model_action.get(key)
        if target is None:
            errors.append(f"UNKNOWN_FILLED_FIELD:{key}")
        elif target.required:
            errors.append(f"REQUIRED_FIELD_SYNTHESIS_FORBIDDEN:{key}")

    if binding.embodiment_id != binding.dataset_schema.embodiment.embodiment_id:
        errors.append("DATASET_EMBODIMENT_MISMATCH")
    if binding.embodiment_id != binding.model_schema.embodiment_id:
        errors.append("MODEL_EMBODIMENT_MISMATCH")
    if not binding.temporal_binding.forbid_episode_crossing:
        errors.append("EPISODE_CROSSING_NOT_FORBIDDEN")
    if binding.action_binding.action_mode != binding.dataset_schema.action_mode:
        errors.append("DATASET_ACTION_MODE_MISMATCH")
    if binding.action_binding.action_mode != binding.model_schema.action_mode:
        errors.append("MODEL_ACTION_MODE_MISMATCH")
    if binding.language_binding.semantics != binding.dataset_schema.language_semantics:
        errors.append("DATASET_LANGUAGE_SEMANTICS_MISMATCH")
    if binding.language_binding.semantics != binding.model_schema.language_semantics:
        errors.append("MODEL_LANGUAGE_SEMANTICS_MISMATCH")
    temporal = binding.temporal_binding
    if temporal.source_sample_rate_hz != binding.dataset_schema.sample_rate_hz:
        errors.append("DATASET_SAMPLE_RATE_MISMATCH")
    if temporal.model_sample_rate_hz != binding.model_schema.sample_rate_hz:
        errors.append("MODEL_SAMPLE_RATE_MISMATCH")
    if temporal.history != binding.model_schema.history:
        errors.append("MODEL_HISTORY_MISMATCH")
    if temporal.horizon != binding.model_schema.horizon:
        errors.append("MODEL_HORIZON_MISMATCH")
    if len(temporal.source_offsets) != binding.dataset_schema.horizon:
        errors.append("DATASET_TEMPORAL_OFFSET_COUNT_MISMATCH")
    if len(temporal.model_offsets) != binding.model_schema.horizon:
        errors.append("MODEL_TEMPORAL_OFFSET_COUNT_MISMATCH")
    if binding.normalization_binding.statistics_fingerprint != (
        binding.dataset_schema.normalization_stats_fingerprint
    ):
        errors.append("DATASET_NORMALIZATION_RECEIPT_MISMATCH")
    if binding.normalization_binding.statistics_fingerprint != (
        binding.model_schema.normalization_stats_fingerprint
    ):
        errors.append("MODEL_NORMALIZATION_RECEIPT_MISMATCH")
    if binding.normalization_binding.axes != binding.dataset_schema.normalization_axes:
        errors.append("DATASET_NORMALIZATION_AXES_MISMATCH")
    if binding.normalization_binding.axes != binding.model_schema.normalization_axes:
        errors.append("MODEL_NORMALIZATION_AXES_MISMATCH")
    if not binding.normalization_binding.padding_identity:
        errors.append("NORMALIZATION_PADDING_NOT_IDENTITY")
    dataset_masks = set(binding.dataset_schema.mask_fields)
    model_masks = set(binding.model_schema.mask_fields)
    required_masks = {
        binding.state_binding.mask_key,
        binding.action_binding.mask_key,
        binding.temporal_binding.mask_key,
        *(item.mask_key for item in binding.camera_bindings),
    }
    if not required_masks.issubset(dataset_masks):
        errors.append("DATASET_MASK_DECLARATION_INCOMPLETE")
    if not required_masks.issubset(model_masks):
        errors.append("MODEL_MASK_DECLARATION_INCOMPLETE")
    return _ordered_unique(errors)


def _projection_transforms(binding: DatasetModelBinding) -> tuple[str, ...]:
    """返回所有非恒等投影、重命名、时序和 padding 变换。"""
    transforms: list[str] = []
    if binding.projector_id != "identity" or binding.model_schema.projector_id != "identity":
        transforms.append(f"projector:{binding.projector_id}")
    for camera in binding.camera_bindings:
        if (
            camera.dataset_camera != camera.model_camera
            or camera.dataset_index != camera.model_index
            or camera.projection != "identity"
        ):
            transforms.append(
                f"camera:{camera.dataset_camera}->{camera.model_camera}:{camera.projection}"
            )
    if binding.state_binding.projector_id != "identity":
        transforms.append(f"state:{binding.state_binding.projector_id}")
    if binding.action_binding.projector_id != "identity":
        transforms.append(f"action:{binding.action_binding.projector_id}")
    if binding.action_binding.inverse_mapping != "identity":
        transforms.append(f"action_inverse:{binding.action_binding.inverse_mapping}")
    temporal = binding.temporal_binding
    if (
        temporal.source_sample_rate_hz != temporal.model_sample_rate_hz
        or temporal.source_offsets != temporal.model_offsets
        or binding.dataset_schema.history != binding.model_schema.history
        or binding.dataset_schema.horizon != binding.model_schema.horizon
    ):
        transforms.append("temporal:explicit_resample_or_window_projection")
    if binding.dataset_schema.normalization_axes != binding.model_schema.normalization_axes:
        transforms.append("normalization:axis_projection")
    if binding.dataset_schema.padding_policy != binding.model_schema.padding_policy:
        transforms.append("padding:policy_projection")
    transforms.extend(f"field:{name}" for name in binding.projected_fields)
    transforms.extend(f"field:{name}" for name in binding.state_binding.projected_fields)
    transforms.extend(f"field:{name}" for name in binding.action_binding.projected_fields)
    transforms.extend(f"drop:{name}" for name in binding.dropped_fields)
    transforms.extend(f"fill:{name}" for name in binding.filled_fields)
    return _ordered_unique(transforms)


def _feature_projection_errors(binding: DatasetModelBinding) -> tuple[str, ...]:
    """要求非同一物理特征映射由显式 projected_fields 覆盖。"""
    dataset = {item.semantic_key: item for item in binding.dataset_schema.features}
    model = {
        item.semantic_key: item
        for item in (*binding.model_schema.state_features, *binding.model_schema.action_features)
    }
    declared = set(binding.projected_fields)
    declared.update(binding.state_binding.projected_fields)
    declared.update(binding.action_binding.projected_fields)
    errors: list[str] = []
    for sources, targets in (
        (binding.state_binding.source_features, binding.state_binding.target_features),
        (binding.action_binding.source_features, binding.action_binding.target_features),
    ):
        if len(sources) != len(targets):
            errors.append("FEATURE_MAPPING_ARITY_MISMATCH")
            continue
        for source_key, target_key in zip(sources, targets, strict=True):
            source = dataset.get(source_key)
            target = model.get(target_key)
            if source is None or target is None:
                continue
            if not _physical_semantics_equal(source, target) and (
                source_key not in declared and target_key not in declared
            ):
                errors.append(f"UNDECLARED_PHYSICAL_PROJECTION:{source_key}->{target_key}")
    return _ordered_unique(errors)


def evaluate_compatibility(binding: DatasetModelBinding) -> DatasetCompatibilityReport:
    """从完整绑定推导四级兼容性;任何未知必需语义均返回 incompatible。"""
    if not isinstance(cast(object, binding), DatasetModelBinding):
        raise TypeError("binding must be DatasetModelBinding")
    reasons: list[str] = []
    unknown = _unknown_required_semantics(binding)
    if unknown:
        reasons.extend(f"UNKNOWN_REQUIRED_SEMANTICS:{name}" for name in unknown)
    reasons.extend(_mapping_errors(binding))
    reasons.extend(_feature_projection_errors(binding))

    transforms = _projection_transforms(binding)
    derived = DatasetCompatibilityLevel.EXACT
    if binding.accepted_level is DatasetCompatibilityLevel.INCOMPATIBLE:
        reasons.append("DECLARED_INCOMPATIBLE")
    if reasons:
        derived = DatasetCompatibilityLevel.INCOMPATIBLE
    elif binding.accepted_level is DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY:
        derived = DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY
    elif transforms:
        derived = DatasetCompatibilityLevel.EXPLICIT_PROJECTION

    if (
        derived is not DatasetCompatibilityLevel.INCOMPATIBLE
        and binding.accepted_level is not derived
    ):
        reasons.append(f"DECLARED_LEVEL_MISMATCH:{binding.accepted_level.value}->{derived.value}")
        derived = DatasetCompatibilityLevel.INCOMPATIBLE

    dropped = _ordered_unique(
        (
            *binding.dropped_fields,
            *binding.state_binding.dropped_fields,
            *binding.action_binding.dropped_fields,
        )
    )
    filled = _ordered_unique(
        (
            *binding.filled_fields,
            *binding.state_binding.filled_fields,
            *binding.action_binding.filled_fields,
        )
    )
    projected = _ordered_unique(
        (
            *binding.projected_fields,
            *binding.state_binding.projected_fields,
            *binding.action_binding.projected_fields,
        )
    )
    warnings = ("SCHEMA_COMPATIBILITY_ONLY_NOT_RUNTIME_OR_MODEL_QUALITY_EVIDENCE",)
    return DatasetCompatibilityReport(
        level=derived,
        binding_fingerprint=binding.fingerprint,
        dataset_schema_fingerprint=binding.dataset_schema.fingerprint,
        model_schema_fingerprint=binding.model_schema.fingerprint,
        immutable_dataset_fingerprint=binding.immutable_dataset_fingerprint,
        reason_codes=_ordered_unique(reasons),
        transforms=transforms,
        dropped_fields=dropped,
        filled_fields=filled,
        projected_fields=projected,
        warnings=warnings,
        batch_factory_allowed=derived is not DatasetCompatibilityLevel.INCOMPATIBLE,
        real_data_validated=False,
    )


__all__ = ["evaluate_compatibility"]
