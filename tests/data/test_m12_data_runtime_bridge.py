"""M12 production data-binding runtime bridge 聚焦测试。"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from autovla.core.types.training import TrainingBatch
from autovla.data.backends.lerobot import LeRobotLocalBackend
from autovla.data.backends.robodm import RoboDMContainerBackend
from autovla.data.backends.webdataset import WebDatasetBackend
from autovla.data.binding import (
    PROJECTION_RECEIPT_SCHEMA,
    BackendBatchReceiptInput,
    DataBackendBindingAdapter,
    DatasetCompatibilityLevel,
    DatasetModelRuntime,
    PhysicalProjectionReceipt,
    RealBatchReceipt,
    evaluate_compatibility,
    sha256_fingerprint,
)
from tests.data.test_m11_dataset_model_binding import build_binding_fixture
from tests.data.test_m11_physical_batch_binding import (
    _batch,
    _config,
    _record,
    _sample_source,
)
from tests.data.test_m12_semantic_manifest import _manifest


def _adapter(backend: str) -> DataBackendBindingAdapter:
    """从三个真实 backend 类取得同一个适配器 contract。"""
    if backend == "lerobot_local":
        return LeRobotLocalBackend().binding_adapter()
    if backend == "webdataset":
        return WebDatasetBackend().binding_adapter()
    if backend == "robodm_container":
        return RoboDMContainerBackend().binding_adapter()
    raise AssertionError(f"unexpected backend fixture: {backend}")


def _receipt_input(backend: str = "lerobot_local") -> BackendBatchReceiptInput:
    """仅用内存身份构造 production reader/context 输入。"""
    config = _config(backend)
    source = _sample_source(config)
    return _adapter(backend).mint(
        config=config,
        semantic_manifest_receipt=_manifest(backend=backend).receipt,
        ordered_sample_identities=("sample-2",),
        ordered_record_provenance=(sha256_fingerprint(source),),
        cursor=(("sample_index", 2),),
        resume_state=(("next_sample_index", 3),),
        resume_mode="exact",
    )


class _Processor:
    """记录 production family handoff 是否收到规范批。"""

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
        """保存批并返回不触发模型运行的调用参数。"""
        self.batch = batch
        return device, dtype, training


@pytest.mark.parametrize("backend", ("lerobot_local", "webdataset", "robodm_container"))
def test_all_backends_mint_equal_contract_and_real_batch_receipt(backend: str) -> None:
    """三个 backend 通过同一 adapter 生成 context 和完整真实批收据。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    receipt_input = _receipt_input(backend)
    context = receipt_input.backend_context

    bound = runtime.bind_production_batch(
        _batch(context),
        receipt_input=receipt_input,
    )

    receipt = bound.real_batch_receipt
    assert isinstance(receipt, RealBatchReceipt)
    assert receipt.backend_key == backend
    assert receipt.backend_decision == "NO_BACKEND_WINNER"
    assert receipt.compatibility_level is DatasetCompatibilityLevel.EXACT
    assert receipt.ordered_sample_identities == ("sample-2",)
    assert receipt.ordered_record_identities == context.record_provenance
    assert receipt.action_shape == (1, 3, 2)
    assert receipt.action_mask_shape == receipt.action_shape
    assert receipt.timestamps_shape == (1, 3)
    assert tuple(name for name, _ in receipt.image_shapes) == ("front", "wrist")
    assert len(receipt.fingerprint) == 64
    assert json.loads(json.dumps(receipt.to_dict()))["backend_decision"] == "NO_BACKEND_WINNER"
    assert receipt_input.fingerprint == _receipt_input(backend).fingerprint
    assert receipt.fingerprint == (
        runtime.bind_production_batch(
            _batch(receipt_input.backend_context),
            receipt_input=receipt_input,
        ).real_batch_receipt.fingerprint
    )


@pytest.mark.parametrize("backend", ("lerobot_local", "webdataset", "robodm_container"))
def test_production_records_use_same_bound_batch_and_receipt_path(backend: str) -> None:
    """tiny 内存记录复用现有 converter/collator 并输出训练可消费批。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    receipt_input = _receipt_input(backend)
    context = receipt_input.backend_context

    bound = runtime.bind_production_records(
        (_record(context),),
        config=_config(backend),
        receipt_input=receipt_input,
    )
    processor = _Processor()
    result = runtime.prepare_real_for_family(
        bound,
        processor,
        device="cpu-contract-only",
        dtype=None,
        training=True,
    )

    assert processor.batch is bound.batch
    assert result == ("cpu-contract-only", None, True)
    assert bound.real_batch_receipt is not None
    assert bound.real_batch_receipt.fingerprint == (
        runtime.bind_production_batch(
            _batch(context),
            receipt_input=receipt_input,
        ).real_batch_receipt.fingerprint
    )


def test_production_handoff_fails_closed_before_processor() -> None:
    """缺 reader chain、样本漂移或 fixture level 均不得到达 processor。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    receipt_input = _receipt_input()
    context = receipt_input.backend_context
    processor = _Processor()

    legacy = runtime.bind(_batch(context), context)
    with pytest.raises(ValueError, match="real batch receipt"):
        runtime.prepare_real_for_family(
            legacy,
            processor,
            device="cpu-contract-only",
            dtype=None,
            training=True,
        )
    assert processor.batch is None

    wrong_identity = replace(
        receipt_input,
        ordered_sample_identities=("foreign-sample",),
    )
    with pytest.raises(ValueError, match="sample identities"):
        runtime.bind_production_batch(
            _batch(context),
            receipt_input=wrong_identity,
        )

    real = runtime.bind_production_batch(
        _batch(context),
        receipt_input=receipt_input,
    )
    assert real.real_batch_receipt is not None
    tampered = replace(
        real,
        real_batch_receipt=replace(
            real.real_batch_receipt,
            action_mask_fingerprint="f" * 64,
        ),
    )
    with pytest.raises(ValueError, match="action_mask_fingerprint"):
        runtime.prepare_real_for_family(
            tampered,
            processor,
            device="cpu-contract-only",
            dtype=None,
            training=True,
        )

    fixture = build_binding_fixture(DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY)
    fixture_runtime = DatasetModelRuntime(fixture, evaluate_compatibility(fixture))
    with pytest.raises(ValueError, match="contract_fixture_only"):
        fixture_runtime.bind_production_batch(
            _batch(context),
            receipt_input=receipt_input,
        )


