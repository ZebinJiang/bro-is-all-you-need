"""AutoVLA 本地 WebDataset 有限/重采样生产流式后端。"""

from __future__ import annotations

import importlib
import json
import random
import warnings
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from autovla.config.schema import DatasetConfig
from autovla.core.types.training import TrainingSample
from autovla.data.backends.base import dataset_config_fingerprint, record_to_training_sample
from autovla.data.contracts import (
    DataAccessMode,
    DataDecodeError,
    DataSchemaMismatchError,
    DataSourceSpec,
    StreamMode,
    StreamPartitionState,
    TransientLocalIOError,
    WorkerContext,
    stable_fingerprint,
)
from autovla.data.datasets.base import contained_path, local_source_fingerprint
from autovla.data.types import DataStage


def _index_rows(root: Path) -> tuple[dict[str, object], ...]:
    """读取并严格校验 WebDataset 本地样本索引。"""
    path = root / "sample_index.jsonl"
    if not path.is_file():
        return ()
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise DataSchemaMismatchError("WebDataset sample_index row must be a mapping")
        shard = value.get("shard")
        key = value.get("key")
        if not isinstance(shard, str) or not shard.strip():
            raise DataSchemaMismatchError("sample_index shard must be non-empty text")
        if not isinstance(key, str) or not key.strip():
            raise DataSchemaMismatchError("sample_index key must be non-empty text")
        contained_path(root, shard)
        rows.append(cast(dict[str, object], value))
    return tuple(rows)


def _local_layout(root: str | Path) -> tuple[Path, tuple[str, ...], tuple[dict[str, object], ...]]:
    """确定性枚举本地 shard 和索引,拒绝任何网络 URL。"""
    raw = str(root)
    parsed = urlparse(raw)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"WebDataset requires local shards, got URL scheme {parsed.scheme!r}")
    dataset_root = Path(parsed.path if parsed.scheme == "file" else raw).resolve()
    rows = _index_rows(dataset_root)
    if rows:
        shards = {contained_path(dataset_root, cast(str, row["shard"])) for row in rows}
    else:
        shards = {path.resolve() for path in dataset_root.glob("shards/*.tar") if path.is_file()}
    ordered = tuple(path.as_posix() for path in sorted(shards))
    if not ordered:
        raise ValueError(f"no complete local WebDataset shards found under {dataset_root}")
    return dataset_root, ordered, rows


def _webdataset_module() -> Any:
    """懒加载并验证 WebDataset 1.0.2 所需公共符号。"""
    try:
        module = importlib.import_module("webdataset")
    except ImportError as exc:
        raise RuntimeError(
            "WebDataset backend requires optional dependency webdataset==1.0.2; "
            "install autovla[data-webdataset]"
        ) from exc
    version = getattr(module, "__version__", None)
    if version != "1.0.2":
        raise RuntimeError(f"WebDataset backend requires webdataset==1.0.2, found {version!r}")
    if not hasattr(module, "WebDataset"):
        raise RuntimeError("webdataset==1.0.2 lacks required public symbol WebDataset")
    return module


def _tuple_tree(value: object) -> object:
    """把 JSON 恢复后的 list 树转换为 random.setstate 所需 tuple。"""
    if isinstance(value, list):
        return tuple(_tuple_tree(item) for item in value)
    return value


