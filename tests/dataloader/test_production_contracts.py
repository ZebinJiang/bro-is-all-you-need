"""生产数据核心的契约、构造、状态和 pickle 测试。"""

from __future__ import annotations

import importlib.util
import inspect
import io
import json
import multiprocessing
import pickle
import subprocess
import sys
import tarfile
import time
from collections.abc import Mapping
from dataclasses import fields, replace
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from autovla.config.schema import (
    DataConfig,
    DataLoaderConfig,
    DatasetConfig,
    TemporalQueryConfig,
)
from autovla.core.registry import ImportStringFactory
from autovla.core.types.training import TrainingSample as CoreTrainingSample
from autovla.data.backends.base import (
    DataBackend,
    DataBackendCapabilities,
    DataBackendSpec,
    MapDataSource,
    StreamingDataSource,
)
from autovla.data.collators import PaddedBatchCollator
from autovla.data.contracts import (
    DataAccessMode,
    DataSourceSpec,
    PartitionPlan,
    SamplingPlan,
    StreamMode,
    StreamPartitionState,
    WorkerContext,
    derive_worker_seed,
    stable_fingerprint,
)
from autovla.data.loader import (
    AutoVLAMapDataset,
    AutoVLAStreamingDataset,
    PlannedBatchSampler,
    ProductionCollator,
    RuntimeTopology,
    SharedEpochDescriptor,
    SourceFactory,
    TrainingDataLoader,
    WorkerInitializer,
)
from autovla.data.module import DataModule
from autovla.data.registry import DataBackendRegistration, DataBackendRegistry
from autovla.data.sampling import PartitionContext
from autovla.data.transforms import TransformPipeline
from autovla.data.types import DataLoaderState, DataStage, TrainingSample


class _TemporalTransportBackend:
    """提供不打开数据的 backend-neutral temporal transport 探针。"""

    def describe_source(self, config: DatasetConfig, stage: DataStage) -> DataSourceSpec:
        """返回固定源身份并声明支持 temporal query。"""
        del stage
        return DataSourceSpec(
            dataset_key=config.name,
            backend_key="temporal_transport_probe",
            split=config.split,
            access_mode=DataAccessMode.MAP,
            source_fingerprint="temporal-probe-source",
            schema_fingerprint="temporal-probe-schema",
            finite=True,
            sample_count=config.sample_count or 4,
            supports_batch_read=True,
            supports_temporal_query=True,
            supports_media=False,
            supports_exact_resume=True,
        )


def create_temporal_transport_backend() -> _TemporalTransportBackend:
    """通过无参数懒工厂构造 transport 探针。"""
    return _TemporalTransportBackend()


def _temporal_transport_registry() -> DataBackendRegistry:
    """构造只含 backend-neutral transport 探针的本地注册表。"""
    registry = DataBackendRegistry("temporal-transport-test")
    spec = DataBackendSpec(
        key="temporal_transport_probe",
        aliases=(),
        capabilities=DataBackendCapabilities(
            sequential_streaming=False,
            random_access=True,
            persistent_index=False,
            grouped_reads=True,
            deterministic_partition=True,
            prototype_only=False,
            native_compatible=False,
        ),
        factory_path=f"{__name__}:create_temporal_transport_backend",
    )
    registry.register(
        spec.key,
        DataBackendRegistration(
            spec=spec,
            factory=ImportStringFactory(spec.factory_path),
        ),
    )
    return registry


def _map_spec() -> DataSourceSpec:
    """返回无外部依赖的确定性 map 源规格。"""
    return DataSourceSpec(
        dataset_key="tiny",
        backend_key="robodm_container",
        split="train",
        access_mode=DataAccessMode.MAP,
        source_fingerprint="source-fingerprint",
        schema_fingerprint="schema-fingerprint",
        finite=True,
        sample_count=4,
        supports_batch_read=True,
        supports_temporal_query=False,
        supports_media=False,
        supports_exact_resume=True,
    )


