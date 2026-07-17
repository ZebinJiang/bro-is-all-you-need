"""M11 真实物理批绑定、后端 sidecar 和有界报告测试。"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from autovla.config.schema import DatasetConfig
from autovla.core.types.training import TrainingBatch
from autovla.data.binding import (
    BackendBatchContext,
    BoundedDatasetSurface,
    DatasetCompatibilityLevel,
    DatasetModelRuntime,
    evaluate_compatibility,
    inspect_bounded_dataset_surface,
)
from tests.data.test_m11_dataset_model_binding import (
    DATASET_FINGERPRINT,
    STATISTICS_FINGERPRINT,
    build_binding_fixture,
)


def _context(backend: str = "lerobot_local") -> BackendBatchContext:
    """构造不偏向任何后端的确定性读取 sidecar。"""
    return BackendBatchContext(
        backend_key=backend,
        source_revision="local-store-revision-7",
        provenance_fingerprint="c" * 64,
        cursor=(("sample_index", 2),),
        resume_state=(("next_sample_index", 3),),
        resume_mode="exact",
    )


def _batch(*, backend: str = "lerobot_local") -> TrainingBatch:
    """构造完整 provenance 的小型物理批,不使用合成契约工厂。"""
    return TrainingBatch(
        images={
            "front": np.zeros((1, 3, 3, 3), dtype=np.uint8),
            "wrist": np.ones((1, 3, 3, 3), dtype=np.uint8),
        },
        language=("move",),
        actions=np.zeros((1, 3, 2), dtype=np.float32),
        action_mask=np.ones((1, 3, 2), dtype=np.bool_),
        sample_source=({"backend": backend, "sample_id": "sample-2"},),
        dataset_fingerprint=DATASET_FINGERPRINT,
        transform_fingerprint="identity",
        statistics_fingerprint=STATISTICS_FINGERPRINT,
        state=np.zeros((1, 2), dtype=np.float32),
        embodiment=("demo-arm",),
        timestamps=np.asarray([[0.0, 1.0 / 30.0, 2.0 / 30.0]], dtype=np.float64),
        dataset_manifest_fingerprint=DATASET_FINGERPRINT,
        store_fingerprints=("store-7",),
        source_fingerprints=("c" * 64,),
        schema_fingerprints=("d" * 64,),
    )


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
    batch = _batch()
    context = _context()
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
    with pytest.raises(ValueError, match="explicit physical projector"):
        runtime.bind(_batch(), _context())

    def project(batch: TrainingBatch, binding_value: object) -> TrainingBatch:
        """显式重命名相机并写入绑定指纹。"""

        assert binding_value is binding
        return replace(
            batch,
            images={"primary": batch.images["front"], "wrist": batch.images["wrist"]},
            transform_fingerprint=binding.fingerprint,
        )

    bound = runtime.bind(_batch(), _context(), projector=project)
    assert tuple(bound.batch.images) == ("primary", "wrist")
    assert bound.compatibility_level is DatasetCompatibilityLevel.EXPLICIT_PROJECTION


@pytest.mark.parametrize("backend", ("lerobot_local", "webdataset", "robodm_container"))
def test_existing_backend_records_share_one_physical_binding_path(backend: str) -> None:
    """三种现有 reader record 经同一转换器、collator 和绑定进入规范批。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    config = DatasetConfig(
        name="fixture-dataset",
        backend=backend,
        root="/governed/not-read-by-this-test",
        embodiment="demo-arm",
        image_keys=("front", "wrist"),
        access_mode="streaming" if backend == "webdataset" else "map",
        stream_mode="finite_epoch" if backend == "webdataset" else None,
        nominal_epoch_size=1 if backend == "webdataset" else None,
    )
    record = {
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
    }
    bound = runtime.bind_records((record,), config=config, context=_context(backend))
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
    changes: dict[str, object] = {field: value}
    if field == "actions":
        changes["action_mask"] = np.ones((1, 2, 2), dtype=np.bool_)
    with pytest.raises(ValueError, match=message):
        runtime.bind(replace(_batch(), **changes), _context())


def test_fixture_only_and_unknown_semantics_never_enter_real_data_runtime() -> None:
    """fixture-only 与未知单位均不能进入真实后端到处理器的路径。"""
    fixture = build_binding_fixture(DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY)
    fixture_runtime = DatasetModelRuntime(fixture, evaluate_compatibility(fixture))
    with pytest.raises(ValueError, match="contract_fixture_only"):
        fixture_runtime.bind(_batch(), _context())

    unknown = build_binding_fixture(DatasetCompatibilityLevel.EXACT, unknown_units=True)
    unknown_report = evaluate_compatibility(unknown)
    assert unknown_report.level is DatasetCompatibilityLevel.INCOMPATIBLE
    with pytest.raises(ValueError, match="incompatible"):
        DatasetModelRuntime(unknown, unknown_report).bind(_batch(), _context())


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
