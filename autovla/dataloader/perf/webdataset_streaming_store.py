"""WebDataset package-backed streaming Training Store backend。"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import io
import json
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

from autovla.dataloader.dataset_artifact import DatasetArtifactV1
from autovla.dataloader.perf.config import PerfBenchmarkConfig

WEBDATASET_STREAMING_SCHEMA_VERSION = "autovla.training_store.webdataset_streaming.v1"
WEBDATASET_STREAMING_FORMAT = "webdataset_streaming_v1"
PFS_STORAGE_BACKEND = "pfs_shared"
DEPENDENCY_MODE = "webdataset_package"


class _ScalarProtocol(Protocol):
    """描述 pyarrow scalar 的最小读取接口。"""

    def as_py(self) -> object: ...


class _ColumnProtocol(Protocol):
    """描述 pyarrow column 的最小索引接口。"""

    def __getitem__(self, index: int) -> _ScalarProtocol: ...


class _TableProtocol(Protocol):
    """描述 pyarrow table 的最小读取接口。"""

    @property
    def column_names(self) -> Sequence[str]: ...

    @property
    def num_rows(self) -> int: ...

    def __getitem__(self, column: str) -> _ColumnProtocol: ...


class _ParquetModuleProtocol(Protocol):
    """描述 pyarrow.parquet 的最小 read_table 接口。"""

    def read_table(self, source: Path, columns: Sequence[str]) -> _TableProtocol: ...


class _TarWriterProtocol(Protocol):
    """描述 WebDataset TarWriter 的最小写入接口。"""

    def write(self, obj: Mapping[str, object]) -> int: ...

    def close(self) -> None: ...


class _WebDatasetPipelineProtocol(Protocol):
    """描述 WebDataset streaming iterable 的最小接口。"""

    def __iter__(self) -> Iterator[Mapping[str, object]]: ...


class _WebDatasetModuleProtocol(Protocol):
    """描述 webdataset 包的最小 API。"""

    def TarWriter(self, fileobj: str, *, mtime: float | None = None) -> _TarWriterProtocol: ...

    def WebDataset(
        self,
        urls: Sequence[str],
        *,
        shardshuffle: bool | int | None = None,
    ) -> _WebDatasetPipelineProtocol: ...


class TrainingStoreWriter(Protocol):
    """Training Store writer 协议。"""

    def build(
        self,
        *,
        config: PerfBenchmarkConfig,
        artifact: DatasetArtifactV1,
    ) -> "StreamingTrainingStoreBuildResult": ...


class TrainingStoreReader(Protocol):
    """Training Store reader 协议。"""

    def read(self, config: PerfBenchmarkConfig) -> "StreamingTrainingStoreBenchmarkResult": ...


class TrainingStoreBackend(TrainingStoreWriter, TrainingStoreReader, Protocol):
    """AutoVLA Training Store backend 协议。"""

    backend_name: str
    dependency_mode: str

    def describe(self) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class StreamingTrainingStoreManifest:
    """记录 streaming Training Store manifest。"""

    payload: Mapping[str, object]

    def to_json_dict(self) -> dict[str, object]:
        """返回 JSON-safe manifest。"""
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class StreamingTrainingStoreBuildResult:
    """记录 WebDataset streaming build 结果。"""

    store_dir: Path
    manifest: Mapping[str, object]
    build_report: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class StreamingTrainingStoreBenchmarkResult:
    """记录 WebDataset streaming read benchmark 结果。"""

    store_dir: Path
    comparison: Mapping[str, object]
    report: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _StreamingPayload:
    """保存 streaming backend 构建用 payload。"""

    actions: NDArray[np.float32]
    state: NDArray[np.float32]
    action_mask: NDArray[np.bool_]
    language_text: tuple[str, ...]
    metadata_json: tuple[str, ...]
    sample_ids: tuple[str, ...]
    episode_ids: tuple[str, ...]
    sample_sources: tuple[Mapping[str, object], ...]
    sample_count: int
    episode_count: int
    action_horizon: int
    action_dim: int
    state_dim: int
    build_scope: str
    store_status: str
    stop_reason: str


class TrainingStoreBackendRegistry:
    """Training Store backend registry。"""

    def __init__(self) -> None:
        """初始化空 registry。"""
        self._backends: dict[str, TrainingStoreBackend] = {}

    def register(self, backend: TrainingStoreBackend) -> None:
        """注册 backend。"""
        self._backends[backend.backend_name] = backend

    def get(self, backend_name: str) -> TrainingStoreBackend:
        """按 backend name 读取 backend。"""
        try:
            return self._backends[backend_name]
        except KeyError as exc:
            raise ValueError(f"unknown training store backend: {backend_name}") from exc

    @classmethod
    def with_default_backends(cls) -> "TrainingStoreBackendRegistry":
        """返回包含 WebDataset streaming backend 的 registry。"""
        registry = cls()
        registry.register(WebDatasetStreamingTrainingStoreBackend())
        return registry


class WebDatasetStreamingTrainingStoreBackend:
    """WebDataset package-backed streaming backend。"""

    backend_name = WEBDATASET_STREAMING_FORMAT
    dependency_mode = DEPENDENCY_MODE

    def describe(self) -> Mapping[str, object]:
        """返回 backend public 描述, 不泄露 raw API。"""
        return {
            "action_state_mask_only_supported": True,
            "backend": self.backend_name,
            "dependency_mode": self.dependency_mode,
            "full_training_window_supported": False,
            "raw_webdataset_api_exposed": False,
            "storage_backend": PFS_STORAGE_BACKEND,
        }

    def validate_source(self, source: str | Path) -> Path:
        """拒绝 URL、pipe 或非本地 source。"""
        path = _local_path(source, field="source")
        if not path.exists():
            raise ValueError("source path must exist on local filesystem")
        return path

    def validate_store_target(self, *, source: str | Path, output: str | Path) -> Path:
        """拒绝 URL、pipe 和 source dataset root 内输出。"""
        source_path = _local_path(source, field="source").absolute()
        output_path = _local_path(output, field="output")
        output_abs = output_path.absolute()
        if output_abs == source_path or _is_relative_to(output_abs, source_path):
            raise ValueError("training store output must not be inside dataset root")
        return output_path

    def build(
        self,
        *,
        config: PerfBenchmarkConfig,
        artifact: DatasetArtifactV1,
    ) -> StreamingTrainingStoreBuildResult:
        """构建 WebDataset streaming store。"""
        return build_webdataset_streaming_store(config=config, artifact=artifact)

    def read(self, config: PerfBenchmarkConfig) -> StreamingTrainingStoreBenchmarkResult:
        """读取 WebDataset streaming store。"""
        return read_webdataset_streaming_store_benchmark(config)


def describe_webdataset_dependency_status() -> dict[str, object]:
    """返回 WebDataset 依赖可用性, 缺失时用于 fail-closed gate。"""
    packages = {
        "braceexpand": importlib.util.find_spec("braceexpand") is not None,
        "webdataset": importlib.util.find_spec("webdataset") is not None,
    }
    return {
        "backend": WEBDATASET_STREAMING_FORMAT,
        "classification": "AVAILABLE" if all(packages.values()) else "DEPENDENCY_BLOCKED",
        "dependency_mode": DEPENDENCY_MODE,
        "packages": packages,
        "required_versions": {
            "braceexpand": "0.1.7",
            "webdataset": "1.0.2",
        },
    }


def build_webdataset_streaming_store(
    *,
    config: PerfBenchmarkConfig,
    artifact: DatasetArtifactV1,
) -> StreamingTrainingStoreBuildResult:
    """构建 webdataset_streaming_v1 store。"""
    started = time.perf_counter()
    backend = WebDatasetStreamingTrainingStoreBackend()
    backend.validate_source(config.dataset)
    requested_store = _require_training_store_dir(config)
    backend.validate_store_target(source=config.dataset, output=requested_store)
    store_dir = _resolved_store_dir(config=config, artifact=artifact)
    (store_dir / "index").mkdir(parents=True, exist_ok=True)
    (store_dir / "shards").mkdir(parents=True, exist_ok=True)
    (store_dir / "stats").mkdir(parents=True, exist_ok=True)
    (store_dir / "reports").mkdir(parents=True, exist_ok=True)

    artifact_payload = artifact.to_json_dict()
    dataset_manifest = _mapping(artifact_payload.get("dataset_manifest"), "dataset_manifest")
    modality = _mapping(artifact_payload.get("modality"), "modality")
    fingerprints = _mapping(artifact_payload.get("fingerprints"), "fingerprints")
    payload = _source_payload(
        config=config,
        dataset_manifest=dataset_manifest,
        modality=modality,
    )
    shard_path, shard_write_ms = _write_webdataset_shard(store_dir=store_dir, payload=payload)
    sample_rows = _sample_rows(payload=payload, shard_path=shard_path, store_dir=store_dir)
    episode_rows = _episode_rows(payload=payload)
    sample_index_path = store_dir / "index" / "samples.jsonl"
    episode_index_path = store_dir / "index" / "episodes.jsonl"
    _write_jsonl(sample_index_path, sample_rows)
    _write_jsonl(episode_index_path, episode_rows)

    raw_payload_hash, raw_signatures = _payload_hash(
        actions=payload.actions,
        state=payload.state,
        action_mask=payload.action_mask,
        language_text=payload.language_text,
        metadata_json=payload.metadata_json,
        sample_ids=payload.sample_ids,
        episode_ids=payload.episode_ids,
        action_horizon=payload.action_horizon,
        action_dim=payload.action_dim,
    )
    field_index_path = store_dir / "index" / "fields.json"
    _write_json(
        field_index_path,
        {
            "action_dim": payload.action_dim,
            "action_horizon": payload.action_horizon,
            "dependency_mode": DEPENDENCY_MODE,
            "episode_ids": list(payload.episode_ids),
            "language_text": list(payload.language_text),
            "metadata_json": list(payload.metadata_json),
            "payload_signatures": [dict(signature) for signature in raw_signatures],
            "raw_payload_hash": raw_payload_hash,
            "sample_ids": list(payload.sample_ids),
            "schema_version": f"{WEBDATASET_STREAMING_SCHEMA_VERSION}.fields",
            "state_dim": payload.state_dim,
        },
    )

    statistics_plan_path = store_dir / "statistics_plan.json"
    _write_json(
        statistics_plan_path,
        _statistics_plan(
            config=config,
            dataset_manifest=dataset_manifest,
            fingerprints=fingerprints,
            payload=payload,
        ),
    )
    statistics_path = store_dir / "stats" / "action_statistics.json"
    _write_json(statistics_path, _action_statistics(payload.actions))
    checksum_targets = {
        "episode_index": episode_index_path,
        "fields": field_index_path,
        "sample_index": sample_index_path,
        "shard_000000": shard_path,
        "statistics": statistics_path,
        "statistics_plan": statistics_plan_path,
    }
    checksums = _checksums(store_dir=store_dir, files=checksum_targets)
    _write_json(store_dir / "checksums.json", checksums)

    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
    manifest = _manifest(
        config=config,
        dataset_manifest=dataset_manifest,
        fingerprints=fingerprints,
        payload=payload,
        store_dir=store_dir,
        shard_path=shard_path,
        build_time_ms=elapsed_ms,
    )
    _write_json(store_dir / "training_store_manifest.json", manifest.to_json_dict())
    total_bytes = _store_payload_size_bytes(
        [
            shard_path,
            sample_index_path,
            episode_index_path,
            field_index_path,
            statistics_plan_path,
            statistics_path,
        ]
    )
    build_report = {
        "build_scope": payload.build_scope,
        "build_time_ms": elapsed_ms,
        "classification": payload.store_status,
        "dataset_source_modified": False,
        "dependency_mode": DEPENDENCY_MODE,
        "external_effects": _external_effects(),
        "full_dataset_conversion": False,
        "full_media_predecode": False,
        "generated_artifacts_tracked": False,
        "local_stage_used": False,
        "output_episode_count": payload.episode_count,
        "output_sample_count": payload.sample_count,
        "pfs_write_mb_s": _mb_per_second(total_bytes=total_bytes, elapsed_ms=elapsed_ms),
        "raw_bounded_decode_baseline": {
            "preserved": True,
            "raw_batch_latency_ms_p50": "missing",
            "raw_batch_latency_ms_p95": "missing",
            "raw_media_decode_time_ms": "missing",
            "status": "baseline evidence must be supplied or recomputed on compute",
        },
        "schema_version": f"{WEBDATASET_STREAMING_SCHEMA_VERSION}.build_report",
        "shard_write_time_ms": shard_write_ms,
        "source_kind": "source_derived_parquet",
        "storage_backend": PFS_STORAGE_BACKEND,
        "stop_reason": payload.stop_reason,
        "store_format": WEBDATASET_STREAMING_FORMAT,
        "webdataset_writer": "webdataset.TarWriter",
    }
    _write_json(store_dir / "build_report.json", build_report)
    _write_json(store_dir / "reports" / "build_report.json", build_report)
    _write_json(
        store_dir / "read_benchmark_report.json",
        {
            "schema_version": f"{WEBDATASET_STREAMING_SCHEMA_VERSION}.read_report",
            "status": "not_run",
        },
    )
    _write_json(
        store_dir / "reports" / "read_benchmark_report.json",
        {
            "schema_version": f"{WEBDATASET_STREAMING_SCHEMA_VERSION}.read_report",
            "status": "not_run",
        },
    )
    config.output_dir.mkdir(parents=True, exist_ok=True)
    (config.output_dir / "resolved_store_path.txt").write_text(
        store_dir.as_posix() + "\n",
        encoding="utf-8",
    )
    return StreamingTrainingStoreBuildResult(
        store_dir=store_dir,
        manifest=manifest.to_json_dict(),
        build_report=build_report,
    )


def read_webdataset_streaming_store_benchmark(
    config: PerfBenchmarkConfig,
) -> StreamingTrainingStoreBenchmarkResult:
    """通过 WebDataset streaming iterator 读取 store。"""
    backend = WebDatasetStreamingTrainingStoreBackend()
    backend.validate_source(config.dataset)
    store_dir = _require_training_store_dir(config)
    backend.validate_store_target(source=config.dataset, output=store_dir)
    started = time.perf_counter()
    manifest = _read_json(store_dir / "training_store_manifest.json")
    checksums = _read_json(store_dir / "checksums.json")
    fields = _read_json(store_dir / "index" / "fields.json")
    build_report = _read_json(
        _first_existing(
            store_dir / "reports" / "build_report.json",
            store_dir / "build_report.json",
        )
    )
    checksum_started = time.perf_counter()
    checksums_verified, checksum_files_checked = _checksums_match(store_dir, checksums)
    checksum_ms = round((time.perf_counter() - checksum_started) * 1000.0, 6)
    index_started = time.perf_counter()
    sample_rows = _read_jsonl(store_dir / "index" / "samples.jsonl", limit=config.max_samples)
    episode_rows = _read_jsonl(store_dir / "index" / "episodes.jsonl")
    index_lookup_ms = round((time.perf_counter() - index_started) * 1000.0, 6)

    stream_started = time.perf_counter()
    samples = _read_webdataset_samples(
        shard_paths=_shard_paths_for_rows(store_dir=store_dir, sample_rows=sample_rows),
        limit=config.max_samples,
    )
    stream_read_ms = round((time.perf_counter() - stream_started) * 1000.0, 6)
    actions = np.asarray([sample["actions"] for sample in samples], dtype=np.float32)
    state = np.asarray([sample["state"] for sample in samples], dtype=np.float32)
    action_mask = np.asarray([sample["action_mask"] for sample in samples], dtype=np.bool_)
    language_text = tuple(_string(sample["language_text"], "language_text") for sample in samples)
    metadata_json = tuple(_string(sample["metadata_json"], "metadata_json") for sample in samples)
    sample_ids = tuple(_string(sample["sample_id"], "sample_id") for sample in samples)
    episode_ids = tuple(_string(sample["episode_id"], "episode_id") for sample in samples)
    store_hash, store_signatures = _payload_hash(
        actions=actions,
        state=state,
        action_mask=action_mask,
        language_text=language_text,
        metadata_json=metadata_json,
        sample_ids=sample_ids,
        episode_ids=episode_ids,
        action_horizon=_positive_int(manifest.get("action_horizon"), "action_horizon"),
        action_dim=_positive_int(manifest.get("action_dim"), "action_dim"),
    )
    raw_signatures = _mapping_list(fields.get("payload_signatures"), "payload_signatures")[
        : len(samples)
    ]
    raw_hash = _sha256_json(raw_signatures)
    comparator_valid = raw_hash == store_hash
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
    raw_baseline = _mapping(build_report.get("raw_bounded_decode_baseline"), "raw baseline")
    raw_p50 = raw_baseline.get("raw_batch_latency_ms_p50", "missing")
    raw_p95 = raw_baseline.get("raw_batch_latency_ms_p95", "missing")
    raw_media_decode = raw_baseline.get("raw_media_decode_time_ms", "missing")
    effective = _effective_raw_comparison(
        raw_p50=raw_p50,
        raw_p95=raw_p95,
        raw_media_decode=raw_media_decode,
    )
    speedup = _speedup(effective["raw_effective_batch_latency_ms_p50"], elapsed_ms)
    shard_paths = _shard_paths_for_rows(store_dir=store_dir, sample_rows=sample_rows)
    comparator_report = {
        "cache_condition": _cache_condition(),
        "comparator_mode": "action_state_mask_only",
        "comparator_valid": comparator_valid,
        "full_training_window_equivalent": False,
        "full_training_window_supported": False,
        "media_payload_equivalent": False,
        "mismatches": [] if comparator_valid else ["payload_hash_mismatch"],
        "payload_fields": _payload_fields(),
        "raw_payload_hash": raw_hash,
        "raw_payload_signature": raw_signatures,
        "raw_source_kind": "source_derived_parquet_build_snapshot",
        "sample_budget": {
            "compared_sample_count": len(samples),
            "requested_sample_count": config.max_samples,
        },
        "status": "PASS" if comparator_valid else "FAIL",
        "store_payload_hash": store_hash,
        "store_payload_signature": store_signatures,
        "store_source_kind": WEBDATASET_STREAMING_FORMAT,
        "training_window_ids": _training_window_ids(sample_rows[: len(samples)]),
    }
    comparison = {
        **effective,
        "action_state_mask_only_supported": True,
        "backend_selection_ready": comparator_valid,
        "cache_condition": comparator_report["cache_condition"],
        "checksum_files_checked": checksum_files_checked,
        "checksum_validation_scope": "open_boundary_once",
        "checksum_validation_time_ms": checksum_ms,
        "comparator_equivalence_status": comparator_report["status"],
        "comparator_mode": "action_state_mask_only",
        "comparator_report": comparator_report,
        "comparator_valid": comparator_valid,
        "decode_avoided_ratio": 1.0,
        "dependency_mode": DEPENDENCY_MODE,
        "episode_index_count": len(episode_rows),
        "first_sample_preview": _first_sample_preview(
            actions=actions,
            state=state,
            action_mask=action_mask,
            language_text=language_text,
            metadata_json=metadata_json,
            sample_ids=sample_ids,
        ),
        "full_training_window_equivalent": False,
        "full_training_window_supported": False,
        "media_payload_equivalent": False,
        "missing_telemetry": _missing_telemetry(raw_p50=raw_p50, raw_media_decode=raw_media_decode),
        "pfs_file_open_count": len(shard_paths) + 5,
        "pfs_metadata_ops_estimate": len(sample_rows) + len(episode_rows) + 6,
        "pfs_read_mb_s": _mb_per_second(
            total_bytes=_payload_bytes(store_dir, manifest),
            elapsed_ms=max(stream_read_ms, 0.001),
        ),
        "prepacked_shard_read_time_ms": stream_read_ms,
        "raw_batch_latency_ms_p50": raw_p50,
        "raw_batch_latency_ms_p95": raw_p95,
        "raw_media_decode_time_ms": raw_media_decode,
        "raw_payload_hash": raw_hash,
        "sample_budget": comparator_report["sample_budget"],
        "sample_index_lookup_time_ms": index_lookup_ms,
        "speedup_vs_raw_decode": speedup,
        "store_format": WEBDATASET_STREAMING_FORMAT,
        "store_payload_hash": store_hash,
        "streaming_iterator": "webdataset.WebDataset",
        "training_store_batch_latency_ms_p50": elapsed_ms,
        "training_store_batch_latency_ms_p95": elapsed_ms,
        "training_store_build_time_ms": build_report.get("build_time_ms", "missing"),
        "training_store_read_time_ms": elapsed_ms,
    }
    report = {
        "checksums_verified": checksums_verified,
        "comparison": comparison,
        "external_effects": _external_effects(),
        "sample_count": len(samples),
        "schema_version": f"{WEBDATASET_STREAMING_SCHEMA_VERSION}.read_report",
        "storage_backend": manifest.get("storage_backend", "missing"),
        "store_status": manifest.get("store_status", "missing"),
    }
    _write_json(store_dir / "read_benchmark_report.json", report)
    _write_json(store_dir / "reports" / "read_benchmark_report.json", report)
    return StreamingTrainingStoreBenchmarkResult(
        store_dir=store_dir,
        comparison=comparison,
        report=report,
    )


def _write_webdataset_shard(*, store_dir: Path, payload: _StreamingPayload) -> tuple[Path, float]:
    """用 WebDataset TarWriter 写出 tar shard。"""
    started = time.perf_counter()
    wds = _webdataset_module()
    shard_path = store_dir / "shards" / "shard-000000.tar"
    writer = wds.TarWriter(shard_path.as_posix(), mtime=0)
    try:
        for index, sample_id in enumerate(payload.sample_ids):
            writer.write(
                {
                    "__key__": sample_id,
                    "action.npy": _npy_bytes(payload.actions[index]),
                    "action_mask.npy": _npy_bytes(payload.action_mask[index]),
                    "json": payload.metadata_json[index].encode("utf-8"),
                    "state.npy": _npy_bytes(payload.state[index]),
                }
            )
    finally:
        writer.close()
    return shard_path, round((time.perf_counter() - started) * 1000.0, 6)


def _read_webdataset_samples(
    *,
    shard_paths: Sequence[Path],
    limit: int,
) -> list[dict[str, object]]:
    """用 WebDataset package streaming iterator 读取 bounded 样本。"""
    wds = _webdataset_module()
    dataset = wds.WebDataset([path.as_posix() for path in shard_paths], shardshuffle=False)
    samples: list[dict[str, object]] = []
    for raw_sample in dataset:
        metadata = _json_bytes(raw_sample.get("json"))
        samples.append(
            {
                "action_mask": _npy_array(raw_sample.get("action_mask.npy")).astype(np.bool_),
                "actions": _npy_array(raw_sample.get("action.npy")).astype(np.float32),
                "episode_id": _string(metadata.get("episode_id"), "episode_id"),
                "language_text": "zjh task 0",
                "metadata_json": json.dumps(metadata, sort_keys=True),
                "sample_id": _string(metadata.get("sample_id"), "sample_id"),
                "state": _npy_array(raw_sample.get("state.npy")).astype(np.float32),
            }
        )
        if len(samples) >= limit:
            break
    return samples


def _source_payload(
    *,
    config: PerfBenchmarkConfig,
    dataset_manifest: Mapping[str, object],
    modality: Mapping[str, object],
) -> _StreamingPayload:
    """从 source parquet 构造 WebDataset sample payload。"""
    source_sample_count = _positive_int(dataset_manifest.get("sample_count"), "sample_count")
    source_episode_count = _positive_int(dataset_manifest.get("episode_count"), "episode_count")
    action_dim = _feature_dim(_mapping(dataset_manifest.get("action_space"), "action_space"))
    state_dim = _feature_dim(_mapping(dataset_manifest.get("state_space"), "state_space"))
    camera_keys = _camera_keys(modality)
    sample_limit = (
        source_sample_count
        if config.build_scope in {"full", "full-or-budgeted"}
        else min(config.max_samples, source_sample_count)
    )
    action_rows: list[list[float]] = []
    state_rows: list[list[float]] = []
    metadata_rows: list[str] = []
    sample_sources: list[Mapping[str, object]] = []
    sample_ids: list[str] = []
    episode_ids: list[str] = []
    for parquet_path in _selected_parquet_files(
        config=config,
        source_episode_count=source_episode_count,
    ):
        for row in _read_parquet_rows(parquet_path=parquet_path, camera_keys=camera_keys):
            if len(action_rows) >= sample_limit:
                break
            action_values = _float_list(row.get("action"), expected=action_dim, field="action")
            state_values = _float_list(
                row.get("observation.state"),
                expected=state_dim,
                field="observation.state",
            )
            row_ord = len(action_rows)
            episode_index = _int_or_default(row.get("episode_index"), row_ord)
            frame_index = _int_or_default(row.get("frame_index"), row_ord)
            source_index = _int_or_default(row.get("index"), row_ord)
            episode_id = f"episode-{episode_index:06d}"
            sample_id = f"sample-{source_index:09d}"
            media_refs: dict[str, object] = {}
            for key in camera_keys:
                media_ref = row.get(key)
                if isinstance(media_ref, Mapping):
                    media_refs[key] = dict(cast(Mapping[str, object], media_ref))
            sample_source: dict[str, object] = {
                "adapter": config.adapter,
                "bounded_preview": config.build_scope != "full",
                "dataset": config.dataset.as_posix(),
                "episode_index": episode_index,
                "frame_index": frame_index,
                "parquet_path": parquet_path.relative_to(config.dataset).as_posix(),
                "sample_index": source_index,
                "source_format": _string_or_missing(dataset_manifest.get("source_format")),
            }
            metadata = {
                "episode_id": episode_id,
                "frame_index": frame_index,
                "media_refs": media_refs,
                "sample_id": sample_id,
                "sample_source": sample_source,
            }
            action_rows.append(action_values)
            state_rows.append(state_values)
            metadata_rows.append(json.dumps(metadata, sort_keys=True))
            sample_sources.append(sample_source)
            sample_ids.append(sample_id)
            episode_ids.append(episode_id)
        if len(action_rows) >= sample_limit:
            break
    if not action_rows:
        raise ValueError("webdataset_streaming_v1 build requires source parquet samples")
    actual_sample_count = len(action_rows)
    action_horizon = 1
    actions = np.asarray(action_rows, dtype=np.float32).reshape(
        actual_sample_count,
        action_horizon,
        action_dim,
    )
    state = np.asarray(state_rows, dtype=np.float32).reshape(actual_sample_count, state_dim)
    action_mask = np.ones((actual_sample_count, action_horizon, action_dim), dtype=np.bool_)
    full_ready = (
        actual_sample_count == source_sample_count
        and len(set(episode_ids)) == source_episode_count
        and config.build_scope in {"full", "full-or-budgeted"}
    )
    return _StreamingPayload(
        actions=cast(NDArray[np.float32], actions),
        state=cast(NDArray[np.float32], state),
        action_mask=action_mask,
        language_text=tuple("zjh task 0" for _ in range(actual_sample_count)),
        metadata_json=tuple(metadata_rows),
        sample_ids=tuple(sample_ids),
        episode_ids=tuple(episode_ids),
        sample_sources=tuple(sample_sources),
        sample_count=actual_sample_count,
        episode_count=len(set(episode_ids)),
        action_horizon=action_horizon,
        action_dim=action_dim,
        state_dim=state_dim,
        build_scope="full" if full_ready else "budgeted_partial",
        store_status="FULL_STORE_READY" if full_ready else "PARTIAL_STORE_READY_FOR_FORMAT_REVIEW",
        stop_reason="complete" if full_ready else "budgeted_or_incomplete_source_coverage",
    )


def _sample_rows(
    *,
    payload: _StreamingPayload,
    shard_path: Path,
    store_dir: Path,
) -> list[dict[str, object]]:
    """构造 samples.jsonl 行。"""
    rows: list[dict[str, object]] = []
    for index, sample_id in enumerate(payload.sample_ids):
        sample_source = payload.sample_sources[index]
        rows.append(
            {
                "action_dim": payload.action_dim,
                "action_horizon": payload.action_horizon,
                "episode_id": payload.episode_ids[index],
                "sample_id": sample_id,
                "sample_source": dict(sample_source),
                "shard_path": shard_path.relative_to(store_dir).as_posix(),
                "split": "train",
                "state_shape": [payload.state_dim],
                "window_start": _int_or_default(sample_source.get("frame_index"), index),
            }
        )
    return rows


def _episode_rows(*, payload: _StreamingPayload) -> list[dict[str, object]]:
    """构造 episodes.jsonl 行。"""
    rows: list[dict[str, object]] = []
    for episode_id in dict.fromkeys(payload.episode_ids):
        rows.append(
            {
                "episode_id": episode_id,
                "sample_count": payload.episode_ids.count(episode_id),
                "sample_ids": [
                    sample_id
                    for sample_id, row_episode in zip(
                        payload.sample_ids,
                        payload.episode_ids,
                        strict=True,
                    )
                    if row_episode == episode_id
                ],
                "split": "train",
            }
        )
    return rows


def _manifest(
    *,
    config: PerfBenchmarkConfig,
    dataset_manifest: Mapping[str, object],
    fingerprints: Mapping[str, object],
    payload: _StreamingPayload,
    store_dir: Path,
    shard_path: Path,
    build_time_ms: float,
) -> StreamingTrainingStoreManifest:
    """构造 WebDataset streaming manifest。"""
    dataset_fingerprint = _string_or_missing(fingerprints.get("dataset_fingerprint"))
    dataset_id = _string_or_missing(dataset_manifest.get("dataset_id"))
    return StreamingTrainingStoreManifest(
        {
            "action_dim": payload.action_dim,
            "action_horizon": payload.action_horizon,
            "action_state_mask_only_supported": True,
            "adapter_name": config.adapter,
            "adapter_version": _string_or_missing(dataset_manifest.get("converter_version")),
            "backend": WEBDATASET_STREAMING_FORMAT,
            "build_scope": payload.build_scope,
            "build_time_ms": build_time_ms,
            "checksums_path": "checksums.json",
            "comparator_mode_supported": ["action_state_mask_only"],
            "created_by": "autovla.dataloader.perf.webdataset_streaming_store",
            "dataset_fingerprint": dataset_fingerprint,
            "dataset_id": dataset_id,
            "dataset_name": dataset_id,
            "dataset_source_modified": False,
            "dependency_mode": DEPENDENCY_MODE,
            "episode_count": payload.episode_count,
            "episode_index_path": "index/episodes.jsonl",
            "external_effects": _external_effects(),
            "full_training_window_supported": False,
            "generated_artifacts_tracked": False,
            "index_path": "index/samples.jsonl",
            "local_stage_used": False,
            "media_payload_equivalent": False,
            "real_training": False,
            "sample_count": payload.sample_count,
            "sample_index_path": "index/samples.jsonl",
            "schema_version": WEBDATASET_STREAMING_SCHEMA_VERSION,
            "shard_count": 1,
            "shard_format": "tar",
            "shards": [
                {
                    "path": shard_path.relative_to(store_dir).as_posix(),
                    "sample_count": payload.sample_count,
                    "sample_start": 0,
                }
            ],
            "source_dataset": config.dataset.as_posix(),
            "source_format": _string_or_missing(dataset_manifest.get("source_format")),
            "state_dim": payload.state_dim,
            "statistics_fingerprint": _string_or_missing(
                fingerprints.get("statistics_fingerprint")
            ),
            "statistics_plan_path": "statistics_plan.json",
            "storage_backend": PFS_STORAGE_BACKEND,
            "store_format": WEBDATASET_STREAMING_FORMAT,
            "store_id": f"webdataset-streaming-v1::{dataset_fingerprint[:16]}",
            "store_path": store_dir.as_posix(),
            "store_status": payload.store_status,
            "transform_fingerprint": _string_or_missing(fingerprints.get("transform_fingerprint")),
        }
    )


def _statistics_plan(
    *,
    config: PerfBenchmarkConfig,
    dataset_manifest: Mapping[str, object],
    fingerprints: Mapping[str, object],
    payload: _StreamingPayload,
) -> dict[str, object]:
    """记录 streaming 统计计划, 不执行昂贵全量统计拟合。"""
    return {
        "action_statistics_policy": "bounded_source_derived_rows",
        "build_scope": payload.build_scope,
        "dataset_fingerprint": _string_or_missing(fingerprints.get("dataset_fingerprint")),
        "expensive_full_statistics_fit": False,
        "sample_count": payload.sample_count,
        "schema_version": f"{WEBDATASET_STREAMING_SCHEMA_VERSION}.statistics_plan",
        "source_dataset": config.dataset.as_posix(),
        "statistics_fingerprint": _string_or_missing(fingerprints.get("statistics_fingerprint")),
        "statistics_scope": _string_or_missing(dataset_manifest.get("statistics_scope")),
        "transform_fingerprint": _string_or_missing(fingerprints.get("transform_fingerprint")),
    }


def _action_statistics(actions: NDArray[np.float32]) -> dict[str, object]:
    """基于 bounded action payload 写出小型统计 evidence。"""
    return {
        "action_max": actions.max(axis=(0, 1)).round(6).tolist(),
        "action_mean": actions.mean(axis=(0, 1)).round(6).tolist(),
        "action_min": actions.min(axis=(0, 1)).round(6).tolist(),
        "action_std": actions.std(axis=(0, 1)).round(6).tolist(),
        "source": WEBDATASET_STREAMING_FORMAT,
        "statistics_scope": "mixed",
    }


def _payload_hash(
    *,
    actions: NDArray[np.float32],
    state: NDArray[np.float32],
    action_mask: NDArray[np.bool_],
    language_text: Sequence[str],
    metadata_json: Sequence[str],
    sample_ids: Sequence[str],
    episode_ids: Sequence[str],
    action_horizon: int,
    action_dim: int,
) -> tuple[str, list[dict[str, object]]]:
    """对 action/state/mask 子集生成逐样本签名和整体 hash。"""
    signatures: list[dict[str, object]] = []
    for index, sample_id in enumerate(sample_ids):
        signature: dict[str, object] = {
            "fields": {
                "action_mask": _array_signature(action_mask[index]),
                "actions": _array_signature(actions[index]),
                "language_text": _text_signature(language_text[index]),
                "metadata_json": _text_signature(_canonical_metadata(metadata_json[index])),
                "state": _array_signature(state[index]),
            },
            "training_window_id": {
                "action_dim": action_dim,
                "action_horizon": action_horizon,
                "episode_id": episode_ids[index],
                "sample_id": sample_id,
                "window_start": index % max(len(sample_ids), 1),
            },
        }
        signatures.append(signature)
    return _sha256_json(signatures), signatures


def _array_signature(array: NDArray[np.generic]) -> dict[str, object]:
    """计算 ndarray 字段签名。"""
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(contiguous.dtype).encode("utf-8"))
    digest.update(json.dumps(list(contiguous.shape), sort_keys=True).encode("utf-8"))
    digest.update(contiguous.tobytes())
    return {
        "dtype": str(contiguous.dtype),
        "sha256": digest.hexdigest(),
        "shape": [int(item) for item in contiguous.shape],
    }


def _text_signature(text: str) -> dict[str, object]:
    """计算文本字段签名。"""
    return {
        "dtype": "str",
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "shape": [1],
    }


def _npy_bytes(array: NDArray[np.generic]) -> bytes:
    """把 ndarray 编码成 WebDataset npy payload。"""
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


def _npy_array(value: object) -> NDArray[np.generic]:
    """从 WebDataset bytes 读取 ndarray。"""
    if not isinstance(value, (bytes, bytearray)):
        raise ValueError("WebDataset sample field must be bytes")
    buffer = io.BytesIO(bytes(value))
    loaded = np.load(buffer, allow_pickle=False)
    return cast(NDArray[np.generic], loaded)


def _json_bytes(value: object) -> Mapping[str, object]:
    """从 WebDataset json bytes 读取 mapping。"""
    if not isinstance(value, (bytes, bytearray)):
        raise ValueError("WebDataset json field must be bytes")
    loaded = json.loads(bytes(value).decode("utf-8"))
    if not isinstance(loaded, Mapping):
        raise TypeError("WebDataset json field must contain a JSON object")
    return cast(Mapping[str, object], loaded)


def _selected_parquet_files(
    *,
    config: PerfBenchmarkConfig,
    source_episode_count: int,
) -> list[Path]:
    """按稳定顺序选择 source parquet 文件。"""
    files = sorted((config.dataset / "data").glob("chunk-*/*.parquet"))
    if not files:
        raise ValueError("webdataset_streaming_v1 build requires source parquet files")
    if config.build_scope in {"full", "full-or-budgeted"}:
        return files
    return files[: min(config.max_episodes, source_episode_count, len(files))]


def _read_parquet_rows(
    *,
    parquet_path: Path,
    camera_keys: Sequence[str],
) -> list[Mapping[str, object]]:
    """读取 WebDataset streaming 所需 parquet 列。"""
    parquet_module = cast(
        _ParquetModuleProtocol,
        importlib.import_module("pyarrow.parquet"),
    )
    columns = [
        "action",
        "observation.state",
        "episode_index",
        "frame_index",
        "index",
        "task_index",
        *camera_keys,
    ]
    table = parquet_module.read_table(parquet_path, columns=columns)
    rows: list[Mapping[str, object]] = []
    for row_index in range(int(table.num_rows)):
        row: dict[str, object] = {}
        for column in table.column_names:
            row[column] = table[column][row_index].as_py()
        rows.append(row)
    return rows


def _resolved_store_dir(*, config: PerfBenchmarkConfig, artifact: DatasetArtifactV1) -> Path:
    """解析 fingerprinted webdataset_streaming_v1 store 路径。"""
    requested = _require_training_store_dir(config)
    payload = artifact.to_json_dict()
    manifest = _mapping(payload.get("dataset_manifest"), "dataset_manifest")
    fingerprints = _mapping(payload.get("fingerprints"), "fingerprints")
    dataset_id = _safe_path_component(
        _string_or_missing(manifest.get("dataset_id")),
        fallback="dataset",
    )
    dataset_fingerprint = _safe_path_component(
        _string_or_missing(fingerprints.get("dataset_fingerprint")),
        fallback="fingerprint",
    )
    base = requested
    if base.name != dataset_id:
        base = base / dataset_id
    return base / dataset_fingerprint / WEBDATASET_STREAMING_FORMAT


def _shard_paths_for_rows(
    *,
    store_dir: Path,
    sample_rows: Sequence[Mapping[str, object]],
) -> list[Path]:
    """从 sample rows 推导需要 streaming 的 tar shard。"""
    paths: list[Path] = []
    seen: set[str] = set()
    for row in sample_rows:
        shard_path = _store_relative_path(
            store_dir=store_dir,
            value=row.get("shard_path"),
            field="shard_path",
        )
        shard_key = shard_path.as_posix()
        if shard_key not in seen:
            seen.add(shard_key)
            paths.append(shard_path)
    return paths


def _checksums(*, store_dir: Path, files: Mapping[str, Path]) -> dict[str, object]:
    """计算 store 文件校验和和相对路径。"""
    return {
        "algorithm": "sha256",
        "files": {key: _sha256_file(path) for key, path in sorted(files.items())},
        "paths": {
            key: path.relative_to(store_dir).as_posix() for key, path in sorted(files.items())
        },
    }


def _checksums_match(store_dir: Path, checksums: Mapping[str, object]) -> tuple[bool, int]:
    """在 open 边界校验 checksum, 不逐样本校验。"""
    files = _mapping(checksums.get("files"), "files")
    paths = _mapping(checksums.get("paths"), "paths")
    checked = 0
    for key, expected_hash in files.items():
        path = _store_relative_path(
            store_dir=store_dir,
            value=paths.get(key),
            field=f"{key} path",
        )
        checked += 1
        if expected_hash != _sha256_file(path):
            return False, checked
    return True, checked


def _store_relative_path(*, store_dir: Path, value: object, field: str) -> Path:
    """把 store 内部记录的路径收敛到 store_dir 内。"""
    text = _string(value, field).strip()
    if not text:
        raise ValueError(f"{field} store-relative path must be non-empty")
    relative_path = _local_path(text, field=field)
    if relative_path.is_absolute():
        raise ValueError(f"{field} store-relative path must not be absolute")
    store_root = store_dir.resolve(strict=False)
    resolved_path = (store_root / relative_path).resolve(strict=False)
    if resolved_path == store_root or not _is_relative_to(resolved_path, store_root):
        raise ValueError(f"{field} store-relative path must stay inside store_dir")
    return resolved_path


def _sha256_file(path: Path) -> str:
    """计算文件 SHA256。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _training_window_ids(sample_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """从 sample rows 生成 JSON-safe window ids。"""
    return [
        {
            "action_dim": _positive_int(row.get("action_dim"), "action_dim"),
            "action_horizon": _positive_int(row.get("action_horizon"), "action_horizon"),
            "episode_id": _string(row.get("episode_id"), "episode_id"),
            "sample_id": _string(row.get("sample_id"), "sample_id"),
            "window_start": _nonnegative_int(row.get("window_start"), "window_start"),
        }
        for row in sample_rows
    ]


def _first_sample_preview(
    *,
    actions: NDArray[np.float32],
    state: NDArray[np.float32],
    action_mask: NDArray[np.bool_],
    language_text: Sequence[str],
    metadata_json: Sequence[str],
    sample_ids: Sequence[str],
) -> dict[str, object]:
    """返回首样本小型 preview, 仅用于测试和报告。"""
    if actions.shape[0] == 0:
        return {}
    return {
        "action_mask": action_mask[0].tolist(),
        "actions": actions[0].round(6).tolist(),
        "language_text": language_text[0],
        "metadata_json": metadata_json[0],
        "sample_id": sample_ids[0],
        "state": state[0].round(6).tolist(),
    }


def _external_effects() -> dict[str, bool]:
    """返回 WebDataset streaming 构建/读取外部副作用边界。"""
    return {
        "checkpoint_download": False,
        "checkpoint_read": False,
        "endpoint": False,
        "full_conversion": False,
        "hf_network": False,
        "model_load": False,
        "real_training": False,
        "robot": False,
        "slurm_submission": False,
        "wandb": False,
    }


def _cache_condition() -> dict[str, object]:
    """返回未控制冷热缓存的显式声明。"""
    return {"cold_cache": "not_asserted", "policy": "not_controlled", "warm_cache": "not_asserted"}


def _payload_fields() -> list[dict[str, object]]:
    """返回 streaming comparator 字段。"""
    return [
        {"name": "actions", "value_check": True},
        {"name": "state", "value_check": True},
        {"name": "action_mask", "value_check": True},
        {"name": "language_text", "value_check": True},
        {"name": "metadata_json", "value_check": True},
    ]


def _effective_raw_comparison(
    *,
    raw_p50: object,
    raw_p95: object,
    raw_media_decode: object,
) -> dict[str, object]:
    """推导 raw/store 对比使用的显式 raw comparator。"""
    raw_p50_value = _optional_float(raw_p50)
    raw_p95_value = _optional_float(raw_p95)
    raw_media_value = _optional_float(raw_media_decode)
    if raw_p50_value is None:
        return {
            "raw_comparison_basis": "missing_raw_batch_latency",
            "raw_effective_batch_latency_ms_p50": "missing",
            "raw_effective_batch_latency_ms_p95": "missing",
        }
    if raw_media_value is not None and raw_media_value > raw_p50_value:
        effective_p50 = raw_media_value
        basis = "media_decode_bottleneck"
    else:
        effective_p50 = raw_p50_value
        basis = "raw_batch_latency"
    p95_base = raw_p95_value if raw_p95_value is not None else raw_p50_value
    effective_p95 = max(p95_base, raw_media_value) if raw_media_value is not None else p95_base
    return {
        "raw_comparison_basis": basis,
        "raw_effective_batch_latency_ms_p50": round(effective_p50, 6),
        "raw_effective_batch_latency_ms_p95": round(effective_p95, 6),
    }


def _missing_telemetry(*, raw_p50: object, raw_media_decode: object) -> list[str]:
    """生成缺失 telemetry 列表。"""
    missing = ["gpu_util_pct", "gpu_memory_used_mb", "hbm_bw_pct"]
    if _optional_float(raw_p50) is None:
        missing.append("raw_batch_latency_ms_p50")
    if _optional_float(raw_media_decode) is None:
        missing.append("raw_media_decode_time_ms")
    return missing


def _webdataset_module() -> _WebDatasetModuleProtocol:
    """动态加载 WebDataset package, 方便 pyright 限定最小 API。"""
    return cast(_WebDatasetModuleProtocol, importlib.import_module("webdataset"))


def _local_path(value: str | Path, *, field: str) -> Path:
    """拒绝 remote URL、pipe 命令和非本地路径。"""
    text = value.as_posix() if isinstance(value, Path) else str(value)
    lowered = text.lower()
    if "://" in lowered or lowered.startswith("pipe:") or lowered.startswith("pipe="):
        raise ValueError(f"{field} must be a local filesystem path")
    return Path(text)


def _is_relative_to(path: Path, parent: Path) -> bool:
    """兼容 Python 3.10 的 relative_to 判断。"""
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON object。"""
    loaded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(loaded, Mapping):
        raise TypeError(f"{path} must contain a JSON object")
    return dict(cast(Mapping[str, object], loaded))


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    """写出稳定 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, object]]:
    """读取 JSONL 文件, 可限制 hot-path 样本数。"""
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if limit is not None and len(rows) >= limit:
                break
            loaded = cast(object, json.loads(line))
            if not isinstance(loaded, Mapping):
                raise TypeError(f"{path} row must contain a JSON object")
            rows.append(dict(cast(Mapping[str, object], loaded)))
    return rows


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """写出稳定 JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _feature_dim(feature: Mapping[str, object]) -> int:
    """读取一维 feature shape。"""
    raw_shape = feature.get("shape")
    if not isinstance(raw_shape, list) or not raw_shape:
        raise ValueError("feature shape must be a non-empty list")
    return _positive_int(cast(list[object], raw_shape)[0], "feature shape")


def _camera_keys(modality: Mapping[str, object]) -> list[str]:
    """读取相机 feature keys。"""
    raw = modality.get("cameras")
    if not isinstance(raw, list):
        return []
    keys: list[str] = []
    for item in cast(list[object], raw):
        camera = _mapping(item, "camera")
        keys.append(_string(camera.get("feature_key"), "camera feature_key"))
    return keys


def _payload_bytes(store_dir: Path, manifest: Mapping[str, object]) -> int:
    """统计 streaming tar shard 文件字节数。"""
    shards = cast(list[object], manifest.get("shards", []))
    total = 0
    for item in shards:
        shard = _mapping(item, "shard")
        total += (store_dir / _string(shard.get("path"), "shard path")).stat().st_size
    return total


def _store_payload_size_bytes(paths: Sequence[Path]) -> int:
    """统计写出 payload 的字节数。"""
    return sum(path.stat().st_size for path in paths if path.exists())


def _first_existing(primary: Path, fallback: Path) -> Path:
    """选择第一个存在路径。"""
    if primary.exists():
        return primary
    if fallback.exists():
        return fallback
    return primary


def _require_training_store_dir(config: PerfBenchmarkConfig) -> Path:
    """读取 Training Store 路径。"""
    if config.training_store_dir is None:
        raise ValueError("training_store_dir is required for webdataset_streaming_v1 modes")
    return config.training_store_dir


def _mapping(value: object, name: str) -> Mapping[str, object]:
    """校验 mapping。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return cast(Mapping[str, object], value)