def _topology() -> RuntimeTopology:
    """返回零 worker 主进程拓扑。"""
    return RuntimeTopology(0, 0, 1, 7, "train", "none")


def _stream_spec() -> DataSourceSpec:
    """返回包含真实后端 shard 身份的 streaming 源规格。"""
    return DataSourceSpec(
        dataset_key="stream",
        backend_key="webdataset",
        split="train",
        access_mode=DataAccessMode.STREAMING,
        source_fingerprint="stream-source-fingerprint",
        schema_fingerprint="stream-schema-fingerprint",
        finite=True,
        sample_count=None,
        supports_batch_read=False,
        supports_temporal_query=False,
        supports_media=True,
        supports_exact_resume=True,
        partition_units=tuple(f"shard-{index}" for index in range(8)),
        stream_mode=StreamMode.FINITE_EPOCH,
        nominal_epoch_size=8,
    )


def _stream_loader() -> tuple[TrainingDataLoader, PartitionPlan]:
    """构造不打开后端、不导入 Torch 的 streaming loader。"""
    spec = _stream_spec()
    config = DatasetConfig(
        "stream",
        "webdataset",
        "datasets/working/webdataset",
        access_mode="streaming",
        stream_mode="finite_epoch",
        nominal_epoch_size=8,
    )
    units = tuple((0, unit_id) for unit_id in spec.partition_units)
    plan = PartitionPlan.for_streaming(
        units,
        global_rank=0,
        world_size=1,
        logical_worker_count=1,
        seed=7,
        epoch=0,
        shuffle=True,
    )
    sampling = SamplingPlan(
        DataAccessMode.STREAMING,
        2,
        False,
        7,
        stream_shard_shuffle=True,
        nominal_epoch_size=8,
        exact_resume=True,
    )
    factory = SourceFactory(
        "autovla.data.backends.webdataset:create_backend",
        config,
        DataStage.TRAIN,
        spec,
    )
    loader = TrainingDataLoader(
        factories=(factory,),
        source_specs=(spec,),
        partition_plan=plan,
        sampling_plan=sampling,
        config=DataLoaderConfig(batch_size=2, stream_shard_shuffle=True),
        topology=_topology(),
        collator=ProductionCollator(
            PaddedBatchCollator(),
            TransformPipeline(),
            "manifest-fingerprint",
            "statistics-fingerprint",
            (("stream", spec.source_fingerprint, spec.schema_fingerprint),),
        ),
        manifest_fingerprint="manifest-fingerprint",
        mix_strategy="weighted",
        mix_balance_by="dataset",
        mix_weights=(1.0,),
        base_stream_units=units,
    )
    return loader, plan


def test_contract_import_remains_torch_lazy_and_complete() -> None:
    """验证导入契约不导入 Torch 且关键字段完整。"""
    assert {item.name for item in fields(WorkerContext)} == {
        "global_rank",
        "local_rank",
        "world_size",
        "worker_id",
        "logical_worker_count",
        "actual_worker_process_count",
        "base_seed",
        "derived_worker_seed",
        "epoch",
        "split",
        "multiprocessing_start_method",
        "node_id",
        "is_main_process",
    }
    assert {
        "dataset_key",
        "backend_key",
        "split",
        "access_mode",
        "source_fingerprint",
        "schema_fingerprint",
        "finite",
        "sample_count",
        "supports_batch_read",
        "supports_temporal_query",
        "supports_media",
        "supports_exact_resume",
        "partition_units",
    }.issubset({item.name for item in fields(DataSourceSpec)})
    assert tuple(inspect.signature(MapDataSource.read_many).parameters) == (
        "self",
        "indices",
    )
    assert tuple(inspect.signature(StreamingDataSource.iter_samples).parameters) == (
        "self",
        "context",
        "state",
    )
    assert tuple(inspect.signature(DataBackend.describe_stream_partition_units).parameters) == (
        "self",
        "config",
        "stage",
    )
    assert CoreTrainingSample is TrainingSample


