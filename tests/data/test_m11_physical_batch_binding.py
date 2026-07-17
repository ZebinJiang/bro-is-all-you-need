"""M11 真实物理批绑定、后端 sidecar 和有界报告测试。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import cast

import numpy as np
import pytest

from autovla.config.schema import DatasetConfig
from autovla.core.types.training import TrainingBatch
from autovla.data.backends.base import dataset_config_fingerprint
from autovla.data.binding import (
    BackendBatchContext,
    BoundedDatasetSurface,
    DatasetCompatibilityLevel,
    DatasetModelBinding,
    DatasetModelRuntime,
    evaluate_compatibility,
    inspect_bounded_dataset_surface,
    sha256_fingerprint,
)
from tests.data.test_m11_dataset_model_binding import (
    DATASET_FINGERPRINT,
    STATISTICS_FINGERPRINT,
    build_binding_fixture,
)


def _config(backend: str = "lerobot_local", *, name: str = "fixture-dataset") -> DatasetConfig:
    """构造不会读取磁盘的显式数据集配置。"""
    return DatasetConfig(
        name=name,
        backend=backend,
        root="/governed/not-read-by-this-test",
        embodiment="demo-arm",
        image_keys=("front", "wrist"),
        access_mode="streaming" if backend == "webdataset" else "map",
        stream_mode="finite_epoch" if backend == "webdataset" else None,
        nominal_epoch_size=1 if backend == "webdataset" else None,
    )


def _sample_source(config: DatasetConfig, *, sample_id: str = "sample-2") -> dict[str, object]:
    """构造与 reader 转换器一致的单条有序来源映射。"""
    return {
        "sample_id": sample_id,
        "timestamp": [0.0, 1.0 / 30.0, 2.0 / 30.0],
        "backend": config.backend,
        "dataset": config.name,
        "dataset_config_fingerprint": dataset_config_fingerprint(config),
        "split": config.split,
    }


def _context(
    binding: DatasetModelBinding,
    config: DatasetConfig,
    *,
    source: dict[str, object] | None = None,
) -> BackendBatchContext:
    """构造绑定配置、manifest、schema 和记录顺序的不可变收据。"""
    dataset_schema = binding.dataset_schema
    record_source = _sample_source(config) if source is None else source
    return BackendBatchContext(
        backend_key=config.backend,
        dataset_id=config.name,
        dataset_config_fingerprint=dataset_config_fingerprint(config),
        manifest_fingerprint=dataset_schema.immutable_dataset_fingerprint,
        schema_fingerprint=dataset_schema.fingerprint,
        source_revision="source-revision-7",
        store_revision="store-revision-7",
        record_provenance=(sha256_fingerprint(record_source),),
        cursor=(("sample_index", 2),),
        resume_state=(("next_sample_index", 3),),
        resume_mode="exact",
    )


def _batch(context: BackendBatchContext) -> TrainingBatch:
    """构造完整 provenance 的小型物理批,不使用合成契约工厂。"""
    source = _sample_source(_config(context.backend_key))
    return TrainingBatch(
        images={
            "front": np.zeros((1, 3, 3, 3), dtype=np.uint8),
            "wrist": np.ones((1, 3, 3, 3), dtype=np.uint8),
        },
        language=("move",),
        actions=np.zeros((1, 3, 2), dtype=np.float32),
        action_mask=np.ones((1, 3, 2), dtype=np.bool_),
        sample_source=(source,),
        dataset_fingerprint=DATASET_FINGERPRINT,
        transform_fingerprint="identity",
        statistics_fingerprint=STATISTICS_FINGERPRINT,
        state=np.zeros((1, 2), dtype=np.float32),
        embodiment=("demo-arm",),
        timestamps=np.asarray([[0.0, 1.0 / 30.0, 2.0 / 30.0]], dtype=np.float64),
        dataset_manifest_fingerprint=DATASET_FINGERPRINT,
        store_fingerprints=(context.store_revision,),
        source_fingerprints=(context.source_revision,),
        schema_fingerprints=(context.schema_fingerprint,),
    )


def _record(context: BackendBatchContext) -> dict[str, object]:
    """构造带独立 reader/manifest envelope 的内存记录。"""
    return {
        "images": {
            "front": np.zeros((3, 3, 3), dtype=np.uint8),
            "wrist": np.ones((3, 3, 3), dtype=np.uint8),
        },
        "payload": {
            "action": np.zeros((3, 2), dtype=np.float32),
            "action_mask": np.ones((3, 2), dtype=np.bool_),
            "state": np.zeros((2,), dtype=np.float32),
            "language": "move",
            "timestamp": [0.0, 1.0 / 30.0, 2.0 / 30.0],
            "sample_id": "sample-2",
        },
        "provenance": {
            "backend_key": context.backend_key,
            "dataset_config_fingerprint": context.dataset_config_fingerprint,
            "dataset_id": context.dataset_id,
            "manifest_fingerprint": context.manifest_fingerprint,
            "record_provenance": context.record_provenance[0],
            "schema_fingerprint": context.schema_fingerprint,
            "source_revision": context.source_revision,
            "store_revision": context.store_revision,
        },
    }


def _copy_object_mapping(value: object) -> dict[str, object]:
    """校验并复制测试记录中的字符串键映射,避免修改原始不可变收据。"""
    assert isinstance(value, Mapping)
    return dict(cast(Mapping[str, object], value))


class _Processor:
    """记录 family processor 入口收到的唯一规范批。"""

    def __init__(self) -> None:
        self.batch: TrainingBatch | None = None

    def prepare_batch(
        self,
        batch: TrainingBatch,
        *,
        device: object,
        dtype: object | None,
        training: bool,
    ) -> tuple[object, object | None, bool]:
        """返回无模型运行的调用证据。"""
        self.batch = batch
        return device, dtype, training


def test_exact_physical_batch_reaches_existing_family_processor_without_copy() -> None:
    """exact 路径保留同一 TrainingBatch、cursor、provenance 和后端中立声明。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    config = _config()
    context = _context(binding, config)
    batch = _batch(context)
    bound = runtime.bind(batch, context)
    processor = _Processor()
    result = runtime.prepare_for_family(
        bound,
        processor,
        device="cuda:0-contract-only",
        dtype=None,
        training=True,
    )
    assert bound.batch is batch
    assert processor.batch is batch
    assert result == ("cuda:0-contract-only", None, True)
    assert bound.backend_context.cursor == (("sample_index", 2),)
    assert bound.backend_context.backend_decision == "NO_BACKEND_WINNER"