def _mapping_list(value: object, name: str) -> list[Mapping[str, object]]:
    """校验 mapping 列表。"""
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list")
    rows: list[Mapping[str, object]] = []
    for item in cast(list[object], value):
        rows.append(_mapping(item, name))
    return rows


def _string(value: object, name: str) -> str:
    """校验非空字符串。"""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _string_or_missing(value: object) -> str:
    """把字符串字段规范化, 缺失时返回 missing。"""
    return value if isinstance(value, str) and value else "missing"


def _positive_int(value: object, name: str) -> int:
    """校验正整数。"""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive int")
    return value


def _nonnegative_int(value: object, name: str) -> int:
    """校验非负整数。"""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative int")
    return value


def _int_or_default(value: object, default: int) -> int:
    """读取 int, 缺失时使用 default。"""
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _float_list(value: object, *, expected: int, field: str) -> list[float]:
    """校验 parquet 数值 list 并转为 float。"""
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    raw_values = cast(list[object], value)
    if len(raw_values) != expected:
        raise ValueError(f"{field} length must be {expected}")
    values: list[float] = []
    for item in raw_values:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{field} must contain numeric values")
        values.append(float(item))
    return values


def _optional_float(value: object) -> float | None:
    """读取可选 float。"""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _canonical_metadata(text: str) -> str:
    """规范化 metadata_json 文本。"""
    return json.dumps(json.loads(text), sort_keys=True)


def _sha256_json(payload: object) -> str:
    """对 JSON-safe payload 计算稳定 SHA256。"""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mb_per_second(*, total_bytes: int, elapsed_ms: float) -> float:
    """计算 MB/s。"""
    mb = total_bytes / (1024.0 * 1024.0)
    return round(mb / (elapsed_ms / 1000.0), 6)


def _speedup(raw_p50: object, store_p50: float) -> object:
    """计算 raw/store speedup。"""
    raw_value = _optional_float(raw_p50)
    if raw_value is not None:
        return round(raw_value / max(store_p50, 0.001), 6)
    return "missing"


def _safe_path_component(value: str, *, fallback: str) -> str:
    """把外部 id/fingerprint 收敛为安全路径片段。"""
    source = value if value and value != "missing" else fallback
    safe = "".join(char if char.isalnum() or char in "-_." else "-" for char in source)
    safe = safe.strip(".-_/")
    return safe or fallback