def test_data_contract_and_module_setup_remain_torch_lazy_in_fresh_process() -> None:
    """在全新解释器中证明数据契约导入和零 worker setup 不加载 Torch。"""
    script = """
import sys
from autovla.config.schema import DataConfig, DatasetConfig
from autovla.data.module import DataModule
from autovla.data.types import DataStage

module = DataModule(DataConfig(datasets=(DatasetConfig(
    "tiny", "robodm_container", "unused", sample_count=4
),)))
module.setup(DataStage.TRAIN)
assert module.train_dataloader().torch_loader_created is False
assert "torch" not in sys.modules, sorted(name for name in sys.modules if name.startswith("torch"))
module.close()
print("PASS_TORCH_LAZY_DATA_SETUP")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PASS_TORCH_LAZY_DATA_SETUP"


def test_partition_plans_split_map_by_rank_and_stream_by_worker_once() -> None:
    """验证 map 不做 worker 二次切分,stream 先 rank 后 worker。"""
    map_plan = PartitionPlan.for_map(
        tuple((0, index) for index in range(12)),
        global_rank=1,
        world_size=2,
        batch_size=2,
        seed=7,
        epoch=0,
        shuffle=False,
        policy="exact_no_pad",
    )
    stream_plan = PartitionPlan.for_streaming(
        tuple((0, value) for value in ("a", "b", "c", "d", "e", "f")),
        global_rank=1,
        world_size=2,
        logical_worker_count=2,
        seed=7,
        epoch=0,
        shuffle=False,
    )

    assert map_plan.rank_sequence == tuple((0, index) for index in (1, 3, 5, 7, 9, 11))
    assert map_plan.worker_assignments == ()
    assert stream_plan.rank_sequence == ((0, "b"), (0, "d"), (0, "f"))
    assert stream_plan.worker_assignments == (
        ((0, "b"), (0, "f")),
        ((0, "d"),),
    )
    assert len(stream_plan.worker_assignment_digests) == 2
    next_epoch = PartitionPlan.for_streaming(
        tuple((0, value) for value in ("a", "b", "c", "d", "e", "f")),
        global_rank=1,
        world_size=2,
        logical_worker_count=2,
        seed=7,
        epoch=1,
        shuffle=False,
    )
    assert next_epoch.permutation_seed != stream_plan.permutation_seed
    assert next_epoch.sequence_digest != stream_plan.sequence_digest
    assert next_epoch.worker_assignment_digests != stream_plan.worker_assignment_digests


def test_config_rejects_worker_and_cross_mode_misconfiguration() -> None:
    """验证 worker-only、fork 和 map/stream 混用都 fail closed。"""
    with pytest.raises(ValueError, match="prefetch_factor requires"):
        DataLoaderConfig(prefetch_factor=2)
    with pytest.raises(ValueError, match="timeout_seconds requires"):
        DataLoaderConfig(timeout_seconds=1.0)
    with pytest.raises(ValueError, match="canonical NumPy-backed TrainingBatch"):
        DataLoaderConfig(pin_memory=True)
    with pytest.raises(ValueError, match=r"one of.*spawn.*forkserver"):
        DataLoaderConfig(num_workers=1, multiprocessing_context="fork")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="map data cannot"):
        DataConfig(loader=DataLoaderConfig(stream_shard_shuffle=True))
    with pytest.raises(ValueError, match="mixed map and streaming"):
        DataConfig(
            datasets=(
                DatasetConfig("map", "robodm_container", "map", sample_count=1),
                DatasetConfig(
                    "stream",
                    "webdataset",
                    "stream",
                    access_mode="streaming",
                    stream_mode="finite_epoch",
                    nominal_epoch_size=1,
                ),
            )
        )


def test_data_module_constructs_source_driven_loader_without_opening_sources() -> None:
    """验证 setup 只建描述,没有同步 batch executor 或 Torch/runtime handle。"""
    config = DataConfig(
        datasets=(
            DatasetConfig(
                name="tiny",
                backend="robodm_container",
                root="unused",
                sample_count=4,
            ),
        ),
        loader=DataLoaderConfig(batch_size=2),
    )
    module = DataModule(config)
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()

    assert isinstance(loader, TrainingDataLoader)
    assert loader.source_specs[0].dataset_key == "tiny"
    manifest = module.dataset_manifest()
    assert manifest.source_fingerprints == (loader.source_specs[0].source_fingerprint,)
    assert manifest.schema_fingerprints == (loader.source_specs[0].schema_fingerprint,)
    assert (
        replace(
            manifest,
            source_fingerprints=("changed-source-fingerprint",),
        ).fingerprint
        != manifest.fingerprint
    )
    assert (
        replace(
            manifest,
            schema_fingerprints=("changed-schema-fingerprint",),
        ).fingerprint
        != manifest.fingerprint
    )
    assert loader.torch_loader_created is False
    assert "_BatchLoader" not in inspect.getsource(sys.modules[DataModule.__module__])
    assert loader.state_dict()["committed_batch_cursor"] == 0
    module.close()


def test_data_module_preserves_bound_local_rank_as_runtime_fact() -> None:
    """验证 DataModule 不再伪造 local_rank=0。"""
    config = DataConfig(
        datasets=(DatasetConfig("tiny", "robodm_container", "unused", sample_count=4),)
    )
    module = DataModule(config, partition=PartitionContext(rank=3, local_rank=1, world_size=4))
    module.setup(DataStage.TRAIN)

    assert module.train_dataloader().runtime_topology.local_rank == 1
    module.close()


def test_temporal_query_survives_data_module_factory_pickle_and_resume_guard() -> None:
    """验证查询经规范工厂链传输并在恢复前拒绝漂移。"""
    query = TemporalQueryConfig(
        feature_key="action",
        feature_family="action",
        frame_offsets=(-1, 0, 1),
        anchor_semantics="sample",
        boundary_policy="pad",
        action_horizon=3,
    )
    dataset = DatasetConfig(
        "temporal-source",
        "temporal_transport_probe",
        "unused",
        sample_count=4,
        temporal_query=query,
    )
    module = DataModule(
        DataConfig(datasets=(dataset,)),
        backend_registry=_temporal_transport_registry(),
    )
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    factory = loader.source_factories[0]
    state = loader.state_dict()
    temporal_state = state["temporal_query_state"]

    assert not inspect.signature(create_temporal_transport_backend).parameters
    assert factory.config.temporal_query is query
    assert pickle.loads(pickle.dumps(factory)).config.temporal_query == query
    assert module.dataset_manifest().temporal_query_fingerprints == (query.fingerprint,)
    assert isinstance(temporal_state, dict)
    assert temporal_state == {
        "sources": [
            {
                "dataset_key": "temporal-source",
                "query_fingerprint": query.fingerprint,
                "query": query.to_dict(),
            }
        ]
    }

    changed_query = replace(query, frame_offsets=(0, 1, 2))
    changed_module = DataModule(
        DataConfig(datasets=(replace(dataset, temporal_query=changed_query),)),
        backend_registry=_temporal_transport_registry(),
    )
    changed_module.setup(DataStage.TRAIN)
    changed_loader = changed_module.train_dataloader()
    unchanged_state = changed_loader.state_dict()

    with pytest.raises(ValueError, match="temporal_query_fingerprint"):
        changed_loader.load_state_dict(state)
    assert changed_loader.state_dict() == unchanged_state
    changed_module.close()
    module.close()


def test_loader_state_is_complete_strict_and_rejects_compatibility_drift() -> None:
    """验证 v2 状态无占位身份并在应用前拒绝运行契约漂移。"""
    config = DataConfig(
        datasets=(DatasetConfig("tiny", "robodm_container", "unused", sample_count=4),),
        loader=DataLoaderConfig(batch_size=2),
    )
    module = DataModule(config)
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    state = dict(loader.state_dict())
    restored = DataLoaderState.from_dict(state)

    assert restored.schema_version == "autovla.data_loader_state.v2"
    assert restored.source_fingerprints == (loader.source_specs[0].source_fingerprint,)
    assert "manifest-owned" not in repr(state)
    assert restored.map_sampler_state["rank_assignment_digest"]
    for field_name in ("source_fingerprints", "schema_fingerprints"):
        bad_identity = dict(state)
        bad_identity[field_name] = [f"changed-{field_name}"]
        with pytest.raises(ValueError, match="resume mismatch"):
            loader.load_state_dict(bad_identity)
        assert loader.state_dict() == state
    bad_batch = dict(state)
    bad_batch["batch_size"] = 3
    with pytest.raises(ValueError, match="resume mismatch"):
        loader.validate_state(bad_batch)
    assert loader.state_dict() == state
    with pytest.raises(ValueError, match="fields mismatch"):
        DataLoaderState.from_dict({"schema_version": DataLoaderState.SCHEMA_VERSION})
    module.close()


def test_top_level_dataset_collator_initializer_and_factory_are_pickle_safe() -> None:
    """验证 spawn/forkserver 会传递的对象可由标准 pickle 往返。"""
    descriptor = SharedEpochDescriptor(None, 0, 7)
    topology = _topology()
    source_factory = SourceFactory(
        "autovla.data.backends.robodm:create_backend",
        DatasetConfig("tiny", "robodm_container", "unused", sample_count=4),
        DataStage.TRAIN,
        _map_spec(),
    )
    stream_spec = _stream_spec()
    stream_factory = SourceFactory(
        "autovla.data.backends.webdataset:create_backend",
        DatasetConfig(
            "stream",
            "webdataset",
            "datasets/working/webdataset",
            access_mode="streaming",
            stream_mode="finite_epoch",
            nominal_epoch_size=8,
        ),
        DataStage.TRAIN,
        stream_spec,
    )
    objects = (
        source_factory,
        AutoVLAMapDataset((source_factory,), topology, descriptor),
        ProductionCollator(
            PaddedBatchCollator(),
            TransformPipeline(),
            "manifest-fingerprint",
            "statistics-fingerprint",
            (("tiny", _map_spec().source_fingerprint, _map_spec().schema_fingerprint),),
        ),
        WorkerInitializer(topology, descriptor),
        PlannedBatchSampler(((0, 0), (0, 1)), 2, False),
        AutoVLAStreamingDataset(
            (stream_factory,),
            topology,
            descriptor,
            tuple((0, unit_id) for unit_id in stream_spec.partition_units),
            SamplingPlan(
                DataAccessMode.STREAMING,
                2,
                False,
                7,
                nominal_epoch_size=8,
            ),
        ),
    )

    for value in objects:
        restored = pickle.loads(pickle.dumps(value))
        assert type(restored) is type(value)


def _write_spawn_robodm_fixture(root: Path, *, sample_count: int = 4) -> None:
    """写入跨两个 worker 可确定性遍历的最小 RoboDM fixture。"""
    container = root / "containers" / "tiny.tar"
    container.parent.mkdir(parents=True)
    index_rows: list[dict[str, object]] = []
    with tarfile.open(container, "w") as archive:
        for index in range(sample_count):
            prefix = f"sample-{index}"
            payload = {
                "language": "pick the block",
                "action": [[float(index), float(index + 1)]],
                "action_mask": [[True, True]],
                "state": [float(index), 1.0],
                "sample_id": f"sample-{index:06d}",
            }
            camera_buffer = io.BytesIO()
            np.save(
                camera_buffer,
                np.full((2, 2, 3), index, dtype=np.uint8),
                allow_pickle=False,
            )
            for name, content in (
                (f"{prefix}/payload.json", json.dumps(payload).encode("utf-8")),
                (f"{prefix}/camera_0.npy", camera_buffer.getvalue()),
            ):
                member = tarfile.TarInfo(name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
            index_rows.append({"container": "containers/tiny.tar", "member_prefix": prefix})
    (root / "sample_index.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in index_rows),
        encoding="utf-8",
    )


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="Torch unavailable; actual spawned DataLoader proof requires the selected runtime",
)
def test_spawn_workers_persist_across_epochs_and_close_without_children(tmp_path: Path) -> None:
    """真实 spawn worker=2 完成两 epoch、复用 PID 并在关闭后全部退出。"""
    root = tmp_path / "robodm-spawn"
    _write_spawn_robodm_fixture(root)
    module = DataModule(
        DataConfig(
            datasets=(
                DatasetConfig(
                    "tiny",
                    "robodm_container",
                    str(root),
                    sample_count=4,
                ),
            ),
            loader=DataLoaderConfig(
                batch_size=1,
                num_workers=2,
                persistent_workers=True,
                prefetch_factor=2,
                multiprocessing_context="spawn",
            ),
        )
    )
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    first_pids: tuple[int, ...] = ()
    try:
        first = [str(batch.sample_source[0]["sample_id"]) for batch in loader]
        first_telemetry = dict(loader.runtime_telemetry)
        first_pids = cast(tuple[int, ...], first_telemetry["observed_worker_pids"])
        second = [str(batch.sample_source[0]["sample_id"]) for batch in loader]
        second_telemetry = dict(loader.runtime_telemetry)
        assert first == second == [f"sample-{index:06d}" for index in range(4)]
        assert len(set(first)) == 4
        assert first_telemetry["observed_worker_ids"] == (0, 1)
        assert len(first_pids) == 2
        assert second_telemetry["observed_worker_pids"] == first_pids
        backend_states = cast(
            Mapping[str, Mapping[str, object]],
            second_telemetry["backend_states"],
        )
        backend_state = backend_states["tiny"]
        handle_counters = cast(Mapping[str, int], backend_state["handle_counters"])
        assert handle_counters["opens"] >= 1
        assert handle_counters["cache_hits"] >= 1
    finally:
        module.close()
    deadline = time.monotonic() + 5.0
    alive = set(first_pids)
    while alive and time.monotonic() < deadline:
        alive &= {child.pid for child in multiprocessing.active_children()}
        if alive:
            time.sleep(0.05)
    assert not alive


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="Torch unavailable; fresh-process DataLoader resume proof requires the selected runtime",
)
def test_fresh_process_resume_delivers_exact_next_sample(tmp_path: Path) -> None:
    """独立解释器保存游标后恢复,首个交付身份必须是精确下一样本。"""
    root = tmp_path / "robodm-resume"
    state_path = tmp_path / "data-state.json"
    _write_spawn_robodm_fixture(root)
    script = """
