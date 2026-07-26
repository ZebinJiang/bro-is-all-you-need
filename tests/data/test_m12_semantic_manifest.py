"""M12 严格语义清单、reader 收据和绑定 provenance 测试。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import cast

import pytest

from autovla.core.types.training import TrainingBatch
from autovla.data.backends.base import dataset_config_fingerprint
from autovla.data.binding import (
    BACKEND_READER_RECEIPT_SCHEMA,
    PROJECTION_RECEIPT_SCHEMA,
    ROW_VALIDATION_RECEIPT_SCHEMA,
    BackendReaderReceipt,
    DatasetCompatibilityLevel,
    DatasetModelRuntime,
    PhysicalProjectionReceipt,
    ProjectionMode,
    ReaderEvidenceClass,
    RowValidationReceipt,
    SemanticManifest,
    evaluate_compatibility,
    parse_semantic_manifest,
    sha256_fingerprint,
)
from tests.data.test_m11_dataset_model_binding import (
    DATASET_FINGERPRINT,
    STATISTICS_FINGERPRINT,
    build_binding_fixture,
)
from tests.data.test_m11_physical_batch_binding import (
    _batch,
    _config,
    _record,
    _sample_source,
)

PROJECTOR_IMPLEMENTATION_FINGERPRINT = "c" * 64


def _feature_mapping(
    semantic_key: str,
    *,
    source_field: str,
    modality: str,
    mask_field: str,
) -> dict[str, object]:
    """构造两维且物理语义完整的内存字段映射。"""
    return {
        "source_field": source_field,
        "semantic_key": semantic_key,
        "dimension": 2,
        "units": "rad",
        "coordinate_frame": "robot_base",
        "reference_frame": "joint_zero",
        "ordering": [f"{semantic_key}.0", f"{semantic_key}.1"],
        "modality": modality,
        "dtype": "float32",
        "representation": "joint_position",
        "source_indices": [0, 1],
        "required": True,
        "mask_field": mask_field,
        "valid_range": [-3.2, 3.2],
    }


def _manifest_mapping(
    *,
    projected: bool = False,
    backend: str = "lerobot_local",
) -> dict[str, object]:
    """构造不读文件的完整版本化语义清单。"""
    projector_id = "demo-projector-v1" if projected else "identity"
    mode = "explicit_projection" if projected else "identity"
    return {
        "schema_version": "autovla.semantic_manifest.v1",
        "dataset_id": "fixture-dataset",
        "dataset_version": "1",
        "source_format": "in_memory_contract",
        "immutable_dataset_fingerprint": DATASET_FINGERPRINT,
        "backend_key": backend,
        "source_revision": "source-revision-7",
        "store_revision": "store-revision-7",
        "features": [
            _feature_mapping(
                "joint_state",
                source_field="state",
                modality="state",
                mask_field="state_mask",
            ),
            _feature_mapping(
                "joint_action",
                source_field="action",
                modality="action",
                mask_field="action_mask",
            ),
        ],
        "embodiment": {
            "embodiment_id": "demo-arm",
            "version": "1",
            "joint_order": ["shoulder", "elbow"],
            "eef_order": ["tool_center"],
            "camera_mounts": [["front", "base_front"], ["wrist", "right_wrist"]],
            "coordinate_conventions": ["right_handed", "xyzw_quaternion"],
            "projector_id": projector_id,
        },
        "camera_names": ["front", "wrist"],
        "camera_mask_field": "camera_mask",
        "language_semantics": "task_instruction",
        "sample_rate_hz": 30.0,
        "history": 1,
        "horizon": 3,
        "action_mode": "absolute_joint_position",
        "temporal": {
            "state_offsets": [0],
            "action_offsets": [0, 1, 2],
            "anchor": "observation_time",
            "boundary_policy": "mask_and_forbid_cross_episode",
            "mask_field": "temporal_mask",
            "forbid_episode_crossing": True,
        },
        "normalization": {
            "method": "mean_std",
            "statistics_fingerprint": STATISTICS_FINGERPRINT,
            "axes": [0],
            "feature_names": ["joint_state", "joint_action"],
            "owner": "dataset_binding",
            "scope": "immutable_dataset",
            "constant_policy": "identity",
            "padding_identity": True,
        },
        "padding_policy": "masked_right_padding",
        "mask_fields": ["camera_mask", "state_mask", "action_mask", "temporal_mask"],
        "projector": {
            "mode": mode,
            "projector_id": projector_id,
            "version": "1",
            "implementation_fingerprint": PROJECTOR_IMPLEMENTATION_FINGERPRINT,
        },
        "backend_decision": "NO_BACKEND_WINNER",
    }


def _nested_mapping(parent: dict[str, object], key: str) -> dict[str, object]:
    """复制清单中的嵌套字符串键映射。"""
    value = parent[key]
    assert isinstance(value, Mapping)
    return dict(cast(Mapping[str, object], value))


def _feature_mappings(parent: dict[str, object]) -> list[dict[str, object]]:
    """复制清单字段列表以进行单点漂移测试。"""
    value = parent["features"]
    assert isinstance(value, list)
    result: list[dict[str, object]] = []
    for item in value:
        assert isinstance(item, Mapping)
        result.append(dict(cast(Mapping[str, object], item)))
    return result


def _manifest(
    *,
    projected: bool = False,
    backend: str = "lerobot_local",
) -> SemanticManifest:
    """解析测试清单并返回严格不可变对象。"""
    return parse_semantic_manifest(_manifest_mapping(projected=projected, backend=backend))


def _reader_receipt(
    manifest: SemanticManifest,
    *,
    source_revision: str | None = None,
    store_revision: str | None = None,
) -> BackendReaderReceipt:
    """构造一条真实行观察和 backend reader 的精确收据。"""
    config = _config(manifest.backend_key)
    source = _sample_source(config)
    semantic = manifest.receipt
    row = RowValidationReceipt(
        receipt_schema=ROW_VALIDATION_RECEIPT_SCHEMA,
        evidence_class=ReaderEvidenceClass.REAL_DATA,
        semantic_manifest_receipt_fingerprint=semantic.fingerprint,
        dataset_schema_fingerprint=semantic.dataset_schema_fingerprint,
        dataset_id=semantic.dataset_id,
        backend_key=semantic.backend_key,
        source_revision=(semantic.source_revision if source_revision is None else source_revision),
        store_revision=semantic.store_revision if store_revision is None else store_revision,
        validator_id="fixture-reader-validator",
        validator_version="1",
        record_provenance=(sha256_fingerprint(source),),
        records_observed=1,
        validation_status="observed_real_data",
    )
    return BackendReaderReceipt(
        receipt_schema=BACKEND_READER_RECEIPT_SCHEMA,
        reader_id="fixture-backend-reader",
        reader_version="1",
        dataset_config_fingerprint=dataset_config_fingerprint(config),
        semantic_manifest_receipt=semantic,
        row_validation_receipt=row,
        cursor=(("sample_index", 2),),
        resume_state=(("next_sample_index", 3),),
        resume_mode="exact",
    )


def test_strict_manifest_maps_complete_semantics_and_is_deterministic() -> None:
    """完整清单应稳定映射到声明态 DatasetSchema 和身份收据。"""
    first = _manifest()
    second = _manifest()
    schema = first.dataset_schema
    assert first.fingerprint == second.fingerprint
    assert first.receipt.fingerprint == second.receipt.fingerprint
    assert schema.row_validation_status == "declared_only"
    assert schema.embodiment.fingerprint == first.embodiment.fingerprint
    assert schema.features == tuple(item.feature for item in first.feature_mappings)
    assert first.temporal.state_offsets == (0,)
    assert first.temporal.action_offsets == (0, 1, 2)
    assert first.projector.mode is ProjectionMode.IDENTITY
    assert first.backend_decision == "NO_BACKEND_WINNER"


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("unknown_top_level", "unknown fields"),
        ("unknown_units", "known physical semantics"),
        ("missing_order", "ordering"),
        ("missing_mask", "mask_fields"),
        ("wrong_history_offsets", "state_offsets length"),
        ("unknown_temporal_anchor", "known physical semantics"),
        ("unknown_normalization_field", "unknown fields"),
    ),
)
def test_manifest_fails_closed_on_missing_or_unknown_semantics(
    mutation: str,
    message: str,
) -> None:
    """单位、帧、顺序、掩码、时间和归一化缺口均不得回退猜测。"""
    raw = _manifest_mapping()
    if mutation == "unknown_top_level":
        raw["guessed_semantics"] = True
    elif mutation in {"unknown_units", "missing_order"}:
        features = _feature_mappings(raw)
        features[0]["units" if mutation == "unknown_units" else "ordering"] = (
            "unknown" if mutation == "unknown_units" else []
        )
        raw["features"] = features
    elif mutation == "missing_mask":
        raw["mask_fields"] = ["camera_mask", "action_mask", "temporal_mask"]
    elif mutation in {"wrong_history_offsets", "unknown_temporal_anchor"}:
        temporal = _nested_mapping(raw, "temporal")
        temporal["state_offsets" if mutation == "wrong_history_offsets" else "anchor"] = (
            [0, -1] if mutation == "wrong_history_offsets" else "unknown"
        )
        raw["temporal"] = temporal
    else:
        normalization = _nested_mapping(raw, "normalization")
        normalization["fallback"] = "implicit"
        raw["normalization"] = normalization
    with pytest.raises(ValueError, match=message):
        parse_semantic_manifest(raw)


def test_manifest_receipt_rejects_binding_schema_projector_and_statistics_drift() -> None:
    """语义收据必须精确绑定 schema、投影器和统计身份。"""
    exact = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    receipt = _manifest().receipt
    receipt.validate_binding(exact)
    with pytest.raises(ValueError, match="dataset_schema_fingerprint"):
        receipt.validate_binding(
            replace(
                exact,
                dataset_schema=replace(exact.dataset_schema, source_format="foreign"),
            )
        )
    with pytest.raises(ValueError, match="projector_id"):
        receipt.validate_binding(replace(exact, projector_id="foreign-projector"))
    with pytest.raises(ValueError, match="normalization_stats_fingerprint"):
        receipt.validate_binding(
            replace(
                exact,
                normalization_binding=replace(
                    exact.normalization_binding,
                    statistics_fingerprint="d" * 64,
                ),
            )
        )


def test_reader_receipt_rejects_source_store_drift_and_fixture_promotion() -> None:
    """真实 reader 只能消费精确来源,fixture 收据不能升级。"""
    manifest = _manifest()
    with pytest.raises(ValueError, match="source_revision"):
        _reader_receipt(manifest, source_revision="foreign-source")
    with pytest.raises(ValueError, match="store_revision"):
        _reader_receipt(manifest, store_revision="foreign-store")

    semantic = manifest.receipt
    fixture = RowValidationReceipt(
        receipt_schema=ROW_VALIDATION_RECEIPT_SCHEMA,
        evidence_class=ReaderEvidenceClass.CONTRACT_FIXTURE_ONLY,
        semantic_manifest_receipt_fingerprint=semantic.fingerprint,
        dataset_schema_fingerprint=semantic.dataset_schema_fingerprint,
        dataset_id=semantic.dataset_id,
        backend_key=semantic.backend_key,
        source_revision=semantic.source_revision,
        store_revision=semantic.store_revision,
        validator_id="contract-batch-factory",
        validator_version="1",
        record_provenance=(),
        records_observed=0,
        validation_status="contract_fixture_only",
    )
    with pytest.raises(ValueError, match="cannot promote a contract fixture"):
        BackendReaderReceipt(
            receipt_schema=BACKEND_READER_RECEIPT_SCHEMA,
            reader_id="fixture-reader",
            reader_version="1",
            dataset_config_fingerprint="e" * 64,
            semantic_manifest_receipt=semantic,
            row_validation_receipt=fixture,
            cursor=(),
            resume_state=(),
            resume_mode="none",
        )


@pytest.mark.parametrize("backend", ("lerobot_local", "webdataset", "robodm_container"))
def test_exact_reader_bridge_emits_bound_batch_provenance_for_batch_and_records(
    backend: str,
) -> None:
    """规范批与内存记录均经同一真实 reader 收据产出不可变来源。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    reader = _reader_receipt(_manifest(backend=backend))
    context = reader.to_batch_context()
    direct = runtime.bind_with_reader_receipt(_batch(context), reader_receipt=reader)
    assert direct.provenance is not None
    assert direct.provenance.real_data_evidence is True
    assert direct.provenance.projection_receipt_fingerprint is None
    assert direct.provenance.backend_key == backend
    assert direct.provenance.backend_decision == "NO_BACKEND_WINNER"
    assert reader.fingerprint == _reader_receipt(_manifest(backend=backend)).fingerprint

    records = runtime.bind_records_with_reader_receipt(
        (_record(context),),
        config=_config(backend),
        reader_receipt=reader,
    )
    assert records.provenance is not None
    assert records.provenance.fingerprint == direct.provenance.fingerprint
    assert records.backend_context.provenance_fingerprint == (
        direct.backend_context.provenance_fingerprint
    )


