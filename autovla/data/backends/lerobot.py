"""AutoVLA 本地 LeRobot v3 子集生产后端。"""

from __future__ import annotations

from collections.abc import Sequence

from autovla.config.schema import DatasetConfig
from autovla.data.backends.base import dataset_config_fingerprint
from autovla.data.contracts import (
    DataAccessMode,
    DataSourceSpec,
    TemporalQuery,
    WorkerContext,
    stable_fingerprint,
)
from autovla.data.datasets.base import local_source_fingerprint
from autovla.data.datasets.local_lerobot import (
    LocalLeRobotDataset,
    LocalLeRobotMetadata,
    inspect_local_lerobot,
)
from autovla.data.types import DataStage


class LeRobotLocalBackend:
    """仅支持本地、已固定格式证据的 LeRobot v3 子集。"""

    def __init__(self, *, temporal_query: TemporalQuery | None = None) -> None:
        """保存可选 canonical TemporalQuery 和 process-local metadata cache。"""
        self._temporal_query = temporal_query
        self._metadata_cache: dict[str, LocalLeRobotMetadata] = {}

    def _metadata(self, config: DatasetConfig) -> LocalLeRobotMetadata:
        """每个进程和根目录只解析一次 metadata surface。"""
        metadata = self._metadata_cache.get(config.root)
        if metadata is None:
            metadata = inspect_local_lerobot(config.root)
            self._metadata_cache[config.root] = metadata
        return metadata

    def _query(self, config: DatasetConfig) -> TemporalQuery | None:
        """把通用配置转换为 canonical TemporalQuery,并保留直接构造兼容。"""
        configured = config.temporal_query
        if configured is None:
            return self._temporal_query
        query = TemporalQuery(
            feature_key=configured.feature_key,
            feature_family=configured.feature_family,
            frame_offsets=tuple(configured.frame_offsets),
            timestamp_deltas=tuple(configured.timestamp_deltas),
            anchor_semantics=configured.anchor_semantics,
            fps=configured.fps,
            tolerance=configured.tolerance,
            boundary_policy=configured.boundary_policy,
            output_mask_semantics=configured.output_mask_semantics,
            action_horizon=configured.action_horizon,
        )
        if self._temporal_query is not None and self._temporal_query != query:
            raise ValueError("configured and directly supplied TemporalQuery differ")
        return query

    def describe_stream_partition_units(
        self, config: DatasetConfig, stage: DataStage
    ) -> Sequence[str]:
        """MAP 后端不声明 streaming 单元。"""
        del config, stage
        return ()

    def describe_source(self, config: DatasetConfig, stage: DataStage) -> DataSourceSpec:
        """用解析 schema 和有界文件账本构造内容敏感 MAP 规格。"""
        del stage
        metadata = self._metadata(config)
        query = self._query(config)
        identity_paths = (
            "meta/info.json",
            "meta/stats.json",
            "meta/tasks.jsonl",
            "meta/episodes.jsonl",
            "sample_index.jsonl",
            *metadata.data_paths,
        )
        source_fingerprint = local_source_fingerprint(
            metadata.root,
            identity_paths,
            semantic_identity={
                "config": dataset_config_fingerprint(config),
                "episodes": [
                    (episode.episode_index, episode.length, episode.tasks)
                    for episode in metadata.episodes
                ],
                "index": [
                    (
                        entry.global_index,
                        entry.episode_index,
                        entry.frame_index,
                        entry.data_path,
                        entry.row_in_episode,
                        entry.sample_id,
                    )
                    for entry in metadata.index
                ],
            },
        )
        return DataSourceSpec(
            dataset_key=config.name,
            backend_key="lerobot_local",
            split=config.split,
            access_mode=DataAccessMode.MAP,
            source_fingerprint=source_fingerprint,
            schema_fingerprint=stable_fingerprint(metadata.schema_identity),
            finite=True,
            sample_count=len(metadata.index),
            supports_batch_read=True,
            supports_temporal_query=True,
            supports_media=True,
            supports_exact_resume=True,
            compatibility_metadata={
                "format": "lerobot-v3-local-subset",
                "format_evidence": "lerobot-v0.5.1",
                "full_lerobot_dataset_api": False,
                "local_only": True,
                "video_dependency": (
                    "optional PyAV package required only for local video features; "
                    "no compatible version inferred"
                ),
                "temporal_query_fingerprint": "none" if query is None else query.fingerprint,
            },
        )

    def open_source(
        self, config: DatasetConfig, stage: DataStage, context: WorkerContext
    ) -> LocalLeRobotDataset:
        """在 worker 中打开 metadata-once、row-group-aware MAP 源。"""
        metadata = self._metadata(config)
        query = self._query(config)
        source = LocalLeRobotDataset(
            config,
            self.describe_source(config, stage),
            metadata,
            temporal_query=query,
        )
        source.initialize_worker(context)
        return source

    def open_dataset(self, config: DatasetConfig, stage: DataStage) -> LocalLeRobotDataset:
        """兼容入口委托同一个生产源实现。"""
        metadata = self._metadata(config)
        query = self._query(config)
        return LocalLeRobotDataset(
            config,
            self.describe_source(config, stage),
            metadata,
            temporal_query=query,
        )


def create_backend() -> LeRobotLocalBackend:
    """构造本地 LeRobot 后端。"""
    return LeRobotLocalBackend()


__all__ = ["LeRobotLocalBackend", "create_backend"]
