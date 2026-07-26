"""AutoVLA RoboDM-container 生产 MAP 后端。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Protocol, TypeGuard

from autovla.config.schema import DatasetConfig
from autovla.core.types.training import TrainingSample
from autovla.data.backends.base import (
    dataset_config_fingerprint,
    local_sample_count,
    record_to_training_sample,
)
from autovla.data.binding.adapter import DataBackendBindingAdapter
from autovla.data.contracts import DataAccessMode, DataSourceSpec, WorkerContext, stable_fingerprint
from autovla.data.datasets.base import contained_path, local_source_fingerprint
from autovla.data.types import DataStage


class _RoboDMReader(Protocol):
    """约束 worker-local RoboDM reader 的最小接口。"""

    @property
    def counters(self) -> Mapping[str, int]: ...

    def read_records(self, indices: Sequence[int]) -> list[dict[str, object]]: ...

    def close(self) -> None: ...


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """判断动态 JSON 值是否为对象映射。"""

    return isinstance(value, Mapping)


def _string_object_mapping(value: object, name: str) -> dict[str, object]:
    """逐键校验并复制字符串键映射。"""

    if not _is_object_mapping(value):
        raise ValueError(f"{name} must be a mapping")
    output: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{name} keys must be strings")
        output[key] = item
    return output


class RoboDMContainerSource:
    """父进程仅保存不可变索引,worker 懒建有界 tar LRU。"""

    def __init__(
        self, config: DatasetConfig, spec: DataSourceSpec, *, max_handles: int = 2
    ) -> None:
        self._config = config
        self.spec = spec
        self._max_handles = max_handles
        self._reader: _RoboDMReader | None = None

    def __len__(self) -> int:
        """返回持久索引长度。"""
        return int(self.spec.sample_count or 0)

    def __getstate__(self) -> dict[str, object]:
        """pickle 时排除 worker-local reader 和 live tar handles。"""
        state = dict(self.__dict__)
        state["_reader"] = None
        return state

    def initialize_worker(self, context: WorkerContext) -> None:
        """在所属 worker 中懒建 reader。"""
        del context
        if self._reader is None:
            from autovla.dataloader.stores.robodm_reader import RoboDMGroupedReader

            self._reader = RoboDMGroupedReader(
                Path(self._config.root), max_handles=self._max_handles
            )

    def read(self, index: int) -> TrainingSample:
        """读取单个容器成员。"""
        return self.read_many((index,))[0]

    def read_many(self, indices: Sequence[int]) -> Sequence[TrainingSample]:
        """按容器分组读取并恢复请求顺序。"""
        if any(index < 0 or index >= len(self) for index in indices):
            raise IndexError("RoboDM index out of range")
        if self._reader is None:
            raise RuntimeError("RoboDM source must be initialized in its worker")
        records = self._reader.read_records(indices)
        samples: list[TrainingSample] = []
        for record in records:
            sample = record_to_training_sample(record, config=self._config)
            source = dict(sample.sample_source)
            physical = record.get("physical_source", {})
            if _is_object_mapping(physical):
                for key, value in physical.items():
                    if isinstance(key, str):
                        source[key] = value
            samples.append(replace(sample, sample_source=source))
        return tuple(samples)

    def state_dict(self) -> Mapping[str, object]:
        """返回 handle 复用、驱逐和关闭计数。"""
        counters: Mapping[str, int] = (
            dict[str, int]() if self._reader is None else self._reader.counters
        )
        return {"handle_counters": counters, "next_sample_identity": None}

    def close(self) -> None:
        """幂等关闭 worker-local handle pool。"""
        reader, self._reader = self._reader, None
        if reader is not None:
            reader.close()


class RoboDMContainerBackend:
    """描述 AutoVLA-owned、非上游原生兼容的容器格式。"""

    def binding_adapter(self) -> DataBackendBindingAdapter:
        """返回 RoboDM 身份的统一 production binding 收据适配器。"""
        return DataBackendBindingAdapter.for_backend("robodm_container")

    def describe_stream_partition_units(
        self, config: DatasetConfig, stage: DataStage
    ) -> Sequence[str]:
        """MAP 后端不声明 streaming 单元。"""
        del config, stage
        return ()

    def describe_source(self, config: DatasetConfig, stage: DataStage) -> DataSourceSpec:
        """从不可变本地索引构造 MAP 源规格。"""
        del stage
        root = Path(config.root).resolve()
        count = local_sample_count(root, config.sample_count)
        rows: list[dict[str, object]] = []
        identity_paths: list[str] = ["sample_index.jsonl"]
        index_path = root / "sample_index.jsonl"
        if index_path.is_file():
            for line in index_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                raw_row: object = json.loads(line)
                row = _string_object_mapping(raw_row, "RoboDM sample index row")
                container = row.get("container")
                member = row.get("member_prefix")
                if not isinstance(container, str) or not isinstance(member, str):
                    raise ValueError("RoboDM index requires container and member_prefix")
                contained_path(root, container)
                identity_paths.append(container)
                rows.append(row)
            source_fingerprint = local_source_fingerprint(
                root,
                identity_paths,
                semantic_identity={
                    "config": dataset_config_fingerprint(config),
                    "index": rows,
                },
            )
            local_identity = "bounded_file_ledger"
        elif config.sample_count is not None:
            source_fingerprint = stable_fingerprint(
                {
                    "config": dataset_config_fingerprint(config),
                    "declared_sample_count": config.sample_count,
                    "local_identity": "unverified_config_only",
                }
            )
            local_identity = "unverified_config_only"
        else:
            raise ValueError(f"RoboDM sample index is missing: {index_path}")
        return DataSourceSpec(
            dataset_key=config.name,
            backend_key="robodm_container",
            split=config.split,
            access_mode=DataAccessMode.MAP,
            source_fingerprint=source_fingerprint,
            schema_fingerprint=stable_fingerprint(
                {
                    "format": "payload.json+camera_N.npy",
                    "image_keys": config.image_keys,
                    "language_key": config.language_key,
                    "action_key": config.action_key,
                    "action_mask_key": config.action_mask_key,
                    "state_key": config.state_key,
                }
            ),
            finite=True,
            sample_count=count,
            supports_batch_read=True,
            supports_temporal_query=False,
            supports_media=True,
            supports_exact_resume=True,
            compatibility_metadata={
                "format": "autovla-robodm-container",
                "upstream_native_compatible": False,
                "prototype_only": True,
                "decision": "NO_BACKEND_WINNER",
                "local_identity": local_identity,
            },
        )

    def open_source(
        self, config: DatasetConfig, stage: DataStage, context: WorkerContext
    ) -> RoboDMContainerSource:
        """在 worker 中打开统一 MAP 源。"""
        source = RoboDMContainerSource(config, self.describe_source(config, stage))
        source.initialize_worker(context)
        return source

    def open_dataset(self, config: DatasetConfig, stage: DataStage) -> RoboDMContainerSource:
        """兼容入口委托同一生产源,不维护第二套读取逻辑。"""
        return RoboDMContainerSource(config, self.describe_source(config, stage))


def create_backend() -> RoboDMContainerBackend:
    """构造 RoboDM-container 后端。"""
    return RoboDMContainerBackend()


__all__ = ["RoboDMContainerBackend", "RoboDMContainerSource", "create_backend"]