def test_explicit_projection_requires_versioned_exact_projection_receipt() -> None:
    """显式投影与 exact 直通必须保持不同收据和执行规则。"""
    binding = build_binding_fixture(
        DatasetCompatibilityLevel.EXPLICIT_PROJECTION,
        projected=True,
    )
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    reader = _reader_receipt(_manifest(projected=True))
    context = reader.to_batch_context()

    def project(
        batch: TrainingBatch,
        binding_value: object,
    ) -> TrainingBatch:
        """在测试中重命名相机并写入精确绑定指纹。"""
        assert binding_value is binding
        return replace(
            batch,
            images={"primary": batch.images["front"], "wrist": batch.images["wrist"]},
            transform_fingerprint=binding.fingerprint,
        )

    with pytest.raises(ValueError, match="exact projection receipt"):
        runtime.bind_with_reader_receipt(
            _batch(context),
            reader_receipt=reader,
            projector=project,
        )
    projection = PhysicalProjectionReceipt(
        receipt_schema=PROJECTION_RECEIPT_SCHEMA,
        binding_fingerprint=binding.fingerprint,
        semantic_manifest_receipt_fingerprint=(reader.semantic_manifest_receipt.fingerprint),
        backend_reader_receipt_fingerprint=reader.fingerprint,
        projector_id=reader.semantic_manifest_receipt.projector_id,
        projector_version=reader.semantic_manifest_receipt.projector_version,
        projector_fingerprint=reader.semantic_manifest_receipt.projector_fingerprint,
    )
    bound = runtime.bind_with_reader_receipt(
        _batch(context),
        reader_receipt=reader,
        projector=project,
        projection_receipt=projection,
    )
    assert bound.provenance is not None
    assert bound.compatibility_level is DatasetCompatibilityLevel.EXPLICIT_PROJECTION
    assert bound.provenance.projection_receipt_fingerprint == projection.fingerprint
    with pytest.raises(ValueError, match="projector_version"):
        runtime.bind_with_reader_receipt(
            _batch(context),
            reader_receipt=reader,
            projector=project,
            projection_receipt=replace(projection, projector_version="stale"),
        )


def test_importing_binding_does_not_load_backends_models_training_engine_or_torch() -> None:
    """轻量契约导入不得级联加载后端、模型、训练引擎或 Torch。"""
    import subprocess
    import sys

    command = (
        "import sys; import autovla.data.binding; "
        "blocked=('autovla.data.backends', 'autovla.models.families', "
        "'autovla.training.engine', 'torch'); "
        "loaded=[name for name in blocked if name in sys.modules]; "
        "assert not loaded, loaded"
    )
    result = subprocess.run(
        [sys.executable, "-c", command],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
