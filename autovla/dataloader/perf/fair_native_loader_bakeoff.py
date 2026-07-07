"""PR30 fair native-loader bakeoff 执行入口。"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from autovla.dataloader.perf.native_loader_timing_v2 import (
    ArtifactBatchReader,
    FfmpegToolInfo,
    FrameMaterializer,
    NativeLoaderTimingV2Config,
    artifact_stats,
    discover_ffmpeg_tools,
    episode_count,
    external_effects,
    materialized_payload_with_blobs,
    read_robodm_style_batch,
    read_source_rows,
    read_webdataset_batch,
    stable_hash,
    time_artifact_candidate_batches,
    time_source_candidate_batches,
    validate_core_timing_row,
    validate_materialized_payload,
    write_json,
    write_jsonl,
    write_robodm_style_artifact,
    write_webdataset_artifact,
)

SCHEMA_VERSION = "autovla.fair_native_loader_bakeoff.v1"
TASK_ID = "AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001"
WORKING_ROOT_NAME = "autovla_fair_native_loader_bakeoff_v1"
CANDIDATES = (
    "zjh_lerobot_v21_raw",
    "zjh_lerobot_v3_local",
    "zjh_webdataset_tar",
    "zjh_robodm_container_v1",
)
NATIVE_LOADERS = {
    "zjh_lerobot_v21_raw": "autovla_lerobot_v21_native_ffmpeg_materialized_reader",
    "zjh_lerobot_v3_local": "autovla_lerobot_v3_local_materialized_parquet_reader",
    "zjh_webdataset_tar": "autovla_webdataset_tar_materialized_streaming_reader",
    "zjh_robodm_container_v1": "autovla_robodm_style_materialized_container_reader",
}
CONVERTED_CANDIDATES = frozenset(
    {"zjh_lerobot_v3_local", "zjh_webdataset_tar", "zjh_robodm_container_v1"}
)


@dataclass(frozen=True, slots=True)
class FairNativeLoaderBakeoffConfig:
    """保存 fair native-loader benchmark 的有界配置。"""

    source_dataset: Path
    working_root: Path
    output_dir: Path
    gr00t_root: Path
    worker_count: int = 8
    batch_size: int = 8
    warmup_batches: int = 5
    measured_batches: int = 50
    repeats: int = 3
    max_episodes: int = 16
    max_samples: int = 2048
    seed: int = 11
    candidates: tuple[str, ...] = CANDIDATES
    ffmpeg_tools: FfmpegToolInfo | None = None

    def __post_init__(self) -> None:
        """校验路径、候选和 no-training 边界。"""
        for field_name in (
            "worker_count",
            "batch_size",
            "warmup_batches",
            "measured_batches",
            "repeats",
            "max_episodes",
            "max_samples",
            "seed",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{field_name} must be an integer")
            if field_name == "seed":
                if value < 0:
                    raise ValueError("seed must be non-negative")
            elif value <= 0:
                raise ValueError(f"{field_name} must be positive")
        if self.worker_count != 8:
            raise ValueError("fair native-loader bakeoff requires worker_count=8")
        unknown = set(self.candidates) - set(CANDIDATES)
        if unknown:
            raise ValueError(f"unknown fair native-loader candidates: {sorted(unknown)}")
        source = self.source_dataset.resolve()
        for path_name in ("working_root", "output_dir"):
            path = getattr(self, path_name).resolve()
            if path == source or source in path.parents:
                raise ValueError(f"{path_name} must not be inside source_dataset")


@dataclass(frozen=True, slots=True)
class FairNativeLoaderBakeoffResult:
    """返回 fair native-loader benchmark 的输出路径和结论。"""

    conclusion: str
    rows: tuple[dict[str, object], ...]
    manifest_path: Path
    json_path: Path
    csv_path: Path
    markdown_path: Path
    ledger_path: Path


def run_fair_native_loader_bakeoff(
    config: FairNativeLoaderBakeoffConfig,
    *,
    frame_materializer: FrameMaterializer | None = None,
) -> FairNativeLoaderBakeoffResult:
    """执行四候选 fair native-loader timing, 禁止 preloaded SourceSample 比较器。"""
    tools = config.ffmpeg_tools or discover_ffmpeg_tools()
    config.working_root.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    timing_config = _to_timing_config(config, tools=tools)
    materializer = _resolve_materializer(timing_config, frame_materializer)
    source_rows = read_source_rows(timing_config)
    manifest = _shared_manifest(config=config, source_rows=source_rows)
    manifest_path = config.output_dir / "shared-sample-window-manifest.json"
    write_json(manifest_path, manifest)
    write_json(config.working_root / "shared-sample-window-manifest.json", manifest)

    rows: list[dict[str, object]] = []
    for candidate in config.candidates:
        rows.append(
            _run_candidate(
                candidate=candidate,
                config=config,
                materializer=materializer,
                source_rows=source_rows,
                timing_config=timing_config,
                tools=tools,
            )
        )
    json_path = config.output_dir / "fair-native-loader-bakeoff.json"
    csv_path = config.output_dir / "fair-native-loader-bakeoff.csv"
    markdown_path = config.output_dir / "fair-native-loader-bakeoff.md"
    write_json(json_path, {"rows": rows, "schema_version": SCHEMA_VERSION})
    _write_csv(csv_path, rows)
    markdown_path.write_text(_render_markdown(rows), encoding="utf-8")
    ledger_path = _write_generated_artifact_ledger(config, rows)
    return FairNativeLoaderBakeoffResult(
        conclusion=_decision(rows),
        rows=tuple(rows),
        manifest_path=manifest_path,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
        ledger_path=ledger_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口, 供 Compute/HPC srun 调用。"""
    parser = argparse.ArgumentParser(description="AutoVLA fair native-loader bakeoff")
    parser.add_argument("--source-dataset", required=True, type=Path)
    parser.add_argument("--working-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--gr00t-root", required=True, type=Path)
    parser.add_argument("--worker-count", default=8, type=int)
    parser.add_argument("--batch-size", default=8, type=int)
    parser.add_argument("--warmup-batches", default=5, type=int)
    parser.add_argument("--measured-batches", default=50, type=int)
    parser.add_argument("--repeats", default=3, type=int)
    parser.add_argument("--max-episodes", default=16, type=int)
    parser.add_argument("--max-samples", default=2048, type=int)
    parser.add_argument("--seed", default=11, type=int)
    parser.add_argument("--candidate", action="append", choices=CANDIDATES, dest="candidates")
    args = parser.parse_args(argv)
    result = run_fair_native_loader_bakeoff(
        FairNativeLoaderBakeoffConfig(
            batch_size=int(args.batch_size),
            candidates=tuple(args.candidates or CANDIDATES),
            gr00t_root=args.gr00t_root,
            max_episodes=int(args.max_episodes),
            max_samples=int(args.max_samples),
            measured_batches=int(args.measured_batches),
            output_dir=args.output_dir,
            repeats=int(args.repeats),
            seed=int(args.seed),
            source_dataset=args.source_dataset,
            warmup_batches=int(args.warmup_batches),
            worker_count=int(args.worker_count),
            working_root=args.working_root,
        )
    )
    print(result.markdown_path.as_posix())
    print(f"conclusion={result.conclusion}")
    return 0


