"""M10 生产数据运行时交接的最小内存契约测试。"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from autovla.config.schema import DataLoaderConfig, DatasetConfig
from autovla.core.types.training import TrainingBatch
from autovla.data.collators import PaddedBatchCollator
from autovla.data.contracts import (
    DataAccessMode,
    DataSourceSpec,
    PartitionPlan,
    SamplingPlan,
)
from autovla.data.loader import (
    ProductionCollator,
    RuntimeTopology,
    SourceFactory,
    TrainingDataLoader,
)
from autovla.data.runtime import (
    BACKEND_DECISION,
    DataRuntimeHandoff,
    DataWaitTelemetry,
    logical_batch_fingerprint,
)
from autovla.data.transforms import TransformPipeline
from autovla.data.types import DataStage


def _batch(*, backend: str = "lerobot_local") -> TrainingBatch:
    """构造不读取数据文件的规范内存批。"""

    sample_ids = ("episode-000/frame-000", "episode-000/frame-001")
    return TrainingBatch(
        images={"camera.rgb": np.zeros((2, 3, 4, 4), dtype=np.float32)},
        language=("pick", "place"),
        actions=np.zeros((2, 3, 7), dtype=np.float32),
        action_mask=np.ones((2, 3, 7), dtype=np.bool_),
        sample_source=tuple(
            {
                "backend": backend,
                "dataset": "logical-dataset",
                "sample_id": sample_id,
                "episode_id": "episode-000",
                "frame_index": index,
            }
            for index, sample_id in enumerate(sample_ids)
        ),
        dataset_fingerprint="manifest",
        dataset_manifest_fingerprint="manifest",
        transform_fingerprint="transform",
        statistics_fingerprint="statistics",
        store_fingerprints=("store-a", "store-b"),
        source_fingerprints=("source-a", "source-b"),
        schema_fingerprints=("schema-a", "schema-b"),
    )


def _handoff(batch: TrainingBatch, *, cursor: int = 2) -> DataRuntimeHandoff:
    """从已提交内存批构造运行时交接。"""

    telemetry = DataWaitTelemetry().observe(0.01)
    return DataRuntimeHandoff.from_committed_batch(
        batch,
        rank=1,
        world_size=2,
        epoch=3,
        global_batches_consumed=max(1, cursor // batch.batch_size),
        global_samples_consumed=cursor,
        committed_sample_cursor=cursor,
        assignment_digest="rank-assignment",
        compatibility_fingerprint="loader-compatibility",
        data_wait=telemetry,
    )


def _in_memory_loader(batch: TrainingBatch) -> TrainingDataLoader:
    """构造不打开 reader、不导入 Torch 的单批生产 loader。"""

    spec = DataSourceSpec(
        dataset_key="logical-dataset",
        backend_key="lerobot_local",
        split="train",
        access_mode=DataAccessMode.MAP,
        source_fingerprint="source",
        schema_fingerprint="schema",
        finite=True,
        sample_count=2,
        supports_batch_read=True,
        supports_temporal_query=False,
        supports_media=False,
        supports_exact_resume=True,
    )
    sequence = ((0, 0), (0, 1))
    plan = PartitionPlan.for_map(
        sequence,
        global_rank=0,
        world_size=1,
        batch_size=2,
        seed=17,
        epoch=0,
        shuffle=False,
        policy="exact_no_pad",
    )
    loader = TrainingDataLoader(
        factories=(
            SourceFactory(
                "autovla.data.backends.lerobot:create_backend",
                DatasetConfig("logical-dataset", "lerobot_local", "unused", sample_count=2),
                DataStage.TRAIN,
                spec,
            ),
        ),
        source_specs=(spec,),
        partition_plan=plan,
        sampling_plan=SamplingPlan(DataAccessMode.MAP, 2, False, 17),
        config=DataLoaderConfig(batch_size=2),
        topology=RuntimeTopology(0, 0, 1, 17, "train", "none"),
        collator=ProductionCollator(
            PaddedBatchCollator(),
            TransformPipeline(),
            "manifest",
            "statistics",
            (("logical-dataset", "source", "schema"),),
        ),
        manifest_fingerprint="manifest",
        mix_strategy="weighted",
        mix_balance_by="dataset",
        mix_weights=(1.0,),
        base_map_sequence=sequence,
    )
    loader._torch_loader = (batch,)
    return loader


def test_runtime_handoff_is_backend_neutral_and_keeps_canonical_action_semantics() -> None:
    """相同逻辑批跨后端保持同一身份且动作/掩码语义封闭。"""

    lerobot = _handoff(_batch(backend="lerobot_local"))
    webdataset = _handoff(_batch(backend="webdataset"))
    robodm = _handoff(_batch(backend="robodm_container"))

    assert lerobot.logical_batch_fingerprint == webdataset.logical_batch_fingerprint
    assert webdataset.logical_batch_fingerprint == robodm.logical_batch_fingerprint
    assert lerobot.logical_sample_ids == (
        "episode-000/frame-000",
        "episode-000/frame-001",
    )
    assert lerobot.action_shape == (2, 3, 7)
    assert lerobot.action_layout == "BHD"
    assert lerobot.action_mask_semantics == "strict_bool_true_is_valid"
    assert lerobot.backend_decision == BACKEND_DECISION == "NO_BACKEND_WINNER"
    assert "backend" not in lerobot.to_dict()


def test_handoff_binds_rank_sharding_resume_cursor_and_data_wait() -> None:
    """rank 分片互斥, 恢复位置和等待遥测进入稳定交接身份。"""

    sequence = tuple((0, index) for index in range(8))
    rank0 = PartitionPlan.for_map(
        sequence,
        global_rank=0,
        world_size=2,
        batch_size=2,
        seed=17,
        epoch=3,
        shuffle=False,
        policy="exact_no_pad",
    )
    rank1 = PartitionPlan.for_map(
        sequence,
        global_rank=1,
        world_size=2,
        batch_size=2,
        seed=17,
        epoch=3,
        shuffle=False,
        policy="exact_no_pad",
    )
    assert set(rank0.rank_sequence).isdisjoint(rank1.rank_sequence)

    first = _handoff(_batch(), cursor=2)
    replay = _handoff(_batch(), cursor=2)
    advanced = _handoff(_batch(), cursor=4)
    assert first.resume_fingerprint == replay.resume_fingerprint
    assert first.resume_fingerprint != advanced.resume_fingerprint
    assert first.rank == 1 and first.world_size == 2
    assert first.data_wait.to_dict() == {
        "observed_batches": 1,
        "total_seconds": 0.01,
        "last_seconds": 0.01,
        "max_seconds": 0.01,
        "mean_seconds": 0.01,
    }


def test_training_loader_publishes_handoff_only_with_committed_batch() -> None:
    """内存 loader 在交付批时同步发布 cursor、身份和等待遥测。"""

    loader = _in_memory_loader(_batch())
    try:
        delivered = next(iter(loader))
        handoff = loader.last_runtime_handoff
        assert delivered.batch_size == 2
        assert handoff is not None
        assert handoff.logical_sample_ids == (
            "episode-000/frame-000",
            "episode-000/frame-001",
        )
        assert handoff.global_batches_consumed == 1
        assert handoff.global_samples_consumed == 2
        assert handoff.committed_sample_cursor == 2
        assert handoff.data_wait.observed_batches == 1
    finally:
        loader.close()


def test_logical_identity_rejects_backend_fallback_and_explicit_drift() -> None:
    """逻辑 ID 必须显式存在, 且不得随物理后端别名漂移。"""

    batch = _batch()
    without_id = replace(
        batch,
        sample_source=tuple(
            {key: value for key, value in source.items() if key != "sample_id"}
            for source in batch.sample_source
        ),
    )
    with pytest.raises(ValueError, match="sample_id"):
        _handoff(without_id)

    drifted_sources = [dict(source) for source in batch.sample_source]
    drifted_sources[0]["logical_sample_id"] = "webdataset-specific-key"
    with pytest.raises(ValueError, match="backend-independent"):
        logical_batch_fingerprint(
            tuple(drifted_sources),
            dataset_manifest_fingerprint="manifest",
            transform_fingerprint="transform",
            statistics_fingerprint="statistics",
        )


def test_legacy_dataset_fallback_binds_the_same_canonical_batch_identity() -> None:
    """legacy 空 manifest 回退值必须同时进入公开字段和逻辑批指纹。"""

    batch = _batch()
    object.__setattr__(batch, "dataset_manifest_fingerprint", None)
    handoff = _handoff(batch)

    assert handoff.dataset_manifest_fingerprint == "manifest"
    assert handoff.logical_batch_fingerprint == logical_batch_fingerprint(
        batch.sample_source,
        dataset_manifest_fingerprint="manifest",
        transform_fingerprint="transform",
        statistics_fingerprint="statistics",
    )


def test_handoff_rejects_uncommitted_counters_and_negative_wait() -> None:
    """交接不得先于批提交, 等待计时也不得静默吞掉负值。"""

    with pytest.raises(ValueError, match="non-negative"):
        DataWaitTelemetry().observe(-0.01)

    with pytest.raises(ValueError, match="global_batches_consumed"):
        DataRuntimeHandoff.from_committed_batch(
            _batch(),
            rank=0,
            world_size=1,
            epoch=0,
            global_batches_consumed=0,
            global_samples_consumed=2,
            committed_sample_cursor=2,
            assignment_digest="rank-assignment",
            compatibility_fingerprint="loader-compatibility",
            data_wait=DataWaitTelemetry(),
        )

    with pytest.raises(ValueError, match="committed sample cursor"):
        DataRuntimeHandoff.from_committed_batch(
            _batch(),
            rank=0,
            world_size=1,
            epoch=0,
            global_batches_consumed=1,
            global_samples_consumed=2,
            committed_sample_cursor=0,
            assignment_digest="rank-assignment",
            compatibility_fingerprint="loader-compatibility",
            data_wait=DataWaitTelemetry().observe(0.01),
        )