def test_explicit_projection_requires_named_projector_and_stamped_fingerprint() -> None:
    """显式投影不能退化为隐式改名、填零或未记录的变换。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXPLICIT_PROJECTION, projected=True)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    context = _context(binding, _config())
    with pytest.raises(ValueError, match="explicit physical projector"):
        runtime.bind(_batch(context), context)

    def project(batch: TrainingBatch, binding_value: object) -> TrainingBatch:
        """显式重命名相机并写入绑定指纹。"""

        assert binding_value is binding
        return replace(
            batch,
            images={"primary": batch.images["front"], "wrist": batch.images["wrist"]},
            transform_fingerprint=binding.fingerprint,
        )

    bound = runtime.bind(_batch(context), context, projector=project)
    assert tuple(bound.batch.images) == ("primary", "wrist")
    assert bound.compatibility_level is DatasetCompatibilityLevel.EXPLICIT_PROJECTION


@pytest.mark.parametrize("backend", ("lerobot_local", "webdataset", "robodm_container"))
def test_existing_backend_records_share_one_physical_binding_path(backend: str) -> None:
    """三种现有 reader record 经同一转换器、collator 和绑定进入规范批。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    config = _config(backend)
    context = _context(binding, config)
    bound = runtime.bind_records((_record(context),), config=config, context=context)
    assert bound.batch.batch_size == 1
    assert tuple(bound.batch.images) == ("front", "wrist")
    assert bound.batch.timestamps is not None
    assert bound.batch.timestamps.shape == (1, 3)
    assert bound.backend_context.backend_decision == "NO_BACKEND_WINNER"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("state", np.zeros((1, 3), dtype=np.float32), "state shape"),
        ("actions", np.zeros((1, 2, 2), dtype=np.float32), "action horizon"),
        ("embodiment", ("unknown-arm",), "embodiment"),
        ("timestamps", np.zeros((1, 1), dtype=np.float64), "timestamps"),
    ),
)
def test_physical_batch_rejects_dimension_history_embodiment_and_time_guesses(
    field: str, value: object, message: str
) -> None:
    """运行时不通过补零、截断或默认具身来制造兼容。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    context = _context(binding, _config())
    changes: dict[str, object] = {field: value}
    if field == "actions":
        changes["action_mask"] = np.ones((1, 2, 2), dtype=np.bool_)
    with pytest.raises(ValueError, match=message):
        runtime.bind(replace(_batch(context), **changes), context)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("dataset_manifest_fingerprint", "e" * 64, "manifest"),
        ("schema_fingerprints", ("e" * 64,), "schema_fingerprints"),
        ("source_fingerprints", ("foreign-source",), "source_fingerprints"),
        ("store_fingerprints", ("foreign-store",), "store_fingerprints"),
    ),
)
def test_direct_bind_rejects_manifest_schema_source_and_store_drift(
    field: str, value: object, message: str
) -> None:
    """直接绑定必须逐项核对收据,不能只检查 provenance 数量。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    context = _context(binding, _config())
    changes = {field: value}
    if field == "dataset_manifest_fingerprint":
        changes["dataset_fingerprint"] = value
    with pytest.raises(ValueError, match=message):
        runtime.bind(replace(_batch(context), **changes), context)


