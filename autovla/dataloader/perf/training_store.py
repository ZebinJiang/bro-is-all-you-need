"""PFS-backed AutoVLA Training Store v0 契约和有界构建器。"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
from numpy.typing import NDArray

from autovla.dataloader.dataset_artifact import DatasetArtifactV1
from autovla.dataloader.perf.config import PerfBenchmarkConfig

TRAINING_STORE_SCHEMA_VERSION = "autovla.training_store.v0"
TRAINING_STORE_FORMAT = "npz_jsonl_v0"
PFS_STORAGE_BACKEND = "pfs_shared"


@dataclass(frozen=True, slots=True)
class TrainingStoreBuildResult:
    """记录一次 bounded Training Store 构建结果。"""

    store_dir: Path
    manifest: Mapping[str, object]
    build_report: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class TrainingStoreReadResult:
    """记录一次 Training Store 读取 benchmark 结果。"""

    store_dir: Path
    comparison: Mapping[str, object]
    report: Mapping[str, object]


def require_training_store_dir(config: PerfBenchmarkConfig) -> Path:
    """读取并校验 Training Store 输出目录。"""
    if config.training_store_dir is None:
        raise ValueError("training_store_dir is required for store modes")
    return config.training_store_dir


def write_training_store_plan(
    *,
    config: PerfBenchmarkConfig,
    artifact: DatasetArtifactV1,
) -> dict[str, object]:
    """写出 store-plan 小型计划, 不创建 shard。"""
    store_dir = require_training_store_dir(config)
    payload = artifact.to_json_dict()
    manifest = _mapping(payload.get("dataset_manifest"), "dataset_manifest")
    fingerprints = _mapping(payload.get("fingerprints"), "fingerprints")
    plan: dict[str, object] = {
        "adapter": config.adapter,
        "build_bounds": _build_bounds(config),
        "dataset_id": _string_or_missing(manifest.get("dataset_id")),
        "dataset_path": config.dataset.as_posix(),
        "external_effects": _external_effects(),
        "local_stage_used": False,
        "planned_outputs": _planned_outputs(),
        "schema_version": f"{TRAINING_STORE_SCHEMA_VERSION}.plan",
        "storage_backend": PFS_STORAGE_BACKEND,
        "store_format": TRAINING_STORE_FORMAT,
        "training_store_dir": store_dir.as_posix(),
        "fingerprints": {
            "dataset_fingerprint": _string_or_missing(fingerprints.get("dataset_fingerprint")),
            "statistics_fingerprint": _string_or_missing(
                fingerprints.get("statistics_fingerprint")
            ),
            "transform_fingerprint": _string_or_missing(fingerprints.get("transform_fingerprint")),
        },
    }
    config.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(config.output_dir / "training_store_plan.json", plan)
    return plan


def build_training_store(
    *,
    config: PerfBenchmarkConfig,
    artifact: DatasetArtifactV1,
) -> TrainingStoreBuildResult:
    """构建有界 PFS Training Store v0, 不写入源数据集。"""
    started = time.perf_counter()
    store_dir = require_training_store_dir(config)
    store_dir.mkdir(parents=True, exist_ok=True)
    (store_dir / "shards").mkdir(parents=True, exist_ok=True)
    (store_dir / "stats").mkdir(parents=True, exist_ok=True)

    payload = artifact.to_json_dict()
    dataset_manifest = _mapping(payload.get("dataset_manifest"), "dataset_manifest")
    modality = _mapping(payload.get("modality"), "modality")
    fingerprints = _mapping(payload.get("fingerprints"), "fingerprints")
    source_sample_count = _positive_int(dataset_manifest.get("sample_count"), "sample_count")
    source_episode_count = _positive_int(dataset_manifest.get("episode_count"), "episode_count")
    sample_count = min(source_sample_count, config.max_samples)
    episode_count = min(source_episode_count, config.max_episodes)
    action_dim = _feature_dim(_mapping(dataset_manifest.get("action_space"), "action_space"))
    state_dim = _feature_dim(_mapping(dataset_manifest.get("state_space"), "state_space"))
    camera_keys = _camera_keys(modality)
    robot_tag = _first_string(dataset_manifest.get("robot_tags"), default="unknown_robot")
    action_horizon = 1

    actions: NDArray[np.float32] = _synthetic_actions(
        sample_count=sample_count,
        action_dim=action_dim,
    )
    state: NDArray[np.float32] = _synthetic_state(sample_count=sample_count, state_dim=state_dim)
    action_mask = np.ones((sample_count, action_horizon, action_dim), dtype=np.bool_)
    language_text = np.array(
        [f"bounded training store sample {index}" for index in range(sample_count)],
        dtype=np.str_,
    )
    metadata_json = np.array(
        [
            json.dumps(
                {
                    "episode_id": _episode_id(index, episode_count),
                    "sample_id": _sample_id(index),
                    "sample_source": _sample_source(config, dataset_manifest),
                },
                sort_keys=True,
            )
            for index in range(sample_count)
        ],
        dtype=np.str_,
    )
    shard_relative = Path("shards") / "shard-000000.npz"
    shard_path = store_dir / shard_relative
    np.savez_compressed(
        shard_path,
        action_mask=action_mask,
        actions=actions,
        language_text=language_text,
        metadata_json=metadata_json,
        state=state,
    )

    sample_rows = _sample_rows(
        config=config,
        dataset_manifest=dataset_manifest,
        camera_keys=camera_keys,
        robot_tag=robot_tag,
        sample_count=sample_count,
        episode_count=episode_count,
        action_dim=action_dim,
        state_dim=state_dim,
        action_horizon=action_horizon,
        shard_relative=shard_relative.as_posix(),
    )
    episode_rows = _episode_rows(sample_count=sample_count, episode_count=episode_count)
    sample_index_path = store_dir / "sample_index.jsonl"
    episode_index_path = store_dir / "episode_index.jsonl"
    _write_jsonl(sample_index_path, sample_rows)
    _write_jsonl(episode_index_path, episode_rows)

    statistics = _action_statistics(actions=actions, artifact_payload=payload)
    statistics_path = store_dir / "stats" / "action_statistics.json"
    _write_json(statistics_path, statistics)

    checksums = _checksums(
        {
            "episode_index": episode_index_path,
            "sample_index": sample_index_path,
            "shard-000000": shard_path,
            "statistics": statistics_path,
        }
    )
    checksum_files = _mapping(checksums.get("files"), "checksum files")
    checksums_path = store_dir / "checksums.json"
    _write_json(checksums_path, checksums)

    manifest = _training_store_manifest(
        config=config,
        dataset_manifest=dataset_manifest,
        fingerprints=fingerprints,
        sample_count=sample_count,
        episode_count=episode_count,
        shard_relative=shard_relative.as_posix(),
        shard_checksum=_string(checksum_files.get("shard-000000"), "shard checksum"),
    )
    _write_json(store_dir / "training_store_manifest.json", manifest)

    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
    build_report = {
        "build_time_ms": elapsed_ms,
        "external_effects": _external_effects(),
        "full_dataset_conversion": False,
        "full_media_predecode": False,
        "input_sample_count": source_sample_count,
        "local_stage_used": False,
        "output_sample_count": sample_count,
        "raw_bounded_decode_baseline": {
            "preserved": True,
            "raw_batch_latency_ms_p50": "missing",
            "raw_batch_latency_ms_p95": "missing",
            "raw_media_decode_time_ms": "missing",
            "status": "baseline evidence must be supplied or recomputed on compute",
        },
        "schema_version": f"{TRAINING_STORE_SCHEMA_VERSION}.build_report",
        "storage_backend": PFS_STORAGE_BACKEND,
        "store_format": TRAINING_STORE_FORMAT,
    }
    _write_json(store_dir / "build_report.json", build_report)
    _write_json(
        store_dir / "read_benchmark_report.json",
        {
            "schema_version": f"{TRAINING_STORE_SCHEMA_VERSION}.read_report",
            "status": "not_run",
        },
    )
    return TrainingStoreBuildResult(
        store_dir=store_dir,
        manifest=manifest,
        build_report=build_report,
    )


def read_training_store_benchmark(config: PerfBenchmarkConfig) -> TrainingStoreReadResult:
    """读取 Training Store 并生成 raw/store 对比报告。"""
    store_dir = require_training_store_dir(config)
    started = time.perf_counter()
    manifest_path = store_dir / "training_store_manifest.json"
    sample_index_path = store_dir / "sample_index.jsonl"
    episode_index_path = store_dir / "episode_index.jsonl"
    checksums_path = store_dir / "checksums.json"
    statistics_path = store_dir / "stats" / "action_statistics.json"
    build_report_path = store_dir / "build_report.json"
    manifest = _read_json(manifest_path)
    sample_rows, sample_lookup_ms = _read_jsonl(sample_index_path)
    episode_rows, _episode_lookup_ms = _read_jsonl(episode_index_path)
    checksums = _read_json(checksums_path)
    _read_json(statistics_path)
    build_report = _read_json(build_report_path)
    shard_paths = _shard_paths(store_dir, manifest)
    shard_started = time.perf_counter()
    total_bytes = 0
    for path in shard_paths:
        total_bytes += path.stat().st_size
        with np.load(path) as shard:
            _ = shard["actions"].shape
            _ = shard["action_mask"].shape
    shard_read_ms = round((time.perf_counter() - shard_started) * 1000.0, 6)
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
    pfs_read_mb_s = _mb_per_second(total_bytes=total_bytes, elapsed_ms=max(shard_read_ms, 0.001))
    file_open_count = 5 + len(shard_paths)
    raw_baseline = _mapping(build_report.get("raw_bounded_decode_baseline"), "raw_bounded_decode")
    raw_p50 = raw_baseline.get("raw_batch_latency_ms_p50", "missing")
    raw_p95 = raw_baseline.get("raw_batch_latency_ms_p95", "missing")
    raw_media_decode = raw_baseline.get("raw_media_decode_time_ms", "missing")
    effective = _effective_raw_comparison(
        raw_p50=raw_p50,
        raw_p95=raw_p95,
        raw_media_decode=raw_media_decode,
    )
    store_p50 = elapsed_ms
    store_p95 = elapsed_ms
    speedup = _speedup(effective["raw_effective_batch_latency_ms_p50"], store_p50)
    missing = _missing_telemetry(
        raw_p50=raw_p50,
        raw_media_decode=raw_media_decode,
    )
    comparison = {
        **effective,
        "decode_avoided_ratio": 1.0,
        "missing_telemetry": missing,
        "pfs_file_open_count": file_open_count,
        "pfs_metadata_ops_estimate": file_open_count + len(sample_rows) + len(episode_rows),
        "pfs_read_mb_s": pfs_read_mb_s,
        "prepacked_shard_read_time_ms": shard_read_ms,
        "raw_batch_latency_ms_p50": raw_p50,
        "raw_batch_latency_ms_p95": raw_p95,
        "raw_media_decode_time_ms": raw_media_decode,
        "sample_index_lookup_time_ms": sample_lookup_ms,
        "speedup_vs_raw_decode": speedup,
        "training_store_batch_latency_ms_p50": store_p50,
        "training_store_batch_latency_ms_p95": store_p95,
        "training_store_build_time_ms": build_report.get("build_time_ms", "missing"),
        "training_store_read_time_ms": elapsed_ms,
    }
    report = {
        "checksums_verified": _checksums_match(store_dir, checksums),
        "comparison": comparison,
        "external_effects": _external_effects(),
        "sample_count": len(sample_rows),
        "schema_version": f"{TRAINING_STORE_SCHEMA_VERSION}.read_report",
        "storage_backend": manifest.get("storage_backend", "missing"),
    }
    _write_json(store_dir / "read_benchmark_report.json", report)
    return TrainingStoreReadResult(store_dir=store_dir, comparison=comparison, report=report)


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
    """生成缺失 telemetry 列表, 不把已存在 raw 字段误报为缺失。"""
    missing = [
        "gpu_util_pct",
        "gpu_memory_used_mb",
        "hbm_bw_pct",
    ]
    if _optional_float(raw_p50) is None:
        missing.append("raw_batch_latency_ms_p50")
    if _optional_float(raw_media_decode) is None:
        missing.append("raw_media_decode_time_ms")
    return missing


def _planned_outputs() -> list[str]:
    """返回 Training Store v0 计划输出清单。"""
    return [
        "training_store_manifest.json",
        "sample_index.jsonl",
        "episode_index.jsonl",
        "shards/*.npz",
        "stats/action_statistics.json",
        "checksums.json",
        "build_report.json",
        "read_benchmark_report.json",
    ]


def _external_effects() -> dict[str, bool]:
    """返回 Training Store 构建/读取的外部副作用边界。"""
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


def _build_bounds(config: PerfBenchmarkConfig) -> dict[str, int]:
    """返回 bounded 构建参数。"""
    return {
        "max_decode_seconds": config.max_decode_seconds,
        "max_episodes": config.max_episodes,
        "max_samples": config.max_samples,
    }


def _training_store_manifest(
    *,
    config: PerfBenchmarkConfig,
    dataset_manifest: Mapping[str, object],
    fingerprints: Mapping[str, object],
    sample_count: int,
    episode_count: int,
    shard_relative: str,
    shard_checksum: str,
) -> dict[str, object]:
    """构造 Training Store manifest。"""
    dataset_fingerprint = _string_or_missing(fingerprints.get("dataset_fingerprint"))
    statistics_fingerprint = _string_or_missing(fingerprints.get("statistics_fingerprint"))
    transform_fingerprint = _string_or_missing(fingerprints.get("transform_fingerprint"))
    return {
        "adapter_name": config.adapter,
        "adapter_version": _string_or_missing(dataset_manifest.get("converter_version")),
        "build_bounds": _build_bounds(config),
        "build_mode": "bounded",
        "checksums_path": "checksums.json",
        "created_by": "autovla.dataloader.perf.training_store",
        "dataset_fingerprint": dataset_fingerprint,
        "dataset_id": _string_or_missing(dataset_manifest.get("dataset_id")),
        "episode_count": episode_count,
        "episode_index_path": "episode_index.jsonl",
        "external_effects": _external_effects(),
        "local_stage_used": False,
        "sample_count": sample_count,
        "sample_index_path": "sample_index.jsonl",
        "schema_version": TRAINING_STORE_SCHEMA_VERSION,
        "shard_count": 1,
        "shards": [
            {
                "checksum": shard_checksum,
                "path": shard_relative,
                "sample_count": sample_count,
            }
        ],
        "source_dataset_path": config.dataset.as_posix(),
        "source_format": _string_or_missing(dataset_manifest.get("source_format")),
        "statistics_fingerprint": statistics_fingerprint,
        "statistics_scope": _string_or_missing(dataset_manifest.get("statistics_scope")),
        "storage_backend": PFS_STORAGE_BACKEND,
        "store_format": TRAINING_STORE_FORMAT,
        "store_id": f"training-store::{dataset_fingerprint[:16]}",
        "transform_fingerprint": transform_fingerprint,
    }


def _sample_rows(
    *,
    config: PerfBenchmarkConfig,
    dataset_manifest: Mapping[str, object],
    camera_keys: Sequence[str],
    robot_tag: str,
    sample_count: int,
    episode_count: int,
    action_dim: int,
    state_dim: int,
    action_horizon: int,
    shard_relative: str,
) -> list[dict[str, object]]:
    """构造 sample_index.jsonl 行。"""
    rows: list[dict[str, object]] = []
    for index in range(sample_count):
        rows.append(
            {
                "action_dim": action_dim,
                "action_horizon": action_horizon,
                "action_mask_shape": [action_horizon, action_dim],
                "action_shape": [action_horizon, action_dim],
                "camera_keys": list(camera_keys),
                "checksum": hashlib.sha256(f"sample-{index}".encode("utf-8")).hexdigest(),
                "episode_id": _episode_id(index, episode_count),
                "language_key": "task",
                "modality_refs": {
                    "action": "modality.action",
                    "cameras": "modality.cameras",
                    "language": "modality.language",
                    "state": "modality.state",
                },
                "robot_tag": robot_tag,
                "sample_id": _sample_id(index),
                "sample_source": _sample_source(config, dataset_manifest),
                "shard_path": shard_relative,
                "shard_row": index,
                "split": "train",
                "state_shape": [state_dim],
                "window_length": action_horizon,
                "window_start": index,
            }
        )
    return rows


def _episode_rows(*, sample_count: int, episode_count: int) -> list[dict[str, object]]:
    """构造 episode_index.jsonl 行。"""
    rows: list[dict[str, object]] = []
    for episode in range(episode_count):
        sample_ids = [
            _sample_id(index)
            for index in range(sample_count)
            if index % max(episode_count, 1) == episode
        ]
        rows.append(
            {
                "episode_id": f"episode-{episode:06d}",
                "sample_count": len(sample_ids),
                "sample_ids": sample_ids,
                "split": "train",
            }
        )
    return rows


def _action_statistics(
    *,
    actions: NDArray[np.float32],
    artifact_payload: Mapping[str, object],
) -> dict[str, object]:
    """基于有界 shard payload 生成 action statistics 报告。"""
    statistics = _mapping(artifact_payload.get("statistics"), "statistics")
    return {
        "action_mean": actions.mean(axis=(0, 1)).round(6).tolist(),
        "action_std": actions.std(axis=(0, 1)).round(6).tolist(),
        "action_min": actions.min(axis=(0, 1)).round(6).tolist(),
        "action_max": actions.max(axis=(0, 1)).round(6).tolist(),
        "source": "bounded_training_store_v0",
        "statistics_scope": statistics.get("statistics_scope", "mixed"),
    }


def _sample_source(
    config: PerfBenchmarkConfig,
    dataset_manifest: Mapping[str, object],
) -> dict[str, object]:
    """构造样本来源记录。"""
    return {
        "adapter": config.adapter,
        "bounded_preview": True,
        "dataset": config.dataset.as_posix(),
        "source_format": _string_or_missing(dataset_manifest.get("source_format")),
    }


def _synthetic_actions(*, sample_count: int, action_dim: int) -> NDArray[np.float32]:
    """生成确定性 action payload, 用于 bounded store 契约验证。"""
    values: NDArray[np.float32] = np.arange(sample_count * action_dim, dtype=np.float32)
    reshaped = values.reshape(sample_count, 1, action_dim) / max(float(action_dim), 1.0)
    return cast(NDArray[np.float32], reshaped)


def _synthetic_state(*, sample_count: int, state_dim: int) -> NDArray[np.float32]:
    """生成确定性 state payload, 不读取 parquet 行。"""
    values: NDArray[np.float32] = np.arange(sample_count * state_dim, dtype=np.float32)
    reshaped = values.reshape(sample_count, state_dim) / max(float(state_dim), 1.0)
    return cast(NDArray[np.float32], reshaped)


def _checksums(files: Mapping[str, Path]) -> dict[str, object]:
    """计算 store 文件校验和。"""
    return {
        "algorithm": "sha256",
        "files": {key: _sha256_file(path) for key, path in sorted(files.items())},
    }


def _checksums_match(store_dir: Path, checksums: Mapping[str, object]) -> bool:
    """校验当前读取路径的 checksum。"""
    files = _mapping(checksums.get("files"), "files")
    expected = {
        "episode_index": store_dir / "episode_index.jsonl",
        "sample_index": store_dir / "sample_index.jsonl",
        "shard-000000": store_dir / "shards" / "shard-000000.npz",
        "statistics": store_dir / "stats" / "action_statistics.json",
    }
    for key, path in expected.items():
        if files.get(key) != _sha256_file(path):
            return False
    return True


def _sha256_file(path: Path) -> str:
    """计算文件 SHA256。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _shard_paths(store_dir: Path, manifest: Mapping[str, object]) -> list[Path]:
    """从 manifest 解析 shard 路径。"""
    raw_shards = manifest.get("shards")
    if not isinstance(raw_shards, list):
        raise ValueError("manifest shards must be a list")
    shard_items = cast(list[object], raw_shards)
    paths: list[Path] = []
    for raw in shard_items:
        shard = _mapping(raw, "shard")
        paths.append(store_dir / _string(shard.get("path"), "shard path"))
    return paths


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON object 文件。"""
    loaded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(loaded, Mapping):
        raise TypeError(f"{path} must contain a JSON object")
    return dict(cast(Mapping[str, object], loaded))


def _read_jsonl(path: Path) -> tuple[list[dict[str, object]], float]:
    """读取 JSONL 文件并返回读取耗时。"""
    started = time.perf_counter()
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        loaded = cast(object, json.loads(line))
        if not isinstance(loaded, Mapping):
            raise TypeError(f"{path} row must contain a JSON object")
        rows.append(dict(cast(Mapping[str, object], loaded)))
    return rows, round((time.perf_counter() - started) * 1000.0, 6)


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    """写出稳定 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    shape_values = cast(list[object], raw_shape)
    first = shape_values[0]
    if isinstance(first, bool) or not isinstance(first, int) or first <= 0:
        raise ValueError("feature shape dimension must be positive")
    return first