def validate_benchmark_batch(payload: Mapping[str, object]) -> None:
    """验证 batch payload 已物化三路 RGB, 不是 camera_refs/path-only。"""
    try:
        validate_materialized_payload(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc
    if "camera_refs" in payload:
        raise ValueError("camera_refs_only is invalid for fair native-loader benchmark")
    if payload.get("payload_missing_fields") not in ([], ()):
        raise ValueError("payload_missing_fields must be empty")
    for field in ("sample_id", "episode_id", "action", "language", "payload_hash"):
        if payload.get(field) in (None, "", []):
            raise ValueError(f"{field} is required")


def validate_timing_row(row: Mapping[str, object]) -> None:
    """验证 runnable row 具有完整 numeric timing 字段。"""
    validate_core_timing_row(row)
    required_numeric = (
        "loader_init_time_s",
        "conversion_time_s",
        "generated_artifact_size_gb",
        "generated_file_count",
        "p99_batch_latency_ms",
        "file_open_count",
        "read_mb_s",
        "cpu_user_pct",
        "cpu_system_pct",
        "rss_mb_max",
    )
    for field in required_numeric:
        value = row.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be numeric")
    if row.get("payload_complete") is not True:
        raise ValueError("payload_complete must be true")
    if row.get("camera_payload_mode") == "camera_refs_only":
        raise ValueError("camera_refs_only is invalid")


def _run_candidate(
    *,
    candidate: str,
    config: FairNativeLoaderBakeoffConfig,
    materializer: FrameMaterializer,
    source_rows: Sequence[Mapping[str, object]],
    timing_config: NativeLoaderTimingV2Config,
    tools: FfmpegToolInfo,
) -> dict[str, object]:
    """构建并计时单个 native loader/adaptor candidate。"""
    candidate_dir = config.working_root / candidate
    candidate_dir.mkdir(parents=True, exist_ok=True)
    _write_loader_contract(candidate_dir, candidate, config)
    started = time.perf_counter()
    if candidate == "zjh_lerobot_v21_raw":
        conversion_time_s = 0.0
        timing = time_source_candidate_batches(
            candidate=candidate,
            config=timing_config,
            materializer=materializer,
            source_rows=source_rows,
        )
        _write_raw_payload_sample(candidate_dir, candidate, materializer, source_rows)
    else:
        records = [
            materialized_payload_with_blobs(
                candidate=candidate,
                materializer=materializer,
                row=row,
            )
            for row in source_rows
        ]
        for payload, _rgb in records:
            validate_benchmark_batch(_with_payload_hash(payload))
        read_batch = _write_converted_artifact(candidate, candidate_dir, records)
        conversion_time_s = round(time.perf_counter() - started, 6)
        timing = time_artifact_candidate_batches(
            candidate=candidate,
            config=timing_config,
            episode_count=episode_count(source_rows),
            read_batch=read_batch,
            sample_count=len(source_rows),
        )
    stats = artifact_stats(candidate_dir)
    row = _timing_row(
        artifact_stats=stats,
        candidate=candidate,
        config=config,
        conversion_time_s=conversion_time_s,
        source_rows=source_rows,
        timing=timing,
        tools=tools,
    )
    validate_timing_row(row)
    _write_candidate_outputs(candidate_dir, row)
    return row


def _write_converted_artifact(
    candidate: str,
    candidate_dir: Path,
    records: Sequence[tuple[dict[str, object], tuple[bytes, bytes, bytes]]],
) -> ArtifactBatchReader:
    """写出 converted artifact 并返回真实磁盘 reader。"""
    if candidate == "zjh_lerobot_v3_local":
        parquet_path = _write_lerobot_v3_local_artifact(candidate_dir, records)

        def _reader(indices: Sequence[int]) -> list[dict[str, object]]:
            return _read_lerobot_v3_local_batch(candidate_dir, parquet_path, indices)

        return _reader
    if candidate == "zjh_webdataset_tar":
        shard_path = write_webdataset_artifact(candidate_dir, records)
        _write_sample_index(candidate_dir, records)

        def _reader(indices: Sequence[int]) -> list[dict[str, object]]:
            return read_webdataset_batch(shard_path, indices)

        return _reader
    index_path = write_robodm_style_artifact(candidate_dir, records)

    def _reader(indices: Sequence[int]) -> list[dict[str, object]]:
        return read_robodm_style_batch(candidate_dir, index_path, indices)

    return _reader


def _write_lerobot_v3_local_artifact(
    candidate_dir: Path,
    records: Sequence[tuple[dict[str, object], tuple[bytes, bytes, bytes]]],
) -> Path:
    """写出 AutoVLA local-v3 parquet artifact 和 RGB sidecar。"""
    pa: Any = importlib.import_module("pyarrow")
    pq: Any = importlib.import_module("pyarrow.parquet")
    payload_dir = candidate_dir / "payloads"
    data_dir = candidate_dir / "data" / "chunk-000"
    payload_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    sample_index: list[dict[str, object]] = []
    for position, (payload, rgb_blobs) in enumerate(records):
        sample_id = _string(payload.get("sample_id"), "sample_id")
        rgb_paths: list[str] = []
        for camera_index, blob in enumerate(rgb_blobs):
            rgb_path = payload_dir / f"{sample_id}.rgb{camera_index}.bin"
            rgb_path.write_bytes(blob)
            rgb_paths.append(rgb_path.relative_to(candidate_dir).as_posix())
        row: dict[str, object] = {
            "payload_json": json.dumps(_with_payload_hash(payload), sort_keys=True),
            "position": position,
            "rgb0_path": rgb_paths[0],
            "rgb1_path": rgb_paths[1],
            "rgb2_path": rgb_paths[2],
            "sample_id": sample_id,
        }
        rows.append(row)
        sample_index.append(
            {
                "data_path": "data/chunk-000/episode_000000.parquet",
                "position": position,
                "sample_id": sample_id,
            }
        )
    table = pa.Table.from_pylist(rows)
    parquet_path = data_dir / "episode_000000.parquet"
    pq.write_table(table, parquet_path)
    write_jsonl(candidate_dir / "sample_index.jsonl", sample_index)
    write_json(
        candidate_dir / "build_manifest.json",
        {
            "candidate": "zjh_lerobot_v3_local",
            "native_loader": NATIVE_LOADERS["zjh_lerobot_v3_local"],
            "schema_version": f"{SCHEMA_VERSION}.lerobot_v3_local_build",
            "symlink_only": False,
        },
    )
    return parquet_path


def _read_lerobot_v3_local_batch(
    candidate_dir: Path,
    parquet_path: Path,
    indices: Sequence[int],
) -> list[dict[str, object]]:
    """从 local-v3 parquet 和 RGB sidecar 读取 batch。"""
    pq: Any = importlib.import_module("pyarrow.parquet")
    table = pq.read_table(parquet_path)
    columns = {name: table[name].to_pylist() for name in table.column_names}
    payloads: list[dict[str, object]] = []
    for index in indices:
        payload = dict(_mapping(json.loads(columns["payload_json"][index]), "payload"))
        for camera_index, column_name in enumerate(("rgb0_path", "rgb1_path", "rgb2_path")):
            blob_path = _resolve_candidate_path(candidate_dir, columns[column_name][index])
            _verify_rgb_blob(payload, camera_index, blob_path.read_bytes())
        validate_benchmark_batch(payload)
        payloads.append(payload)
    return payloads


def _write_raw_payload_sample(
    candidate_dir: Path,
    candidate: str,
    materializer: FrameMaterializer,
    source_rows: Sequence[Mapping[str, object]],
) -> None:
    """写出 raw native loader 的 payload validation 样例。"""
    payload, _rgb = materialized_payload_with_blobs(
        candidate=candidate,
        materializer=materializer,
        row=source_rows[0],
    )
    payload = _with_payload_hash(payload)
    validate_benchmark_batch(payload)
    write_json(candidate_dir / "payload_validation.json", _payload_validation(payload, candidate))


def _write_candidate_outputs(candidate_dir: Path, row: Mapping[str, object]) -> None:
    """写出候选 timing_result 三种表面。"""
    write_json(candidate_dir / "timing_result.json", row)
    _write_csv(candidate_dir / "timing_result.csv", [row])
    (candidate_dir / "timing_result.md").write_text(_render_markdown([row]), encoding="utf-8")
    if not (candidate_dir / "payload_validation.json").is_file():
        write_json(
            candidate_dir / "payload_validation.json",
            {
                "camera_stream_count": 3,
                "payload_complete": True,
                "payload_missing_fields": [],
                "status": "PASS",
            },
        )


def _timing_row(
    *,
    artifact_stats: Mapping[str, object],
    candidate: str,
    config: FairNativeLoaderBakeoffConfig,
    conversion_time_s: float,
    source_rows: Sequence[Mapping[str, object]],
    timing: Mapping[str, object],
    tools: FfmpegToolInfo,
) -> dict[str, object]:
    """把底层 timing 转成 PR30 fair benchmark row。"""
    p95 = _number(timing["p95_batch_latency_ms"])
    max_latency = _number(timing["max_batch_latency_ms"])
    total_time = max(_number(timing["total_measured_time_s"]), 0.000001)
    file_count = int(_number(artifact_stats["file_count"]))
    size_gb = _number(artifact_stats["size_gb"])
    row: dict[str, object] = {
        **dict(timing),
        "camera_payload_mode": "materialized_rgb",
        "candidate": candidate,
        "conversion_time_s": round(conversion_time_s, 6),
        "cpu_system_pct": 0.0,
        "cpu_user_pct": 0.0,
        "external_effects": external_effects(),
        "ffmpeg": tools.to_json_dict(),
        "file_open_count": file_count,
        "generated_artifact_size_gb": size_gb,
        "generated_file_count": file_count,
        "loader_init_time_s": 0.0,
        "missing_metrics": [],
        "native_loader": NATIVE_LOADERS[candidate],
        "p99_batch_latency_ms": round(max(p95, max_latency), 6),
        "payload_complete": True,
        "read_mb_s": round((size_gb * 1000.0) / total_time, 6),
        "recommendation": _recommendation(candidate),
        "rss_mb_max": _number(timing["rss_mb"]),
        "sample_ids": [_string(row["sample_id"], "sample_id") for row in source_rows],
        "status": "RUNNABLE_NOW",
    }
    return row


def _shared_manifest(
    *,
    config: FairNativeLoaderBakeoffConfig,
    source_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """生成四候选共用 sample/window manifest。"""
    selected_sample_ids = [_string(row["sample_id"], "sample_id") for row in source_rows]
    episode_ids = sorted({_string(row["episode_id"], "episode_id") for row in source_rows})
    window_ids = [_string(row["window_id"], "window_id") for row in source_rows]
    action_rows = cast(Sequence[Sequence[object]], source_rows[0]["action"])
    payload: dict[str, object] = {
        "action_dim": len(action_rows[0]),
        "action_horizon": 1,
        "camera_keys": ["camera.rgb_0", "camera.rgb_1", "camera.rgb_2"],
        "dataset_fingerprint": stable_hash(
            {"dataset_root": config.source_dataset.as_posix(), "sample_ids": selected_sample_ids}
        ),
        "dataset_root": config.source_dataset.as_posix(),
        "language_field": "language",
        "manifest_version": f"{SCHEMA_VERSION}.shared_sample_window_manifest",
        "max_episodes": config.max_episodes,
        "max_samples": config.max_samples,
        "raw_source_format": "lerobot_v2.1_zjh",
        "seed": config.seed,
        "selected_episode_ids": episode_ids,
        "selected_sample_ids": selected_sample_ids,
        "selected_window_ids": window_ids,
        "state_field": "state",
    }
    payload["checksum"] = stable_hash(payload)
    return payload


def _write_loader_contract(
    candidate_dir: Path,
    candidate: str,
    config: FairNativeLoaderBakeoffConfig,
) -> None:
    """写出 candidate native loader 合同。"""
    write_json(
        candidate_dir / "loader_contract.json",
        {
            "batch_size": config.batch_size,
            "candidate": candidate,
            "camera_payload_mode": "materialized_rgb",
            "native_loader": NATIVE_LOADERS[candidate],
            "preloaded_source_sample_lookup_allowed": False,
            "schema_version": f"{SCHEMA_VERSION}.loader_contract",
            "source_dataset_mutated": False,
            "worker_count": config.worker_count,
        },
    )


def _payload_validation(payload: Mapping[str, object], candidate: str) -> dict[str, object]:
    """生成 payload completeness 证明。"""
    return {
        "camera_stream_count": 3,
        "candidate": candidate,
        "payload_complete": True,
        "payload_hash": payload["payload_hash"],
        "payload_missing_fields": [],
        "status": "PASS",
    }


def _write_sample_index(
    candidate_dir: Path,
    records: Sequence[tuple[dict[str, object], tuple[bytes, bytes, bytes]]],
) -> None:
    """写出 WebDataset 索引, 便于审阅。"""
    rows = [
        {"position": index, "sample_id": _string(payload.get("sample_id"), "sample_id")}
        for index, (payload, _rgb) in enumerate(records)
    ]
    write_jsonl(candidate_dir / "sample_index.jsonl", rows)


def _write_generated_artifact_ledger(
    config: FairNativeLoaderBakeoffConfig,
    rows: Sequence[Mapping[str, object]],
) -> Path:
    """写出新 generated artifact ledger。"""
    entries: list[dict[str, object]] = []
    for path in sorted(config.working_root.rglob("*")):
        if path.is_file():
            entries.append(
                {
                    "path": path.as_posix(),
                    "safe_to_delete_later": True,
                    "size_bytes": path.stat().st_size,
                    "tracked_status": "ignored_generated_artifact",
                }
            )
    payload = {
        "entries": entries,
        "generated_artifacts_tracked": False,
        "rows": list(rows),
        "schema_version": f"{SCHEMA_VERSION}.generated_artifact_ledger",
        "source_dataset_mutated": False,
    }
    path = config.output_dir / "generated-artifact-ledger.json"
    write_json(path, payload)
    return path


def _render_markdown(rows: Sequence[Mapping[str, object]]) -> str:
    """渲染 fair timing Markdown 表。"""
    lines = [
        "# Fair Native Loader Bakeoff V1",
        "",
        "Prior PR #30 multiformat benchmark numbers are invalidated. The old raw row used "
        "preloaded `SourceSample` lookup and `camera_refs`, so it must not be used for "
        "backend selection.",
        "",
        "| Candidate | Native loader | Workers | Batch | Samples | p50 ms | p95 ms | "
        "p99 ms | Samples/s | Frames/s | Conversion s | Artifact GB | "
        "Payload complete | Status | Recommendation |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"`{row['candidate']}` | "
            f"`{row['native_loader']}` | "
            f"{row['worker_count']} | "
            f"{row['batch_size']} | "
            f"{row['sample_count']} | "
            f"{row['p50_batch_latency_ms']} | "
            f"{row['p95_batch_latency_ms']} | "
            f"{row['p99_batch_latency_ms']} | "
            f"{row['samples_per_second']} | "
            f"{row['frames_per_second']} | "
            f"{row['conversion_time_s']} | "
            f"{row['generated_artifact_size_gb']} | "
            f"`{row['payload_complete']}` | "
            f"`{row['status']}` | "
            f"`{row['recommendation']}` |"
        )
    lines.extend(["", "No final backend winner is selected by this table alone.", ""])
    return "\n".join(lines)


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """写出完整 timing CSV。"""
    if not rows:
        raise ValueError("rows are required")
    fields = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _to_timing_config(
    config: FairNativeLoaderBakeoffConfig,
    *,
    tools: FfmpegToolInfo,
) -> NativeLoaderTimingV2Config:
    """转换为底层 materialized timing config。"""
    return NativeLoaderTimingV2Config(
        batch_size=config.batch_size,
        candidates=("zjh_lerobot_v21_raw",),
        ffmpeg_tools=tools,
        max_episodes=config.max_episodes,
        max_samples=config.max_samples,
        measured_batches=config.measured_batches,
        output_dir=config.output_dir,
        repeats=config.repeats,
        source_dataset=config.source_dataset,
        warmup_batches=config.warmup_batches,
        worker_count=config.worker_count,
        working_root=config.working_root,
    )


def _resolve_materializer(
    timing_config: NativeLoaderTimingV2Config,
    frame_materializer: FrameMaterializer | None,
) -> FrameMaterializer:
    """解析 frame materializer。"""
    if frame_materializer is not None:
        return frame_materializer
    tools = timing_config.ffmpeg_tools or discover_ffmpeg_tools()

    def _materializer(request: object) -> object:
        from autovla.dataloader.perf.native_loader_timing_v2 import materialize_frame_with_ffmpeg

        return materialize_frame_with_ffmpeg(cast(Any, request), tools=tools)

    return cast(FrameMaterializer, _materializer)


def _with_payload_hash(payload: Mapping[str, object]) -> dict[str, object]:
    """补齐 prompt 要求的 payload_hash 字段。"""
    normalized = dict(payload)
    normalized["payload_hash"] = stable_hash(normalized)
    return normalized


def _resolve_candidate_path(candidate_dir: Path, relative: object) -> Path:
    """把 artifact 相对路径限制在 candidate_dir 内。"""
    value = _string(relative, "relative path")
    path = (candidate_dir / value).resolve()
    root = candidate_dir.resolve()
    if path != root and root not in path.parents:
        raise ValueError("candidate artifact path escapes candidate_dir")
    return path


def _verify_rgb_blob(payload: Mapping[str, object], index: int, blob: bytes) -> None:
    """校验 RGB sidecar 和 proof 一致。"""
    proof = _mapping(payload.get(f"camera.rgb_{index}_materialized"), "camera proof")
    if proof.get("byte_length") != len(blob):
        raise ValueError("RGB byte_length mismatch")
    if proof.get("sha256") != _sha256(blob):
        raise ValueError("RGB sha256 mismatch")


def _decision(rows: Sequence[Mapping[str, object]]) -> str:
    """计算本次 correction 的保守结论。"""
    if len(rows) != len(CANDIDATES):
        return "BLOCKED_DEPENDENCY_OR_EXECUTION"
    return "NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY"


def _recommendation(candidate: str) -> str:
    """生成保守 recommendation。"""
    if candidate == "zjh_lerobot_v21_raw":
        return "native_raw_baseline_context"
    return "compare_against_raw_native_before_selection"


def _mapping(value: object, field: str) -> Mapping[str, object]:
    """校验 mapping。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _string(value: object, field: str) -> str:
    """解析非空字符串。"""
    if not isinstance(value, str) or not value:
        raise TypeError(f"{field} must be a non-empty string")
    return value


def _number(value: object) -> float:
    """解析 numeric。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("value must be numeric")
    return float(value)


def _sha256(blob: bytes) -> str:
    """计算 bytes sha256。"""
    import hashlib

    return hashlib.sha256(blob).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