def test_caller_invented_context_identity_is_not_accepted() -> None:
    """调用方不能仅替换 context revision 就取得另一个物理批的身份。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    context = _context(binding, _config())
    invented = replace(context, source_revision="caller-invented-source")
    with pytest.raises(ValueError, match="source_fingerprints"):
        runtime.bind(_batch(context), invented)


def test_bind_records_rejects_wrong_config_and_shape_compatible_foreign_record() -> None:
    """记录入口在数组物化前拒绝错误配置和相同形状的外来 sample。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    config = _config()
    context = _context(binding, config)
    record = _record(context)

    with pytest.raises(ValueError, match="config identity"):
        runtime.bind_records((record,), config=_config(name="foreign-dataset"), context=context)

    payload = _copy_object_mapping(record["payload"])
    payload["sample_id"] = "foreign-sample"
    foreign_record = dict(record)
    foreign_record["payload"] = payload
    with pytest.raises(ValueError, match="source differs"):
        runtime.bind_records((foreign_record,), config=config, context=context)


@pytest.mark.parametrize(
    "field",
    ("manifest_fingerprint", "schema_fingerprint", "source_revision", "store_revision"),
)
def test_bind_records_rejects_record_receipt_identity_drift(field: str) -> None:
    """记录 envelope 的 manifest/schema/source/store 任一漂移都必须失败。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    config = _config()
    context = _context(binding, config)
    record = _record(context)
    provenance = _copy_object_mapping(record["provenance"])
    provenance[field] = "e" * 64 if "fingerprint" in field else f"foreign-{field}"
    record["provenance"] = provenance
    with pytest.raises(ValueError, match=field):
        runtime.bind_records((record,), config=config, context=context)


def test_fixture_only_and_unknown_semantics_never_enter_real_data_runtime() -> None:
    """fixture-only 与未知单位均不能进入真实后端到处理器的路径。"""
    fixture = build_binding_fixture(DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY)
    fixture_runtime = DatasetModelRuntime(fixture, evaluate_compatibility(fixture))
    fixture_context = _context(fixture, _config())
    with pytest.raises(ValueError, match="contract_fixture_only"):
        fixture_runtime.bind(_batch(fixture_context), fixture_context)

    unknown = build_binding_fixture(DatasetCompatibilityLevel.EXACT, unknown_units=True)
    unknown_report = evaluate_compatibility(unknown)
    assert unknown_report.level is DatasetCompatibilityLevel.INCOMPATIBLE
    unknown_context = _context(unknown, _config())
    with pytest.raises(ValueError, match="incompatible"):
        DatasetModelRuntime(unknown, unknown_report).bind(_batch(unknown_context), unknown_context)


def test_current_72x98_three_camera_surface_is_bounded_and_not_family_compatible() -> None:
    """当前只读数据集只暴露观察形状,不提升任何 family 兼容性。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    surface = BoundedDatasetSurface(
        dataset_id="black-rubber-bellows-0622-0623-768-cmd-256-30hz",
        version="v2.1",
        source_format="lerobot",
        source_revision="metadata-inventory@475cc6c40c7c",
        provenance="M11 initial dataset inventory; no row or media read",
        state_dimension=72,
        action_dimension=98,
        camera_names=("head_rgb", "left_wrist_rgb", "right_wrist_rgb"),
        sample_rate_hz=30.0,
    )
    report = inspect_bounded_dataset_surface(surface, binding.model_schema)
    assert report.level is DatasetCompatibilityLevel.INCOMPATIBLE
    assert report.real_sample_read is False
    assert report.family_compatibility_claimed is False
    assert report.backend_decision == "NO_BACKEND_WINNER"
    assert {
        "UNKNOWN_UNITS",
        "UNKNOWN_COORDINATE_OR_REFERENCE_FRAMES",
        "UNKNOWN_FEATURE_ORDERING",
        "UNKNOWN_HISTORY",
        "UNKNOWN_NORMALIZATION",
        "UNKNOWN_EMBODIMENT",
        "STATE_DIMENSION_MISMATCH",
        "ACTION_DIMENSION_MISMATCH",
    }.issubset(report.reason_codes)


def test_contract_fixture_provenance_records_source_revision() -> None:
    """确定性 fixture provenance 必须显式包含模型输入契约来源版本。"""
    from autovla.data.binding import ContractBatchFactory

    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    provenance = ContractBatchFactory(binding, evaluate_compatibility(binding)).provenance()
    assert provenance.source_revision == binding.model_schema.source_pin
    assert provenance.provenance_schema == "autovla.contract_batch_provenance.v2"