def test_explicit_projection_production_receipt_binds_projector_identity() -> None:
    """显式投影必须沿 production 输入携带精确 projector receipt。"""
    binding = build_binding_fixture(
        DatasetCompatibilityLevel.EXPLICIT_PROJECTION,
        projected=True,
    )
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    config = _config()
    source = _sample_source(config)
    receipt_input = _adapter("lerobot_local").mint(
        config=config,
        semantic_manifest_receipt=_manifest(projected=True).receipt,
        ordered_sample_identities=("sample-2",),
        ordered_record_provenance=(sha256_fingerprint(source),),
        cursor=(("sample_index", 2),),
        resume_state=(("next_sample_index", 3),),
        resume_mode="exact",
    )
    reader = receipt_input.reader_receipt

    def project(batch: TrainingBatch, binding_value: object) -> TrainingBatch:
        """测试 projector 只做已声明相机映射并写入绑定指纹。"""
        assert binding_value is binding
        return replace(
            batch,
            images={"primary": batch.images["front"], "wrist": batch.images["wrist"]},
            transform_fingerprint=binding.fingerprint,
        )

    projection = PhysicalProjectionReceipt(
        receipt_schema=PROJECTION_RECEIPT_SCHEMA,
        binding_fingerprint=binding.fingerprint,
        semantic_manifest_receipt_fingerprint=reader.semantic_manifest_receipt.fingerprint,
        backend_reader_receipt_fingerprint=reader.fingerprint,
        projector_id=reader.semantic_manifest_receipt.projector_id,
        projector_version=reader.semantic_manifest_receipt.projector_version,
        projector_fingerprint=reader.semantic_manifest_receipt.projector_fingerprint,
    )
    bound = runtime.bind_production_batch(
        _batch(receipt_input.backend_context),
        receipt_input=receipt_input,
        projector=project,
        projection_receipt=projection,
    )

    assert bound.real_batch_receipt is not None
    assert (
        bound.real_batch_receipt.projector_fingerprint
        == reader.semantic_manifest_receipt.projector_fingerprint
    )
    assert (
        bound.real_batch_receipt.compatibility_level
        is DatasetCompatibilityLevel.EXPLICIT_PROJECTION
    )


def test_receipts_are_immutable_and_reject_paths_or_credentials() -> None:
    """公开 receipt 不允许绝对用户路径、凭据片段或可变字段。"""
    binding = build_binding_fixture(DatasetCompatibilityLevel.EXACT)
    runtime = DatasetModelRuntime(binding, evaluate_compatibility(binding))
    receipt_input = _receipt_input()
    bound = runtime.bind_production_batch(
        _batch(receipt_input.backend_context),
        receipt_input=receipt_input,
    )
    receipt = bound.real_batch_receipt
    assert receipt is not None

    with pytest.raises(FrozenInstanceError):
        receipt.source_revision = "changed"
    with pytest.raises(ValueError, match="absolute user path"):
        replace(receipt, source_revision="/home/user/private/source")
    with pytest.raises(ValueError, match="credential material"):
        replace(receipt, store_revision="token=not-allowed")
    with pytest.raises(ValueError, match="absolute user path"):
        _adapter("lerobot_local").mint(
            config=_config(),
            semantic_manifest_receipt=_manifest().receipt,
            ordered_sample_identities=("/home/user/sample-2",),
            ordered_record_provenance=("a" * 64,),
            cursor=(),
            resume_state=(),
            resume_mode="none",
        )


def test_adapter_preserves_ordered_replay_identities_without_ranking() -> None:
    """replay/resample 可重复同一身份,但顺序和后端平权声明必须保留。"""
    adapter = _adapter("webdataset")
    receipt_input = adapter.mint(
        config=_config("webdataset"),
        semantic_manifest_receipt=_manifest(backend="webdataset").receipt,
        ordered_sample_identities=("sample-2", "sample-2"),
        ordered_record_provenance=("a" * 64, "a" * 64),
        cursor=(("sample_offset", 2),),
        resume_state=(("next_sample_offset", 3),),
        resume_mode="replay",
    )

    assert receipt_input.ordered_sample_identities == ("sample-2", "sample-2")
    assert receipt_input.reader_receipt.record_provenance == ("a" * 64, "a" * 64)
    assert receipt_input.backend_decision == "NO_BACKEND_WINNER"


def test_binding_import_keeps_training_engine_and_backend_implementations_unloaded() -> None:
    """统一 contract 导入不反向加载 TrainingEngine 或 backend 实现。"""
    import subprocess
    import sys

    command = (
        "import sys; import autovla.data.binding; "
        "blocked=('autovla.training.engine', 'autovla.data.backends.lerobot', "
        "'autovla.data.backends.webdataset', 'autovla.data.backends.robodm'); "
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