import json
import sys
from pathlib import Path
from autovla.config.schema import DataConfig, DataLoaderConfig, DatasetConfig
from autovla.data.module import DataModule
from autovla.data.types import DataStage

mode, root_text, state_text = sys.argv[1:]
module = DataModule(DataConfig(
    datasets=(DatasetConfig("tiny", "robodm_container", root_text, sample_count=4),),
    loader=DataLoaderConfig(batch_size=1),
))
module.setup(DataStage.TRAIN)
if mode == "resume":
    module.load_state_dict(json.loads(Path(state_text).read_text(encoding="utf-8")))
batch = next(iter(module.train_dataloader()))
print(batch.sample_source[0]["sample_id"])
if mode == "save":
    Path(state_text).write_text(json.dumps(module.state_dict()), encoding="utf-8")
module.close()
"""

    def run(mode: str) -> subprocess.CompletedProcess[str]:
        """执行一个全新解释器阶段。"""
        return subprocess.run(
            [sys.executable, "-c", script, mode, str(root), str(state_path)],
            cwd=Path(__file__).resolve().parents[2],
            check=False,
            capture_output=True,
            text=True,
        )

    saved = run("save")
    assert saved.returncode == 0, saved.stderr
    assert saved.stdout.strip() == "sample-000000"
    resumed = run("resume")
    assert resumed.returncode == 0, resumed.stderr
    assert resumed.stdout.strip() == "sample-000001"


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="Torch unavailable in AC3 writer environment; actual DataLoader runtime deferred",
)
def test_real_torch_loader_is_constructed_only_when_iteration_starts(
    tmp_path: Path,
) -> None:
    """在可用环境中验证 production facade 延迟构造标准 Torch loader。"""
    root = tmp_path / "robodm"
    container = root / "containers" / "tiny.tar"
    container.parent.mkdir(parents=True)
    payload = {
        "language": "pick the block",
        "action": [[0.25, -0.5]],
        "action_mask": [[True, True]],
        "state": [0.0, 1.0],
        "sample_id": "tiny-0",
    }
    camera_buffer = io.BytesIO()
    np.save(camera_buffer, np.zeros((2, 2, 3), dtype=np.uint8), allow_pickle=False)
    with tarfile.open(container, "w") as archive:
        for name, content in (
            ("sample-0/payload.json", json.dumps(payload).encode("utf-8")),
            ("sample-0/camera_0.npy", camera_buffer.getvalue()),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    (root / "sample_index.jsonl").write_text(
        json.dumps({"container": "containers/tiny.tar", "member_prefix": "sample-0"}) + "\n",
        encoding="utf-8",
    )
    config = DataConfig(
        datasets=(DatasetConfig("tiny", "robodm_container", str(root), sample_count=1),),
        loader=DataLoaderConfig(batch_size=1, num_workers=0),
    )
    module = DataModule(config)
    try:
        module.setup(DataStage.TRAIN)
        loader = module.train_dataloader()

        assert loader.torch_loader_created is False
        iterator = iter(loader)
        batch = next(iterator)
        assert loader.torch_loader_created is True
        assert batch.language == ("pick the block",)
        assert batch.actions.shape == (1, 1, 2)
        assert batch.sample_source[0]["sample_id"] == "tiny-0"
    finally:
        module.close()


def test_sampling_plan_requires_serialized_stream_shuffle_state() -> None:
    """验证 exact stream resume 不接受未序列化 sample buffer。"""
    with pytest.raises(ValueError, match="stream_sample_shuffle_buffer=0"):
        SamplingPlan(
            DataAccessMode.STREAMING,
            2,
            False,
            7,
            stream_sample_shuffle_buffer=4,
            nominal_epoch_size=8,
            exact_resume=True,
        )
    spec = DataSourceSpec(
        dataset_key="stream",
        backend_key="webdataset",
        split="train",
        access_mode=DataAccessMode.STREAMING,
        source_fingerprint="source",
        schema_fingerprint="schema",
        finite=False,
        sample_count=None,
        supports_batch_read=False,
        supports_temporal_query=False,
        supports_media=True,
        supports_exact_resume=True,
        partition_units=("shard-0",),
        stream_mode=StreamMode.RESAMPLED,
        nominal_epoch_size=8,
    )
    assert spec.stream_mode is StreamMode.RESAMPLED


def test_production_collation_preserves_ordered_source_and_physical_provenance() -> None:
    """验证混合数据的 store/source/schema 和物理来源按样本顺序保留。"""

    def sample(
        dataset_key: str,
        store_fingerprint: str,
        container: str,
        member: str,
        frame_index: int,
    ) -> TrainingSample:
        """构造携带 backend 物理与逻辑来源的最小样本。"""
        return TrainingSample(
            images={"front": np.full((2, 2, 3), frame_index, dtype=np.uint8)},
            language=f"sample-{frame_index}",
            actions=np.asarray([[frame_index, frame_index + 1]], dtype=np.float32),
            action_mask=np.ones((1, 2), dtype=np.bool_),
            sample_source={
                "dataset": dataset_key,
                "physical": {"container": container, "member": member},
                "logical": {"frame_index": frame_index},
            },
            dataset_fingerprint=store_fingerprint,
            transform_fingerprint="backend-transform",
            statistics_fingerprint="backend-statistics",
        )

    collator = ProductionCollator(
        PaddedBatchCollator(),
        TransformPipeline(),
        "dataset-manifest-fingerprint",
        "resolved-statistics-fingerprint",
        (
            ("source-a", "source-fingerprint-a", "schema-fingerprint-a"),
            ("source-b", "source-fingerprint-b", "schema-fingerprint-b"),
        ),
    )
    batch = collator(
        (
            sample("source-b", "store-fingerprint-b", "b.tar", "2.json", 2),
            sample("source-a", "store-fingerprint-a", "a.tar", "1.json", 1),
        )
    )

    assert batch.dataset_fingerprint == "dataset-manifest-fingerprint"
    assert batch.dataset_manifest_fingerprint == "dataset-manifest-fingerprint"
    assert batch.store_fingerprints == (
        "store-fingerprint-b",
        "store-fingerprint-a",
    )
    assert batch.source_fingerprints == (
        "source-fingerprint-b",
        "source-fingerprint-a",
    )
    assert batch.schema_fingerprints == (
        "schema-fingerprint-b",
        "schema-fingerprint-a",
    )
    assert batch.sample_source[0]["physical"] == {
        "container": "b.tar",
        "member": "2.json",
    }
    assert batch.sample_source[1]["physical"] == {
        "container": "a.tar",
        "member": "1.json",
    }
    assert batch.sample_source[0]["logical"] == {"frame_index": 2}
    assert batch.sample_source[1]["logical"] == {"frame_index": 1}


def test_stream_resume_state_binds_assignment_rng_and_backend_state() -> None:
    """验证恢复状态保留后端载荷并绑定当前 epoch 的 worker assignment。"""
    loader, plan = _stream_loader()
    assignment = tuple(unit_id for _, unit_id in plan.worker_assignments[0])
    worker_state = StreamPartitionState(
        worker_id=0,
        epoch=0,
        assignment_owner="autovla_loader",
        assigned_units=assignment,
        upstream_partitioning_disabled=True,
        assignment_digest=stable_fingerprint({"epoch": 0, "assigned_units": assignment}),
        shard_order_digest=plan.sequence_digest,
        current_shard=assignment[0],
        shard_rng_state={"seed": plan.permutation_seed, "shuffle": True},
        sample_rng_state={
            "seed": derive_worker_seed(
                base_seed=7,
                epoch=0,
                global_rank=0,
                split="train",
                worker_id=0,
            )
        },
        source_state={"backend_cursor": "member-3"},
    )
    state = dict(loader.state_dict())
    state["stream_partition_states"] = {"stream:0": worker_state.to_dict()}
    state["stream_rng_state"] = {
        "stream:0": {
            "shard_rng_state": dict(worker_state.shard_rng_state),
            "sample_rng_state": dict(worker_state.sample_rng_state),
        }
    }

    restored = loader.validate_state(state)
    restored_worker = StreamPartitionState.from_dict(
        restored.stream_partition_states["stream:0"]  # type: ignore[arg-type]
    )
    assert restored.sample_shuffle_resume_policy == "disabled_for_exact_resume"
    assert restored.sample_shuffle_buffer_state == {
        "policy": "disabled_for_exact_resume",
        "buffer_size": 0,
        "serialized": True,
    }
    assert restored_worker.source_state == {"backend_cursor": "member-3"}

    bad = dict(state)
    bad_generator = dict(state["generator_state"])  # type: ignore[arg-type]
    bad_generator["epoch"] = 1
    bad["generator_state"] = bad_generator
    with pytest.raises(ValueError, match="generator state differs"):
        loader.validate_state(bad)
    loader.close()
