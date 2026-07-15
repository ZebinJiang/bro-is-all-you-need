"""R5 生产数据 schema、上游适配和混合计划契约。"""

import sys
import types
from pathlib import Path
from typing import cast

import pytest

from autovla.core.semantics import TensorLayout
from autovla.data.backends.webdataset import _local_layout, _webdataset_module
from autovla.data.contracts import DataAccessMode, DataSourceSpec
from autovla.data.datasets.local_lerobot import (
    LeRobotEpisode,
    LeRobotFeature,
    LeRobotIndexEntry,
    LocalLeRobotMetadata,
    convert_lerobot_statistics,
)
from autovla.data.mixing import (
    BatchCompositionPolicy,
    DatasetMixturePlan,
    DatasetMixtureState,
    MixtureComponent,
    MixtureSchedulePoint,
    MixtureWeightPolicy,
)
from autovla.data.schema import (
    FeatureLayout,
    FeatureRole,
    FeatureSpec,
    FrameIndex,
    SampleId,
    TemporalPaddingPolicy,
    TemporalWindow,
    Timestamp,
)


def test_lerobot_statistics_and_source_capabilities_are_canonical() -> None:
    """LeRobot ``[D]``/``[T,D]`` 统计量保持显式布局且不联网。"""
    metadata = LocalLeRobotMetadata(
        root=Path("/local/lerobot"),
        info={"codebase_version": "v3"},
        features=(
            LeRobotFeature("observation.state", "float32", (2,)),
            LeRobotFeature("action", "float32", (2, 2)),
        ),
        fps=10.0,
        total_episodes=1,
        total_frames=1,
        statistics={
            "observation.state": {"mean": [1.0, 2.0], "std": [2.0, 3.0]},
            "action": {
                "mean": [[1.0, 2.0], [3.0, 4.0]],
                "std": [[2.0, 3.0], [4.0, 5.0]],
            },
        },
        tasks=((0, "pick"),),
        episodes=(LeRobotEpisode(0, 1, ("pick",)),),
        index=(LeRobotIndexEntry(0, 0, 0, "data/0.parquet", 0, "sample-0", 0.0),),
        data_paths=("data/0.parquet",),
        media_path_templates=(),
    )
    statistics = convert_lerobot_statistics(metadata)
    assert statistics.features["observation.state"].layout == TensorLayout.feature(2)
    assert statistics.features["action"].layout == TensorLayout.time_feature(2, 2)

    spec = DataSourceSpec(
        dataset_key="local",
        backend_key="lerobot_local",
        split="train",
        access_mode=DataAccessMode.MAP,
        source_fingerprint="source",
        schema_fingerprint="schema",
        finite=True,
        sample_count=1,
        supports_batch_read=True,
        supports_temporal_query=True,
        supports_media=True,
        supports_exact_resume=True,
        compatibility_metadata={"episode_metadata": True, "statistics_metadata": True},
    )
    assert spec.capabilities.episode_metadata
    assert spec.capabilities.resume_mode == "exact"


def test_mixture_composition_replay_caps_and_exact_types() -> None:
    """混合/平衡指纹可重放, cap/replacement 和类型边界真实生效。"""
    components = (
        MixtureComponent("a", "sha-a", size=2, weight=1.0, cap=1),
        MixtureComponent("b", "sha-b", size=4, weight=3.0),
    )
    plan = DatasetMixturePlan(
        components,
        policy=MixtureWeightPolicy.SCHEDULED,
        replacement=False,
        schedule=(MixtureSchedulePoint(0, {"a": 1.0, "b": 3.0}),),
    )
    assert (
        plan.fingerprint
        == DatasetMixturePlan(
            components,
            policy=MixtureWeightPolicy.SCHEDULED,
            replacement=False,
            schedule=(MixtureSchedulePoint(0, {"b": 3.0, "a": 1.0}),),
        ).fingerprint
    )
    draw = dict(a=1, b=0)
    assert {
        plan.select(step=0, global_position=index, rank=1, worker_id=2, draw_counts=draw)
        for index in range(8)
    } == {"b"}
    replay = [
        plan.select(step=0, global_position=index, rank=1, worker_id=2) for index in range(12)
    ]
    assert replay == [
        plan.select(step=0, global_position=index, rank=1, worker_id=2) for index in range(12)
    ]
    state = DatasetMixtureState(plan.fingerprint, 12, {"a": 1, "b": 3}, {"a": 1, "b": 3})
    assert state.to_dict()["next_global_position"] == 12
    assert DatasetMixturePlan.from_dict(plan.to_dict()).fingerprint == plan.fingerprint
    assert DatasetMixtureState.from_dict(state.to_dict()).to_dict() == state.to_dict()

    policy = BatchCompositionPolicy(
        dataset_targets={"a": 1, "b": 3},
        maximum_contribution={"a": 1},
        drop_last=True,
        accumulation_steps=2,
    )
    assert policy.quotas(4, global_batch_index=0) == {"a": 1, "b": 3}
    assert BatchCompositionPolicy.from_dict(policy.to_dict()).fingerprint == policy.fingerprint
    redistributed = policy.resolve_available(4, global_batch_index=3, exhausted=("a",))
    assert redistributed == {"b": 4}
    assert (
        policy.provenance(global_batch_index=3, quotas=redistributed)[
            "batch_composition_policy_fingerprint"
        ]
        == policy.fingerprint
    )

    feature = FeatureSpec(
        "action", FeatureRole.ACTION, FeatureLayout(TensorLayout.feature(), "f32")
    )
    assert feature.required
    window = TemporalWindow(
        (SampleId("s0"),),
        (FrameIndex(0),),
        (Timestamp(0.0),),
        (True,),
        TemporalPaddingPolicy.ERROR,
    )
    assert window.valid == (True,)
    with pytest.raises((TypeError, ValueError)):
        DatasetMixturePlan(components, seed=cast(int, True))
    with pytest.raises((TypeError, ValueError)):
        DatasetMixturePlan(components, replacement=cast(bool, 1))
    with pytest.raises((TypeError, ValueError)):
        BatchCompositionPolicy(dataset_targets={"a": cast(int, True)})
    with pytest.raises((TypeError, ValueError)):
        BatchCompositionPolicy(dataset_targets={"a": 1}, drop_last=cast(bool, 1))
    with pytest.raises((TypeError, ValueError)):
        BatchCompositionPolicy(dataset_targets={"a": 1}, accumulation_steps=cast(int, True))
    with pytest.raises((TypeError, ValueError)):
        DatasetMixtureState(plan.fingerprint, cast(int, True))
    with pytest.raises((TypeError, ValueError)):
        plan.select(step=0, global_position=cast(int, True), rank=0, worker_id=0)
    with pytest.raises((TypeError, ValueError)):
        FeatureSpec("x", FeatureRole.STATE, feature.layout, required=cast(bool, 1))
    with pytest.raises((TypeError, ValueError)):
        TemporalWindow(
            (SampleId("s0"),),
            (FrameIndex(0),),
            (Timestamp(0.0),),
            (cast(bool, 1),),
            TemporalPaddingPolicy.ERROR,
        )


def test_webdataset_public_api_boundary_is_lazy_and_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """WebDataset 只解析公共构造 API, 并在 pipeline 前拒绝远程 URL。"""
    module = types.ModuleType("webdataset")
    module.__version__ = "1.0.2"
    module.WebDataset = lambda shards, **options: (shards, options)
    monkeypatch.setitem(sys.modules, "webdataset", module)
    assert _webdataset_module() is module
    with pytest.raises(ValueError, match="local shards"):
        _local_layout("https://example.invalid/data")