class WebDatasetStreamingSource:
    """只消费 AutoVLA assigned_units 的 worker-local 有限或重采样流。"""

    def __init__(
        self,
        config: DatasetConfig,
        spec: DataSourceSpec,
        *,
        handler_policy: str = "raise",
        transient_retries: int = 0,
    ) -> None:
        if handler_policy not in {"raise", "warn_and_skip"}:
            raise ValueError("WebDataset handler_policy must be raise or warn_and_skip")
        if transient_retries < 0:
            raise ValueError("WebDataset transient_retries must be non-negative")
        self._config = config
        self.spec = spec
        self._handler_policy = handler_policy
        self._transient_retries = transient_retries
        self._context: WorkerContext | None = None
        self._iterator: object | None = None
        self._pipeline: object | None = None
        root, _, rows = _local_layout(config.root)
        self._root = root
        self._keys_by_shard: dict[str, tuple[str, ...]] = {}
        for shard in spec.partition_units:
            relative = Path(shard).resolve().relative_to(root).as_posix()
            self._keys_by_shard[shard] = tuple(
                cast(str, row["key"]) for row in rows if row["shard"] == relative
            )
        self._state: dict[str, object] = {}
        self._counts = {
            "delivered": 0,
            "warn_and_skip": 0,
            "transient_retries": 0,
            "schema_failures": 0,
            "decode_failures": 0,
        }

    def initialize_worker(self, context: WorkerContext) -> None:
        """安装拥有该 pipeline 的 worker 上下文。"""
        self._context = context

    def _pipeline_handler(self, error: Exception) -> bool:
        """只在显式 warn-and-skip 策略下计数并继续。"""
        if isinstance(error, OSError):
            raise error
        if self._handler_policy == "warn_and_skip":
            self._counts["warn_and_skip"] += 1
            warnings.warn(
                f"skipping WebDataset pipeline error: {error}",
                RuntimeWarning,
                stacklevel=2,
            )
            return True
        raise error

    def _open_pipeline(self, shard: str) -> Iterator[Mapping[str, object]]:
        """为一个本地 shard 创建关闭可追踪的公共 WebDataset pipeline。"""
        self._close_pipeline()
        wds = _webdataset_module()
        self._pipeline = wds.WebDataset(
            [shard],
            shardshuffle=False,
            nodesplitter=lambda urls: urls,
            workersplitter=lambda urls: urls,
            handler=self._pipeline_handler,
        )
        self._iterator = iter(self._pipeline)
        return cast(Iterator[Mapping[str, object]], self._iterator)

    def _close_pipeline(self) -> None:
        """显式关闭 iterator、pipeline 和其拥有的 tar stream。"""
        iterator, self._iterator = self._iterator, None
        pipeline, self._pipeline = self._pipeline, None
        if iterator is not None:
            close = getattr(iterator, "close", None)
            if callable(close):
                close()
        if pipeline is not None and pipeline is not iterator:
            close = getattr(pipeline, "close", None)
            if callable(close):
                close()

    def _decode(self, raw: Mapping[str, object], shard: str) -> TrainingSample | None:
        """schema 始终 fail-fast;媒体 decode 仅按显式策略跳过。"""
        from autovla.dataloader.stores.webdataset_reader import decode_webdataset_record

        try:
            key = raw.get("__key__")
            if not isinstance(key, str) or not key.strip():
                raise DataSchemaMismatchError("WebDataset sample lacks non-empty __key__")
            record = decode_webdataset_record(raw)
            sample = record_to_training_sample(record, config=self._config)
            provenance = dict(sample.sample_source)
            provenance["physical"] = {"shard": shard, "key": key}
            return replace(sample, sample_source=provenance)
        except DataSchemaMismatchError:
            self._counts["schema_failures"] += 1
            raise
        except DataDecodeError:
            self._counts["decode_failures"] += 1
            if self._handler_policy == "warn_and_skip":
                self._counts["warn_and_skip"] += 1
                warnings.warn(
                    f"skipping WebDataset decode failure in {shard}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                return None
            raise
        except (KeyError, TypeError, ValueError) as exc:
            self._counts["schema_failures"] += 1
            raise DataSchemaMismatchError(
                f"WebDataset canonical conversion failed in {shard}"
            ) from exc

    def _next_identity(self, shard: str, offset: int) -> str | None:
        """从不可变索引返回下一条未读逻辑身份。"""
        keys = self._keys_by_shard.get(shard, ())
        return keys[offset] if offset < len(keys) else None

    def _record_position(
        self,
        *,
        shard: str,
        shard_index: int,
        next_offset: int,
        delivered_identity: object,
        state: StreamPartitionState,
        replayed: int,
        mode_state: Mapping[str, object] | None = None,
    ) -> None:
        """记录下一条未读 cursor 和刚交付身份。"""
        source_state = dict(mode_state or {})
        self._state = {
            "current_shard": shard,
            "shard_index": shard_index,
            "consumed_sample_offset": next_offset,
            "shard_rng_state": dict(state.shard_rng_state),
            "sample_rng_state": dict(state.sample_rng_state),
            "handler_counts": dict(self._counts),
            "delivered_sample_identity": delivered_identity,
            "next_unread_identity": self._next_identity(shard, next_offset),
            "next_cursor": {"shard_index": shard_index, "sample_offset": next_offset},
            "resume_replay_within_current_shard": replayed,
            "upstream_splitters_disabled": True,
            **source_state,
        }

    def _iter_shard(
        self,
        *,
        shard: str,
        start_offset: int,
    ) -> Iterator[tuple[int, Mapping[str, object]]]:
        """顺序迭代 shard;仅瞬时本地 I/O 可有界重开并重放。"""
        retries = 0
        resume_offset = start_offset
        while True:
            try:
                iterator = self._open_pipeline(shard)
                for offset, raw in enumerate(iterator):
                    if offset >= resume_offset:
                        yield offset, raw
                        resume_offset = offset + 1
                return
            except OSError as exc:
                self._close_pipeline()
                if retries >= self._transient_retries:
                    raise TransientLocalIOError(
                        f"WebDataset local I/O failed after {retries} retries: {shard}"
                    ) from exc
                retries += 1
                self._counts["transient_retries"] += 1

    def _finite(self, state: StreamPartitionState) -> Iterator[TrainingSample]:
        """一次遍历 assigned shard 列表,无隐藏重复。"""
        assigned = state.assigned_units
        start_shard = state.shard_index
        start_offset = state.consumed_sample_offset
        if state.current_shard is not None and (
            start_shard >= len(assigned) or assigned[start_shard] != state.current_shard
        ):
            raise ValueError("finite WebDataset cursor does not match assigned shard")
        for shard_index, shard in enumerate(assigned[start_shard:], start=start_shard):
            replayed = start_offset if shard_index == start_shard else 0
            for offset, raw in self._iter_shard(shard=shard, start_offset=replayed):
                sample = self._decode(raw, shard)
                if sample is None:
                    continue
                self._counts["delivered"] += 1
                self._record_position(
                    shard=shard,
                    shard_index=shard_index,
                    next_offset=offset + 1,
                    delivered_identity=cast(Mapping[str, object], sample.sample_source["physical"])[
                        "key"
                    ],
                    state=state,
                    replayed=replayed,
                    mode_state={"stream_mode": "finite_epoch"},
                )
                yield sample
            self._close_pipeline()
            start_offset = 0
            self._state.update(
                current_shard=None,
                shard_index=shard_index + 1,
                consumed_sample_offset=0,
                next_cursor={"shard_index": shard_index + 1, "sample_offset": 0},
                next_unread_identity=None,
            )

    def _resampled(self, state: StreamPartitionState) -> Iterator[TrainingSample]:
        """按确定 RNG 有放回选择 shard,严格交付 nominal epoch 长度。"""
        nominal = cast(int, self.spec.nominal_epoch_size)
        source_state = dict(state.source_state)
        delivered = int(source_state.get("resampled_draw_count", 0))
        selection_count = int(source_state.get("resampled_selection_count", 0))
        seed = int(state.sample_rng_state.get("seed", self._context.derived_worker_seed))  # type: ignore[union-attr]
        rng = random.Random(seed)
        raw_rng = source_state.get("resample_rng_state")
        if raw_rng is not None:
            rng.setstate(cast(tuple[Any, ...], _tuple_tree(raw_rng)))
        current = cast(str | None, source_state.get("resampled_current_shard"))
        raw_unit_index = source_state.get("resampled_current_unit_index")
        current_unit_index = None if raw_unit_index is None else int(cast(int, raw_unit_index))
        if current is not None and current not in state.assigned_units:
            raise ValueError("resampled WebDataset cursor contains an unassigned shard")
        if current is not None:
            expected_unit_index = state.assigned_units.index(current)
            if current_unit_index is None:
                current_unit_index = expected_unit_index
            elif current_unit_index != expected_unit_index:
                raise ValueError("resampled WebDataset unit index differs from current shard")
        elif current_unit_index is not None:
            raise ValueError("resampled WebDataset unit index requires a current shard")
        if state.current_shard is not None and current != state.current_shard:
            raise ValueError("resampled WebDataset canonical/backend cursors differ")
        if current_unit_index is not None and state.shard_index != current_unit_index:
            raise ValueError("resampled WebDataset canonical unit index differs from backend")
        offset = state.consumed_sample_offset if current is not None else 0
        while delivered < nominal:
            if current is None:
                current_unit_index = rng.randrange(len(state.assigned_units))
                current = state.assigned_units[current_unit_index]
                selection_count += 1
                offset = 0
            replayed = offset
            exhausted = True
            for sample_offset, raw in self._iter_shard(shard=current, start_offset=offset):
                exhausted = False
                sample = self._decode(raw, current)
                offset = sample_offset + 1
                if sample is None:
                    continue
                delivered += 1
                self._counts["delivered"] += 1
                mode_state = {
                    "stream_mode": "resampled",
                    "replacement": True,
                    "resampled_draw_count": delivered,
                    "resampled_selection_count": selection_count,
                    "resampled_current_shard": current,
                    "resampled_current_unit_index": current_unit_index,
                    "resample_rng_state": rng.getstate(),
                    "nominal_epoch_size": nominal,
                }
                self._record_position(
                    shard=current,
                    shard_index=cast(int, current_unit_index),
                    next_offset=offset,
                    delivered_identity=cast(Mapping[str, object], sample.sample_source["physical"])[
                        "key"
                    ],
                    state=state,
                    replayed=replayed,
                    mode_state=mode_state,
                )
                self._state["sample_rng_state"] = {
                    "seed": seed,
                    "state": rng.getstate(),
                }
                yield sample
                if delivered >= nominal:
                    self._close_pipeline()
                    return
            self._close_pipeline()
            if exhausted and offset == 0:
                raise DataSchemaMismatchError(f"resampled WebDataset shard is empty: {current}")
            current = None
            current_unit_index = None
            offset = 0

    def iter_samples(
        self, context: WorkerContext, state: StreamPartitionState
    ) -> Iterator[TrainingSample]:
        """验证 AutoVLA assignment 后执行有限或显式重采样状态机。"""
        if context != self._context:
            raise RuntimeError("WebDataset source is not initialized for this worker")
        if state.assignment_owner != "autovla_loader" or not state.upstream_partitioning_disabled:
            raise ValueError("WebDataset requires AutoVLA-owned single partitioning")
        if any(unit not in self.spec.partition_units for unit in state.assigned_units):
            raise ValueError("stream state contains undeclared WebDataset shard")
        for name, value in state.handler_counts.items():
            if name in self._counts:
                self._counts[name] = value
        try:
            if self.spec.stream_mode is StreamMode.RESAMPLED:
                yield from self._resampled(state)
            else:
                yield from self._finite(state)
        finally:
            self._close_pipeline()

    def state_dict(self) -> Mapping[str, object]:
        """返回下一未读 cursor、RNG、处理器计数和交付身份。"""
        state = dict(self._state)
        state["handler_counts"] = dict(self._counts)
        return state

    def close(self) -> None:
        """幂等关闭 iterator、pipeline 和 tar stream。"""
        self._close_pipeline()


class WebDatasetBackend:
    """描述并打开规范 STREAMING WebDataset 源。"""

    def describe_stream_partition_units(
        self, config: DatasetConfig, stage: DataStage
    ) -> Sequence[str]:
        """不打开 tar 句柄地返回稳定本地 shard 列表。"""
        del stage
        return _local_layout(config.root)[1]

    def describe_source(self, config: DatasetConfig, stage: DataStage) -> DataSourceSpec:
        """返回内容敏感、有限/重采样语义明确的不可变源规格。"""
        root, units, rows = _local_layout(config.root)
        mode = StreamMode(config.stream_mode or "finite_epoch")
        if mode is StreamMode.RESAMPLED and stage is not DataStage.TRAIN:
            raise ValueError("resampled WebDataset is forbidden outside the training stage")
        relative_units = tuple(Path(unit).relative_to(root).as_posix() for unit in units)
        identity_paths: tuple[str, ...] = (
            *(("sample_index.jsonl",) if rows else ()),
            *relative_units,
        )
        return DataSourceSpec(
            dataset_key=config.name,
            backend_key="webdataset",
            split=config.split,
            access_mode=DataAccessMode.STREAMING,
            source_fingerprint=local_source_fingerprint(
                root,
                identity_paths,
                semantic_identity={
                    "config": dataset_config_fingerprint(config),
                    "index": rows,
                    "shards": relative_units,
                },
            ),
            schema_fingerprint=stable_fingerprint(
                {
                    "format": "payload.json+camera_N.npy",
                    "image_keys": config.image_keys,
                    "language_key": config.language_key,
                    "state_key": config.state_key,
                    "action_key": config.action_key,
                    "action_mask_key": config.action_mask_key,
                }
            ),
            finite=mode is StreamMode.FINITE_EPOCH,
            sample_count=None,
            supports_batch_read=False,
            supports_temporal_query=False,
            supports_media=True,
            supports_exact_resume=True,
            partition_units=units,
            stream_mode=mode,
            nominal_epoch_size=config.nominal_epoch_size,
            compatibility_metadata={
                "format": "webdataset-1.0.2-public-api",
                "canonical_access": "streaming-only",
                "local_only": True,
                "resampled_replacement": mode is StreamMode.RESAMPLED,
            },
        )

    def open_source(
        self, config: DatasetConfig, stage: DataStage, context: WorkerContext
    ) -> WebDatasetStreamingSource:
        """在消费 worker 中构造流式源,不创建随机访问句柄。"""
        source = WebDatasetStreamingSource(config, self.describe_source(config, stage))
        source.initialize_worker(context)
        return source

    def open_dataset(self, config: DatasetConfig, stage: DataStage) -> object:
        """拒绝旧随机访问入口,避免 index restart/rescan 回归。"""
        del config, stage
        raise RuntimeError("canonical WebDataset backend is streaming-only; use open_source")


def create_backend() -> WebDatasetBackend:
    """构造 WebDataset 后端实例。"""
    return WebDatasetBackend()


__all__ = ["WebDatasetBackend", "WebDatasetStreamingSource", "create_backend"]