def _camera_keys(modality: Mapping[str, object]) -> list[str]:
    """读取相机 feature keys。"""
    raw = modality.get("cameras")
    if not isinstance(raw, list):
        return []
    camera_items = cast(list[object], raw)
    keys: list[str] = []
    for item in camera_items:
        camera = _mapping(item, "camera")
        keys.append(_string(camera.get("feature_key"), "camera feature_key"))
    return keys


def _positive_int(value: object, name: str) -> int:
    """校验正整数。"""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive int")
    return value


def _mapping(value: object, name: str) -> Mapping[str, object]:
    """校验 mapping。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return cast(Mapping[str, object], value)


def _string(value: object, name: str) -> str:
    """校验字符串。"""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _string_or_missing(value: object) -> str:
    """把字符串字段规范化, 缺失时返回 missing。"""
    return value if isinstance(value, str) and value else "missing"


def _first_string(value: object, *, default: str) -> str:
    """读取字符串列表首项。"""
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return default


def _sample_id(index: int) -> str:
    """构造稳定 sample id。"""
    return f"sample-{index:06d}"


def _episode_id(index: int, episode_count: int) -> str:
    """构造稳定 episode id。"""
    return f"episode-{index % max(episode_count, 1):06d}"


def _mb_per_second(*, total_bytes: int, elapsed_ms: float) -> float:
    """计算 MB/s。"""
    mb = total_bytes / (1024.0 * 1024.0)
    return round(mb / (elapsed_ms / 1000.0), 6)


def _speedup(raw_p50: object, store_p50: float) -> object:
    """计算 raw/store speedup, raw 缺失时保留 missing。"""
    raw_value = _optional_float(raw_p50)
    if raw_value is not None:
        return round(raw_value / max(store_p50, 0.001), 6)
    return "missing"


def _optional_float(value: object) -> float | None:
    """把可选数字字段转为 float。"""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None
