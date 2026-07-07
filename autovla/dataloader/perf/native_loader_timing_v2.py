"""Native-loader timing report v2 的数据侧实现。"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import resource
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence, cast

SCHEMA_VERSION = "autovla.native_loader_timing_report_v2.v1"
PAYLOAD_SCHEMA_VERSION = "autovla.native_loader_timing_payload_v2.v1"
WORKING_ROOT_NAME = "autovla_native_loader_timing_v2"
CAMERA_STREAMS = (
    "observation.images.left_wrist_rgb",
    "observation.images.head_rgb",
    "observation.images.right_wrist_rgb",
)
RUN_CANDIDATES = (
    "zjh_lerobot_v21_raw",
    "webdataset_converted",
    "robodm_style_converted",
)
NOT_RUN_CANDIDATES = {
    "lerobot_v3_converted": (
        "NOT_RUN_DEPENDENCY_BLOCKED",
        "official LeRobot v3 dependency/conversion route is not separately approved",
    ),
    "zarr_converted": (
        "NOT_RUN_DEPENDENCY_BLOCKED",
        "actual Zarr dependency/version decision is missing",
    ),
}
TIMING_CANDIDATE_IDS = (
    "zjh_lerobot_v21_raw",
    "lerobot_v3_converted",
    "webdataset_converted",
    "robodm_style_converted",
    "zarr_converted",
)
CORE_TIMING_FIELDS = (
    "candidate",
    "native_loader",
    "worker_count",
    "batch_size",
    "sample_count",
    "episode_count",
    "repeats",
    "warmup_batches",
    "measured_batches",
    "first_batch_latency_ms",
    "p50_batch_latency_ms",
    "p95_batch_latency_ms",
    "max_batch_latency_ms",
    "total_measured_time_s",
    "samples_per_second",
    "frames_per_second",
    "batches_per_second",
    "conversion_time_s",
    "generated_artifact_size_gb",
    "generated_file_count",
    "rss_mb",
    "missing_metrics",
)
PLACEHOLDER_VALUES = {"", "missing", "not_recorded", "null", "unknown"}


@dataclass(frozen=True)
class FfmpegToolInfo:
    """记录 ffmpeg/ffprobe 的路径和版本。"""

    ffmpeg_path: Path
    ffmpeg_version: str
    ffprobe_path: Path
    ffprobe_version: str

    def to_json_dict(self) -> dict[str, object]:
        """返回 JSON-safe 工具证据。"""
        return {
            "ffmpeg_path": self.ffmpeg_path.as_posix(),
            "ffmpeg_version": self.ffmpeg_version,
            "ffprobe_path": self.ffprobe_path.as_posix(),
            "ffprobe_version": self.ffprobe_version,
        }


@dataclass(frozen=True)
class FrameRequest:
    """描述一次 source video 到 RGB frame 的请求。"""

    frame_index: int
    height: int
    sample_id: str
    stream_key: str
    timestamp_s: float
    video_path: Path
    width: int


@dataclass(frozen=True)
class FrameMaterialization:
    """保存一次 RGB frame stdout 物化结果。"""

    byte_length: int
    dtype: str
    height: int
    rgb_bytes: bytes
    sha256: str
    width: int

    def proof(self) -> dict[str, object]:
        """返回不携带原始图像字节的可审计 proof。"""
        digest = self.sha256 or hashlib.sha256(self.rgb_bytes).hexdigest()
        return {
            "byte_length": self.byte_length,
            "dtype": self.dtype,
            "shape": [self.height, self.width, 3],
            "sha256": digest,
        }


@dataclass(frozen=True)
class NativeLoaderTimingV2Config:
    """保存 native-loader timing v2 的输入配置。"""

    source_dataset: Path
    working_root: Path
    output_dir: Path
    worker_count: int
    batch_size: int
    max_episodes: int
    max_samples: int
    repeats: int
    warmup_batches: int
    measured_batches: int
    candidates: tuple[str, ...] = TIMING_CANDIDATE_IDS
    ffmpeg_tools: FfmpegToolInfo | None = None

    def __post_init__(self) -> None:
        """校验路径和 bounded 参数。"""
        if self.worker_count != 8:
            raise ValueError("native-loader timing v2 requires worker_count=8")
        for field_name in (
            "batch_size",
            "max_episodes",
            "max_samples",
            "repeats",
            "measured_batches",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")
        if self.warmup_batches < 0:
            raise ValueError("warmup_batches must be non-negative")
        unknown = set(self.candidates) - set(TIMING_CANDIDATE_IDS)
        if unknown:
            raise ValueError(f"unknown timing candidates: {sorted(unknown)}")
        source = self.source_dataset.resolve()
        working = self.working_root.resolve()
        if working == source or source in working.parents:
            raise ValueError("working_root must not be inside source dataset")
        if self.output_dir.resolve() == source or source in self.output_dir.resolve().parents:
            raise ValueError("output_dir must not be inside source dataset")


@dataclass(frozen=True)
class NativeLoaderTimingV2Result:
    """返回 timing report v2 的主要输出位置和行。"""

    conclusion: str
    generated_artifact_ledger: Path
    output_dir: Path
    report_path: Path
    rows: tuple[dict[str, object], ...]
    working_root: Path


FrameMaterializer = Callable[[FrameRequest], FrameMaterialization]
ArtifactBatchReader = Callable[[Sequence[int]], list[dict[str, object]]]


def discover_ffmpeg_tools(
    *,
    ffmpeg_path: Path = Path("/usr/bin/ffmpeg"),
    ffprobe_path: Path = Path("/usr/bin/ffprobe"),
) -> FfmpegToolInfo:
    """发现系统 ffmpeg/ffprobe, 缺失时 fail closed。"""
    for path, name in ((ffmpeg_path, "ffmpeg"), (ffprobe_path, "ffprobe")):
        if not path.is_file():
            raise FileNotFoundError(f"{name} is required at {path}")
    return FfmpegToolInfo(
        ffmpeg_path=ffmpeg_path,
        ffmpeg_version=_tool_version(ffmpeg_path),
        ffprobe_path=ffprobe_path,
        ffprobe_version=_tool_version(ffprobe_path),
    )


def build_ffmpeg_rgb_frame_argv(
    *,
    ffmpeg_path: Path,
    video_path: Path,
    timestamp_s: float,
    width: int,
    height: int,
) -> list[str]:
    """构造只向 stdout 写 raw RGB 的 ffmpeg argv。"""
    return [
        ffmpeg_path.as_posix(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{timestamp_s:.6f}",
        "-i",
        video_path.as_posix(),
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:{height}:flags=neighbor",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]


def resolve_source_video_path(source_root: Path, value: str) -> Path:
    """把相对视频路径限制在 source dataset root 内。"""
    if not value or value.strip() != value:
        raise ValueError("source video path must be a non-empty normalized relative path")
    lowered = value.lower()
    if "://" in lowered or lowered.startswith("pipe:") or lowered.startswith("pipe="):
        raise ValueError("source video path must not be URL or pipe")
    raw_path = Path(value)
    if raw_path.is_absolute():
        raise ValueError("source video path must be relative")
    root = source_root.resolve()
    candidate = (root / raw_path).resolve(strict=False)
    if candidate != root and root not in candidate.parents:
        raise ValueError("source video path escapes source dataset root")
    if not candidate.is_file():
        raise ValueError(f"source video file does not exist: {candidate}")
    return candidate


def materialize_frame_with_ffmpeg(
    request: FrameRequest,
    *,
    tools: FfmpegToolInfo,
    timeout_s: float = 30.0,
) -> FrameMaterialization:
    """用 ffmpeg stdout 物化一帧 RGB, 不写图像或视频文件。"""
    argv = build_ffmpeg_rgb_frame_argv(
        ffmpeg_path=tools.ffmpeg_path,
        height=request.height,
        timestamp_s=request.timestamp_s,
        video_path=request.video_path,
        width=request.width,
    )
    completed = subprocess.run(
        argv,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_s,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg frame materialization failed: {stderr}")
    expected_bytes = request.width * request.height * 3
    if len(completed.stdout) != expected_bytes:
        raise ValueError(
            f"ffmpeg returned {len(completed.stdout)} bytes, expected {expected_bytes}"
        )
    return FrameMaterialization(
        byte_length=len(completed.stdout),
        dtype="uint8",
        height=request.height,
        rgb_bytes=completed.stdout,
        sha256=hashlib.sha256(completed.stdout).hexdigest(),
        width=request.width,
    )


def run_native_loader_timing_v2(
    config: NativeLoaderTimingV2Config,
    *,
    frame_materializer: FrameMaterializer | None = None,
) -> NativeLoaderTimingV2Result:
    """生成 V2 native-loader timing 输出, 真正大规模执行留给 Compute/HPC。"""
    tools = config.ffmpeg_tools or discover_ffmpeg_tools()
    if frame_materializer is None:

        def _default_materializer(request: FrameRequest) -> FrameMaterialization:
            """默认通过 ffmpeg 物化 RGB frame。"""
            return materialize_frame_with_ffmpeg(request, tools=tools)

        materializer: FrameMaterializer = _default_materializer
    else:
        materializer = frame_materializer
    config.working_root.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    source_rows = _read_source_rows(config)
    rows: list[dict[str, object]] = []
    for candidate in config.candidates:
        if candidate in RUN_CANDIDATES:
            rows.append(
                _run_materialized_candidate(
                    candidate=candidate,
                    config=config,
                    materializer=materializer,
                    source_rows=source_rows,
                    tools=tools,
                )
            )
        else:
            rows.append(_write_not_run_candidate(candidate=candidate, config=config, tools=tools))
    ledger_path = _write_generated_artifact_ledger(config=config)
    report_path = _write_report(config=config, rows=rows, tools=tools)
    return NativeLoaderTimingV2Result(
        conclusion="READY_FOR_COMPUTE_EXECUTION",
        generated_artifact_ledger=ledger_path,
        output_dir=config.output_dir,
        report_path=report_path,
        rows=tuple(rows),
        working_root=config.working_root,
    )


def validate_materialized_payload(payload: Mapping[str, object]) -> None:
    """验证 RUN payload 不含 stream/path-only RGB 替代品。"""
    required = ("action", "language", "state", "action_mask", "deterministic_payload_hash")
    for field in required:
        if payload.get(field) in (None, "", []):
            raise ValueError(f"{field} is required")
    if payload.get("payload_missing_fields") not in ([], ()):
        raise ValueError("payload_missing_fields must be [] for RUN rows")
    for index in range(3):
        materialized_key = f"camera.rgb_{index}_materialized"
        legacy_key = f"camera.rgb_{index}"
        if legacy_key in payload and materialized_key not in payload:
            raise ValueError(f"{materialized_key} is required; stream refs are invalid")
        proof = _mapping(payload.get(materialized_key), materialized_key)
        shape = _int_list(proof.get("shape"), materialized_key)
        if len(shape) != 3 or shape[2] != 3:
            raise ValueError(f"{materialized_key} must have RGB shape [H,W,3]")
        byte_length = _positive_int(proof.get("byte_length"), f"{materialized_key}.byte_length")
        if byte_length != shape[0] * shape[1] * shape[2]:
            raise ValueError(f"{materialized_key} byte_length does not match shape")
        if proof.get("dtype") != "uint8":
            raise ValueError(f"{materialized_key} dtype must be uint8")
        if not isinstance(proof.get("sha256"), str) or not proof["sha256"]:
            raise ValueError(f"{materialized_key} sha256 is required")


def validate_core_timing_row(row: Mapping[str, object]) -> None:
    """验证 RUN timing row 的核心字段均为具体值。"""
    for field in CORE_TIMING_FIELDS:
        if field not in row:
            raise ValueError(f"{field} is required")
        value = row[field]
        if value is None:
            raise ValueError(f"{field} must be concrete")
        if isinstance(value, str) and value in PLACEHOLDER_VALUES:
            raise ValueError(f"{field} must be concrete")
    if row.get("missing_metrics") != []:
        raise ValueError("missing_metrics must be []")
    numeric_fields = tuple(
        field
        for field in CORE_TIMING_FIELDS
        if field not in {"candidate", "native_loader", "missing_metrics"}
    )
    for field in numeric_fields:
        value = row[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be numeric")
        if not math.isfinite(float(value)):
            raise ValueError(f"{field} must be finite")
    p50 = _float(row.get("p50_batch_latency_ms"), "p50_batch_latency_ms")
    p95 = _float(row.get("p95_batch_latency_ms"), "p95_batch_latency_ms")
    max_latency = _float(row.get("max_batch_latency_ms"), "max_batch_latency_ms")
    if p95 < p50:
        raise ValueError("p95_batch_latency_ms must be >= p50_batch_latency_ms")
    if max_latency < p95:
        raise ValueError("max_batch_latency_ms must be >= p95_batch_latency_ms")


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口, 供后续 Compute/HPC wave 调用。"""
    parser = argparse.ArgumentParser(description="AutoVLA native-loader timing report v2")
    parser.add_argument("--source-dataset", required=True, type=Path)
    parser.add_argument("--working-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--worker-count", default=8, type=int)
    parser.add_argument("--batch-size", default=8, type=int)
    parser.add_argument("--max-episodes", default=4, type=int)
    parser.add_argument("--max-samples", default=512, type=int)
    parser.add_argument("--repeats", default=3, type=int)
    parser.add_argument("--warmup-batches", default=1, type=int)
    parser.add_argument("--measured-batches", default=8, type=int)
    parser.add_argument(
        "--candidate",
        action="append",
        choices=TIMING_CANDIDATE_IDS,
        dest="candidates",
    )
    args = parser.parse_args(argv)
    result = run_native_loader_timing_v2(
        NativeLoaderTimingV2Config(
            batch_size=int(args.batch_size),
            candidates=tuple(args.candidates or TIMING_CANDIDATE_IDS),
            max_episodes=int(args.max_episodes),
            max_samples=int(args.max_samples),
            measured_batches=int(args.measured_batches),
            output_dir=args.output_dir,
            repeats=int(args.repeats),
            source_dataset=args.source_dataset,
            warmup_batches=int(args.warmup_batches),
            worker_count=int(args.worker_count),
            working_root=args.working_root,
        )
    )
    print(result.report_path.as_posix())
    return 0


def _run_materialized_candidate(
    *,
    candidate: str,
    config: NativeLoaderTimingV2Config,
    materializer: FrameMaterializer,
    source_rows: Sequence[Mapping[str, object]],
    tools: FfmpegToolInfo,
) -> dict[str, object]:
    """执行一个 RUN candidate 的 bounded timing 和 evidence 写出。"""
    candidate_dir = config.working_root / candidate
    candidate_dir.mkdir(parents=True, exist_ok=True)
    conversion_started = time.perf_counter()
    _write_json(
        candidate_dir / "conversion_manifest.json",
        {
            "candidate": candidate,
            "external_effects": _external_effects(),
            "ffmpeg": tools.to_json_dict(),
            "generated_artifacts_tracked": False,
            "prototype_only": candidate == "robodm_style_converted",
            "schema_version": f"{SCHEMA_VERSION}.conversion_manifest",
            "source_dataset": config.source_dataset.as_posix(),
            "source_dataset_mutated": False,
        },
    )
    materialized_records = [
        _materialized_payload_with_blobs(
            candidate=candidate,
            materializer=materializer,
            row=row,
        )
        for row in source_rows
    ]
    materialized_rows = [payload for payload, _rgb_blobs in materialized_records]
    for payload in materialized_rows:
        validate_materialized_payload(payload)
    payload_path = candidate_dir / "materialized_payload_rows.jsonl"
    _write_jsonl(payload_path, materialized_rows)
    if candidate == "zjh_lerobot_v21_raw":
        conversion_time_s = 0.0
        timing = _time_source_candidate_batches(
            candidate=candidate,
            config=config,
            materializer=materializer,
            source_rows=source_rows,
        )
        timing_source = "source_parquet_ffmpeg"
    elif candidate == "webdataset_converted":
        shard_path = _write_webdataset_artifact(candidate_dir, materialized_records)
        conversion_time_s = _elapsed_s(conversion_started)
        timing = _time_artifact_candidate_batches(
            candidate=candidate,
            config=config,
            episode_count=_episode_count(source_rows),
            read_batch=lambda indices: _read_webdataset_batch(shard_path, indices),
            sample_count=len(materialized_rows),
        )
        timing_source = "converted_webdataset_artifact"
    else:
        index_path = _write_robodm_style_artifact(candidate_dir, materialized_records)
        conversion_time_s = _elapsed_s(conversion_started)
        timing = _time_artifact_candidate_batches(
            candidate=candidate,
            config=config,
            episode_count=_episode_count(source_rows),
            read_batch=lambda indices: _read_robodm_style_batch(candidate_dir, index_path, indices),
            sample_count=len(materialized_rows),
        )
        timing_source = "converted_robodm_style_artifact"
    artifact_stats = _artifact_stats(candidate_dir)
    row: dict[str, object] = {
        **timing,
        "candidate": candidate,
        "classification": "RUNNABLE_NOW",
        "conversion_time_s": conversion_time_s,
        "external_effects": _external_effects(),
        "ffmpeg": tools.to_json_dict(),
        "generated_artifact_size_gb": artifact_stats["size_gb"],
        "generated_file_count": artifact_stats["file_count"],
        "missing_metrics": list[str](),
        "native_loader": _native_loader_name(candidate),
        "payload_schema_version": PAYLOAD_SCHEMA_VERSION,
        "prototype_only": candidate == "robodm_style_converted",
        "source_dataset_mutated": False,
        "timing_source": timing_source,
    }
    validate_core_timing_row(row)
    _write_json(config.output_dir / f"{candidate}-timing-result.json", row)
    return row


def _write_not_run_candidate(
    *,
    candidate: str,
    config: NativeLoaderTimingV2Config,
    tools: FfmpegToolInfo,
) -> dict[str, object]:
    """写出未运行候选的依赖阻塞 reason。"""
    classification, reason = NOT_RUN_CANDIDATES[candidate]
    candidate_dir = config.working_root / candidate
    candidate_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "candidate": candidate,
        "classification": classification,
        "external_effects": _external_effects(),
        "ffmpeg": tools.to_json_dict(),
        "missing_metrics": ["candidate_not_run"],
        "not_run_reason": reason,
        "schema_version": f"{SCHEMA_VERSION}.not_run_reason",
    }
    _write_json(candidate_dir / "not_run_reason.json", payload)
    _write_json(config.output_dir / f"{candidate}-timing-result.json", payload)
    return payload


def _materialized_payload(
    *,
    candidate: str,
    materializer: FrameMaterializer,
    row: Mapping[str, object],
) -> dict[str, object]:
    """把 source row 转成只含 proof 的物化 payload。"""
    payload, _rgb_blobs = _materialized_payload_with_blobs(
        candidate=candidate,
        materializer=materializer,
        row=row,
    )
    return payload


def _materialized_payload_with_blobs(
    *,
    candidate: str,
    materializer: FrameMaterializer,
    row: Mapping[str, object],
) -> tuple[dict[str, object], tuple[bytes, bytes, bytes]]:
    """把 source row 转成 proof payload 和真实 RGB bytes。"""
    camera_payloads: dict[str, object] = {}
    rgb_blobs: list[bytes] = []
    for index, request in enumerate(cast(Sequence[FrameRequest], row["frame_requests"])):
        materialized = materializer(request)
        camera_payloads[f"camera.rgb_{index}_materialized"] = materialized.proof()
        rgb_blobs.append(materialized.rgb_bytes)
    payload: dict[str, object] = {
        "action": row["action"],
        "action_mask": row["action_mask"],
        **camera_payloads,
        "candidate": candidate,
        "episode_id": row["episode_id"],
        "frame_index": row["frame_index"],
        "language": row["language"],
        "payload_missing_fields": [],
        "sample_id": row["sample_id"],
        "source_backend": candidate,
        "state": row["state"],
        "timestamp": row["timestamp"],
        "window_id": row["window_id"],
    }
    payload["deterministic_payload_hash"] = _stable_hash(payload)
    if len(rgb_blobs) != 3:
        raise ValueError("exactly three RGB blobs are required")
    return payload, (rgb_blobs[0], rgb_blobs[1], rgb_blobs[2])


def _time_source_candidate_batches(
    *,
    candidate: str,
    config: NativeLoaderTimingV2Config,
    materializer: FrameMaterializer,
    source_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """对候选按 batch 物化 payload 并收集具体 timing 字段。"""
    measured_latencies: list[float] = []
    measured_samples = 0
    measured_started = time.perf_counter()
    total_batches = config.warmup_batches + config.repeats * config.measured_batches
    for batch_index in range(total_batches):
        batch = _batch_for_index(source_rows, batch_index=batch_index, batch_size=config.batch_size)
        started = time.perf_counter()
        for row in batch:
            _materialized_payload(candidate=candidate, materializer=materializer, row=row)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if batch_index >= config.warmup_batches:
            measured_latencies.append(round(elapsed_ms, 6))
            measured_samples += len(batch)
    total_measured_s = max(time.perf_counter() - measured_started, 0.000001)
    if not measured_latencies:
        raise ValueError("measured batch latencies are required")
    p50 = _percentile(measured_latencies, 50.0)
    p95 = _percentile(measured_latencies, 95.0)
    return {
        "batch_size": config.batch_size,
        "batches_per_second": round(len(measured_latencies) / total_measured_s, 6),
        "episode_count": _episode_count(source_rows),
        "first_batch_latency_ms": measured_latencies[0],
        "frames_per_second": round((measured_samples * 3) / total_measured_s, 6),
        "max_batch_latency_ms": round(max(measured_latencies), 6),
        "measured_batches": config.measured_batches,
        "p50_batch_latency_ms": round(p50, 6),
        "p95_batch_latency_ms": round(p95, 6),
        "repeats": config.repeats,
        "rss_mb": _rss_mb(),
        "sample_count": len(source_rows),
        "samples_per_second": round(measured_samples / total_measured_s, 6),
        "total_measured_time_s": round(total_measured_s, 6),
        "warmup_batches": config.warmup_batches,
        "worker_count": config.worker_count,
    }


def _time_artifact_candidate_batches(
    *,
    candidate: str,
    config: NativeLoaderTimingV2Config,
    episode_count: int,
    read_batch: ArtifactBatchReader,
    sample_count: int,
) -> dict[str, object]:
    """通过 converted artifact reader 计时, 不回读 source videos。"""
    measured_latencies: list[float] = []
    measured_samples = 0
    measured_started = time.perf_counter()
    total_batches = config.warmup_batches + config.repeats * config.measured_batches
    for batch_index in range(total_batches):
        indices = _batch_indices(
            sample_count, batch_index=batch_index, batch_size=config.batch_size
        )
        started = time.perf_counter()
        payloads = read_batch(indices)
        if len(payloads) != len(indices):
            raise ValueError(f"{candidate} artifact reader returned the wrong batch size")
        for payload in payloads:
            validate_materialized_payload(payload)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if batch_index >= config.warmup_batches:
            measured_latencies.append(round(elapsed_ms, 6))
            measured_samples += len(payloads)
    total_measured_s = max(time.perf_counter() - measured_started, 0.000001)
    if not measured_latencies:
        raise ValueError("measured batch latencies are required")
    p50 = _percentile(measured_latencies, 50.0)
    p95 = _percentile(measured_latencies, 95.0)
    return {
        "batch_size": config.batch_size,
        "batches_per_second": round(len(measured_latencies) / total_measured_s, 6),
        "episode_count": episode_count,
        "first_batch_latency_ms": measured_latencies[0],
        "frames_per_second": round((measured_samples * 3) / total_measured_s, 6),
        "max_batch_latency_ms": round(max(measured_latencies), 6),
        "measured_batches": config.measured_batches,
        "p50_batch_latency_ms": round(p50, 6),
        "p95_batch_latency_ms": round(p95, 6),
        "repeats": config.repeats,
        "rss_mb": _rss_mb(),
        "sample_count": sample_count,
        "samples_per_second": round(measured_samples / total_measured_s, 6),
        "total_measured_time_s": round(total_measured_s, 6),
        "warmup_batches": config.warmup_batches,
        "worker_count": config.worker_count,
    }


def _read_source_rows(config: NativeLoaderTimingV2Config) -> list[dict[str, object]]:
    """从 LeRobot-v2.1 parquet 和 metadata 读取 bounded source rows。"""
    metadata = _read_metadata(config.source_dataset)
    tasks = _read_tasks(config.source_dataset)
    cameras = _camera_specs(metadata)
    parquet_module = importlib.import_module("pyarrow.parquet")
    rows: list[dict[str, object]] = []
    episode_ids: set[int] = set()
    for parquet_path in sorted((config.source_dataset / "data").glob("chunk-*/*.parquet")):
        table = parquet_module.read_table(parquet_path)
        for raw in _iter_table_rows(table):
            episode_index = _int(raw.get("episode_index"), "episode_index")
            if episode_index not in episode_ids and len(episode_ids) >= config.max_episodes:
                continue
            episode_ids.add(episode_index)
            rows.append(
                _source_row(
                    cameras=cameras,
                    metadata=metadata,
                    raw=raw,
                    source_dataset=config.source_dataset,
                    tasks=tasks,
                )
            )
            if len(rows) >= config.max_samples:
                return rows
    if not rows:
        raise ValueError("native-loader timing v2 requires source parquet rows")
    return rows


def _source_row(
    *,
    cameras: Sequence[Mapping[str, object]],
    metadata: Mapping[str, object],
    raw: Mapping[str, object],
    source_dataset: Path,
    tasks: Mapping[int, str],
) -> dict[str, object]:
    """把 source parquet row 转成 frame request 载体。"""
    action = _float_list(raw.get("action"), "action")
    state = _float_list(raw.get("observation.state", raw.get("state")), "state")
    action_mask = _bool_list(raw.get("action_mask"), expected=len(action))
    sample_index = _int(raw.get("index"), "index")
    episode_index = _int(raw.get("episode_index"), "episode_index")
    frame_index = _int(raw.get("frame_index"), "frame_index")
    timestamp = _float(raw.get("timestamp"), "timestamp")
    task_index = _int(raw.get("task_index", 0), "task_index")
    language = _string(raw.get("language", tasks.get(task_index, "zjh task")), "language")
    sample_id = f"sample-{sample_index:09d}"
    episode_id = f"episode-{episode_index:06d}"
    requests = [
        _frame_request(
            camera=camera,
            episode_index=episode_index,
            frame_index=frame_index,
            metadata=metadata,
            sample_id=sample_id,
            source_dataset=source_dataset,
            timestamp=timestamp,
        )
        for camera in cameras
    ]
    return {
        "action": [action],
        "action_mask": [action_mask],
        "episode_id": episode_id,
        "frame_index": frame_index,
        "frame_requests": requests,
        "language": language,
        "sample_id": sample_id,
        "state": state,
        "timestamp": timestamp,
        "window_id": f"{episode_id}:{sample_id}:{frame_index}",
    }


def _frame_request(
    *,
    camera: Mapping[str, object],
    episode_index: int,
    frame_index: int,
    metadata: Mapping[str, object],
    sample_id: str,
    source_dataset: Path,
    timestamp: float,
) -> FrameRequest:
    """从 metadata template 解析单路视频帧请求。"""
    stream_key = _string(camera.get("stream_key"), "stream_key")
    template = _string(metadata.get("video_path"), "video_path")
    relative_video = template.format(
        episode_chunk=episode_index // 1000,
        episode_index=episode_index,
        video_key=stream_key,
    )
    return FrameRequest(
        frame_index=frame_index,
        height=_positive_int(camera.get("height"), "camera height"),
        sample_id=sample_id,
        stream_key=stream_key,
        timestamp_s=timestamp,
        video_path=resolve_source_video_path(source_dataset, relative_video),
        width=_positive_int(camera.get("width"), "camera width"),
    )


def _camera_specs(metadata: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    """从 metadata features 提取三路 RGB 相机规格。"""
    features = _mapping(metadata.get("features"), "features")
    specs: list[dict[str, object]] = []
    for stream in CAMERA_STREAMS:
        feature = _mapping(features.get(stream), stream)
        info = _mapping(feature.get("video_info", feature.get("info", {})), "video_info")
        specs.append(
            {
                "height": _positive_int(
                    info.get("video.height", feature.get("height", 0)),
                    f"{stream}.height",
                ),
                "stream_key": stream,
                "width": _positive_int(
                    info.get("video.width", feature.get("width", 0)),
                    f"{stream}.width",
                ),
            }
        )
    return tuple(specs)


def _read_metadata(root: Path) -> dict[str, object]:
    """读取 LeRobot metadata/info。"""
    for relative in ("metadata.json", "meta/info.json"):
        path = root / relative
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise TypeError(f"{relative} must contain a JSON object")
            return cast(dict[str, object], loaded)
    raise FileNotFoundError("metadata.json or meta/info.json is required")


def _read_tasks(root: Path) -> dict[int, str]:
    """读取 task_index 到语言文本的映射。"""
    path = root / "meta" / "tasks.jsonl"
    if not path.is_file():
        return {}
    tasks: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        loaded_obj: object = json.loads(line)
        if isinstance(loaded_obj, Mapping):
            loaded = cast(Mapping[str, object], loaded_obj)
            tasks[_int(loaded.get("task_index", len(tasks)), "task_index")] = _string(
                loaded.get("task", "zjh task"),
                "task",
            )
    return tasks


def _iter_table_rows(table: Any) -> list[dict[str, object]]:
    """把 pyarrow Table 转成 JSON-safe rows。"""
    names = list(table.column_names)
    columns = {name: table[name].to_pylist() for name in names}
    rows: list[dict[str, object]] = []
    for index in range(int(table.num_rows)):
        rows.append({name: _json_safe(columns[name][index]) for name in names})
    return rows


def _batch_for_index(
    rows: Sequence[Mapping[str, object]],
    *,
    batch_index: int,
    batch_size: int,
) -> Sequence[Mapping[str, object]]:
    """返回循环取样 batch, 确保短 fixture 也能稳定测量。"""
    if not rows:
        raise ValueError("rows are required")
    indices = _batch_indices(len(rows), batch_index=batch_index, batch_size=batch_size)
    return [rows[index] for index in indices]


def _batch_indices(row_count: int, *, batch_index: int, batch_size: int) -> list[int]:
    """返回循环取样 batch indices。"""
    if row_count <= 0:
        raise ValueError("row_count must be positive")
    start = (batch_index * batch_size) % row_count
    return [(start + offset) % row_count for offset in range(batch_size)]


def _write_webdataset_artifact(
    candidate_dir: Path,
    records: Sequence[tuple[dict[str, object], tuple[bytes, bytes, bytes]]],
) -> Path:
    """用 WebDataset package 写出 converted tar sample payloads。"""
    wds_module: Any = importlib.import_module("webdataset")
    shard_dir = candidate_dir / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    shard_path = shard_dir / "shard-000000.tar"
    with wds_module.TarWriter(shard_path.as_posix(), mtime=0) as sink:
        for payload, rgb_blobs in records:
            sample_id = _string(payload.get("sample_id"), "sample_id")
            sink.write(
                {
                    "__key__": sample_id,
                    "payload.json": json.dumps(payload, sort_keys=True).encode("utf-8"),
                    "rgb0.bin": rgb_blobs[0],
                    "rgb1.bin": rgb_blobs[1],
                    "rgb2.bin": rgb_blobs[2],
                }
            )
    _write_json(
        candidate_dir / "sidecar_fields.json",
        {
            "backend": "webdataset_converted",
            "dependency_mode": "webdataset_package",
            "payload_files": ["payload.json", "rgb0.bin", "rgb1.bin", "rgb2.bin"],
            "schema_version": f"{SCHEMA_VERSION}.webdataset_artifact",
            "shard": shard_path.relative_to(candidate_dir).as_posix(),
        },
    )
    return shard_path


def _read_webdataset_batch(shard_path: Path, indices: Sequence[int]) -> list[dict[str, object]]:
    """通过 WebDataset streaming reader 读取 batch payloads。"""
    wds_module: Any = importlib.import_module("webdataset")
    needed = set(indices)
    selected: dict[int, dict[str, object]] = {}
    for position, sample_obj in enumerate(
        wds_module.WebDataset(shard_path.as_posix(), shardshuffle=False)
    ):
        if position not in needed:
            continue
        sample = _mapping(sample_obj, "webdataset sample")
        selected[position] = _payload_from_webdataset_sample(sample)
        if len(selected) == len(needed):
            break
    missing = needed - set(selected)
    if missing:
        raise ValueError(f"webdataset artifact is missing positions: {sorted(missing)}")
    return [selected[index] for index in indices]


def _payload_from_webdataset_sample(sample: Mapping[str, object]) -> dict[str, object]:
    """从 WebDataset sample 还原 payload 并校验 RGB bytes。"""
    payload_bytes = _bytes(sample.get("payload.json"), "payload.json")
    loaded: object = json.loads(payload_bytes.decode("utf-8"))
    payload = dict(_mapping(loaded, "payload.json"))
    for index in range(3):
        blob = _bytes(sample.get(f"rgb{index}.bin"), f"rgb{index}.bin")
        _verify_rgb_blob(payload, index=index, blob=blob)
    validate_materialized_payload(payload)
    return payload


def _write_robodm_style_artifact(
    candidate_dir: Path,
    records: Sequence[tuple[dict[str, object], tuple[bytes, bytes, bytes]]],
) -> Path:
    """写出 AutoVLA owned RoboDM-style prototype artifact。"""
    payload_dir = candidate_dir / "payloads"
    payload_dir.mkdir(parents=True, exist_ok=True)
    index_rows: list[dict[str, object]] = []
    for position, (payload, rgb_blobs) in enumerate(records):
        sample_id = _string(payload.get("sample_id"), "sample_id")
        rgb_paths: list[str] = []
        for camera_index, blob in enumerate(rgb_blobs):
            rgb_path = payload_dir / f"{sample_id}.rgb{camera_index}.bin"
            rgb_path.write_bytes(blob)
            rgb_paths.append(rgb_path.relative_to(candidate_dir).as_posix())
        index_rows.append(
            {
                "payload": payload,
                "position": position,
                "rgb_paths": rgb_paths,
                "schema_version": f"{SCHEMA_VERSION}.robodm_style_sample",
            }
        )
    index_path = candidate_dir / "sample_index.jsonl"
    _write_jsonl(index_path, index_rows)
    _write_json(
        candidate_dir / "loader_contract.json",
        {
            "backend": "robodm_style_converted",
            "dependency_mode": "autovla_owned_prototype",
            "prototype_only": True,
            "schema_version": f"{SCHEMA_VERSION}.robodm_style_artifact",
        },
    )
    return index_path


def _read_robodm_style_batch(
    candidate_dir: Path,
    index_path: Path,
    indices: Sequence[int],
) -> list[dict[str, object]]:
    """从 owned JSONL index 和 RGB sidecar files 读取 batch payloads。"""
    index_rows = _read_jsonl_objects(index_path)
    payloads: list[dict[str, object]] = []
    for index in indices:
        row = _mapping(index_rows[index], "robodm index row")
        payload = dict(_mapping(row.get("payload"), "payload"))
        rgb_paths = _string_list(row.get("rgb_paths"), "rgb_paths")
        if len(rgb_paths) != 3:
            raise ValueError("robodm_style artifact requires three RGB payload paths")
        for camera_index, relative in enumerate(rgb_paths):
            blob_path = _resolve_candidate_relative(candidate_dir, relative)
            _verify_rgb_blob(payload, index=camera_index, blob=blob_path.read_bytes())
        validate_materialized_payload(payload)
        payloads.append(payload)
    return payloads


def _read_jsonl_objects(path: Path) -> list[object]:
    """读取 JSONL objects。"""
    rows: list[object] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _resolve_candidate_relative(candidate_dir: Path, relative: str) -> Path:
    """把 artifact 内相对路径限制在 candidate_dir 内。"""
    if not relative or relative.strip() != relative:
        raise ValueError("artifact relative path must be normalized")
    lowered = relative.lower()
    if "://" in lowered or lowered.startswith("pipe:") or lowered.startswith("pipe="):
        raise ValueError("artifact relative path must not be URL or pipe")
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError("artifact relative path must not be absolute")
    resolved = (candidate_dir / candidate).resolve()
    root = candidate_dir.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("artifact relative path escapes candidate_dir")
    return resolved


def _verify_rgb_blob(payload: Mapping[str, object], *, index: int, blob: bytes) -> None:
    """校验 artifact 中读取的 RGB bytes 与 payload proof 一致。"""
    proof = _mapping(payload.get(f"camera.rgb_{index}_materialized"), "camera proof")
    byte_length = _positive_int(proof.get("byte_length"), "camera byte_length")
    if len(blob) != byte_length:
        raise ValueError("RGB blob byte_length does not match payload proof")
    sha256 = _string(proof.get("sha256"), "camera sha256")
    if hashlib.sha256(blob).hexdigest() != sha256:
        raise ValueError("RGB blob sha256 does not match payload proof")


def _write_report(
    *,
    config: NativeLoaderTimingV2Config,
    rows: Sequence[Mapping[str, object]],
    tools: FfmpegToolInfo,
) -> Path:
    """写出 task-local Markdown timing report。"""
    report_path = config.output_dir / "native-loader-timing-report-v2.md"
    lines = [
        "# Native Loader Timing Report V2",
        "",
        f"- Source dataset: `{config.source_dataset.as_posix()}`",
        f"- Working root: `{config.working_root.as_posix()}`",
        f"- ffmpeg: `{tools.ffmpeg_path}`",
        f"- ffprobe: `{tools.ffprobe_path}`",
        "- Fine-tune/training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: not used.",
        "",
        "| Candidate | Classification | Native loader | Samples | p50 ms | p95 ms | Missing |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"`{row['candidate']}` | "
            f"`{row['classification']}` | "
            f"`{row.get('native_loader', 'not_run')}` | "
            f"`{row.get('sample_count', 'not_run')}` | "
            f"`{row.get('p50_batch_latency_ms', 'not_run')}` | "
            f"`{row.get('p95_batch_latency_ms', 'not_run')}` | "
            f"`{row.get('missing_metrics', [])}` |"
        )
    lines.extend(
        [
            "",
            "Compute/HPC still owns the real source-dataset timing run. This report surface is "
            "generated by the login-node-safe implementation harness.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def _write_generated_artifact_ledger(*, config: NativeLoaderTimingV2Config) -> Path:
    """写出 generated artifact ledger, 只记录 working root 下文件。"""
    entries: list[dict[str, object]] = []
    for path in sorted(config.working_root.rglob("*")):
        if path.is_file():
            entries.append(
                {
                    "candidate": _candidate_from_path(config.working_root, path),
                    "checksum_manifest": path.name == "checksums.json",
                    "created_by": "autovla.dataloader.perf.native_loader_timing_v2",
                    "file_count": 1,
                    "path": path.as_posix(),
                    "safe_to_delete_later": True,
                    "size_bytes": path.stat().st_size,
                    "tracked_status": "ignored_generated_artifact",
                }
            )
    payload = {
        "entries": entries,
        "generated_artifacts_tracked": False,
        "schema_version": f"{SCHEMA_VERSION}.generated_artifact_ledger",
        "source_dataset_mutated": False,
    }
    path = config.output_dir / "generated-artifact-ledger.json"
    _write_json(path, payload)
    return path


def _candidate_from_path(root: Path, path: Path) -> str:
    """从 working root 相对路径提取 candidate id。"""
    try:
        return path.relative_to(root).parts[0]
    except (IndexError, ValueError):
        return "unknown"


def _artifact_stats(path: Path) -> dict[str, object]:
    """统计 candidate generated artifact 大小和文件数。"""
    total = 0
    count = 0
    for child in path.rglob("*"):
        if child.is_file():
            count += 1
            total += child.stat().st_size
    return {"file_count": count, "size_gb": round(total / 1_000_000_000.0, 9)}


def _native_loader_name(candidate: str) -> str:
    """返回候选 native loader 名称。"""
    return {
        "robodm_style_converted": "autovla_owned_robodm_style_rgb_materialized_reader",
        "webdataset_converted": "webdataset_rgb_materialized_streaming_reader",
        "zjh_lerobot_v21_raw": "raw_zjh_lerobot_v21_ffmpeg_materialized_reader",
    }[candidate]


def _external_effects() -> dict[str, bool]:
    """返回硬边界外部副作用。"""
    return {
        "checkpoint_read": False,
        "endpoint": False,
        "hf_network": False,
        "model_load": False,
        "real_training": False,
        "robot": False,
        "tokenizer_load": False,
        "wandb": False,
    }


def _tool_version(path: Path) -> str:
    """读取工具版本第一行。"""
    completed = subprocess.run(
        [path.as_posix(), "-version"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10.0,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{path} -version failed: {completed.stderr.strip()}")
    first_line = completed.stdout.splitlines()[0] if completed.stdout.splitlines() else ""
    if not first_line:
        raise RuntimeError(f"{path} did not report a version")
    return first_line


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    """写出稳定 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    """写出稳定 JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _elapsed_s(started: float) -> float:
    """返回秒级耗时。"""
    return round(time.perf_counter() - started, 6)


def _percentile(values: Sequence[float], percentile: float) -> float:
    """计算小样本线性插值 percentile。"""
    if not values:
        raise ValueError("percentile requires values")
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _rss_mb() -> float:
    """读取当前进程最大 RSS, Linux 单位为 KB。"""
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 6)


def _episode_count(rows: Sequence[Mapping[str, object]]) -> int:
    """统计 bounded rows 的 episode 数。"""
    return len({_string(row.get("episode_id"), "episode_id") for row in rows})


def _stable_hash(payload: Mapping[str, object]) -> str:
    """计算 JSON-safe payload 哈希。"""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def artifact_stats(path: Path) -> dict[str, object]:
    """为 fair rerun 暴露 generated artifact 统计。"""
    return _artifact_stats(path)


def episode_count(rows: Sequence[Mapping[str, object]]) -> int:
    """为 fair rerun 暴露 bounded episode 计数。"""
    return _episode_count(rows)


def external_effects() -> dict[str, bool]:
    """为 fair rerun 暴露外部副作用证明。"""
    return _external_effects()


def materialized_payload_with_blobs(
    *,
    candidate: str,
    materializer: FrameMaterializer,
    row: Mapping[str, object],
) -> tuple[dict[str, object], tuple[bytes, bytes, bytes]]:
    """为 fair rerun 暴露 proof payload 和真实 RGB bytes。"""
    return _materialized_payload_with_blobs(
        candidate=candidate,
        materializer=materializer,
        row=row,
    )


def read_robodm_style_batch(
    candidate_dir: Path,
    index_path: Path,
    indices: Sequence[int],
) -> list[dict[str, object]]:
    """为 fair rerun 暴露 RoboDM-style artifact reader。"""
    return _read_robodm_style_batch(candidate_dir, index_path, indices)


def read_source_rows(config: NativeLoaderTimingV2Config) -> list[dict[str, object]]:
    """为 fair rerun 暴露 bounded source row 读取。"""
    return _read_source_rows(config)


def read_webdataset_batch(shard_path: Path, indices: Sequence[int]) -> list[dict[str, object]]:
    """为 fair rerun 暴露 WebDataset artifact reader。"""
    return _read_webdataset_batch(shard_path, indices)


def stable_hash(payload: Mapping[str, object]) -> str:
    """为 fair rerun 暴露稳定 JSON 哈希。"""
    return _stable_hash(payload)


def time_artifact_candidate_batches(
    *,
    candidate: str,
    config: NativeLoaderTimingV2Config,
    episode_count: int,
    read_batch: ArtifactBatchReader,
    sample_count: int,
) -> dict[str, object]:
    """为 fair rerun 暴露 artifact reader timing。"""
    return _time_artifact_candidate_batches(
        candidate=candidate,
        config=config,
        episode_count=episode_count,
        read_batch=read_batch,
        sample_count=sample_count,
    )


def time_source_candidate_batches(
    *,
    candidate: str,
    config: NativeLoaderTimingV2Config,
    materializer: FrameMaterializer,
    source_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """为 fair rerun 暴露 source native-loader timing。"""
    return _time_source_candidate_batches(
        candidate=candidate,
        config=config,
        materializer=materializer,
        source_rows=source_rows,
    )


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    """为 fair rerun 暴露稳定 JSON 写入。"""
    _write_json(path, payload)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    """为 fair rerun 暴露稳定 JSONL 写入。"""
    _write_jsonl(path, rows)


def write_robodm_style_artifact(
    candidate_dir: Path,
    records: Sequence[tuple[dict[str, object], tuple[bytes, bytes, bytes]]],
) -> Path:
    """为 fair rerun 暴露 RoboDM-style artifact builder。"""
    return _write_robodm_style_artifact(candidate_dir, records)


def write_webdataset_artifact(
    candidate_dir: Path,
    records: Sequence[tuple[dict[str, object], tuple[bytes, bytes, bytes]]],
) -> Path:
    """为 fair rerun 暴露 WebDataset artifact builder。"""
    return _write_webdataset_artifact(candidate_dir, records)


def _json_safe(value: object) -> object:
    """把 pyarrow/numpy 标量递归转换成 JSON-safe 值。"""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _json_safe(item) for key, item in mapping.items()}
    if isinstance(value, (list, tuple)):
        sequence = cast(Sequence[object], value)
        return [_json_safe(item) for item in sequence]
    if hasattr(value, "as_py"):
        scalar = cast(Any, value)
        return _json_safe(scalar.as_py())
    return value


def _mapping(value: object, field: str) -> Mapping[str, object]:
    """校验 mapping。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _int(value: object, field: str) -> int:
    """解析 int, 避免 bool 混入。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    return value


def _positive_int(value: object, field: str) -> int:
    """解析正整数。"""
    parsed = _int(value, field)
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _float(value: object, field: str) -> float:
    """解析 finite float。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{field} must be finite")
    return parsed


def _string(value: object, field: str) -> str:
    """解析非空字符串。"""
    if not isinstance(value, str) or not value:
        raise TypeError(f"{field} must be a non-empty string")
    return value


def _bytes(value: object, field: str) -> bytes:
    """解析 bytes。"""
    if not isinstance(value, bytes):
        raise TypeError(f"{field} must be bytes")
    return value


def _string_list(value: object, field: str) -> list[str]:
    """解析字符串列表。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{field} must be a sequence")
    sequence = cast(Sequence[object], value)
    return [_string(item, field) for item in sequence]


def _float_list(value: object, field: str) -> list[float]:
    """解析 float list。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{field} must be a sequence")
    sequence = cast(Sequence[object], value)
    return [_float(item, field) for item in sequence]


def _bool_list(value: object, *, expected: int) -> list[bool]:
    """解析 action_mask, 缺失时按 action 维度推导。"""
    if value is None:
        return [True for _ in range(expected)]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError("action_mask must be a sequence")
    sequence = cast(Sequence[object], value)
    parsed = [bool(item) for item in sequence]
    if len(parsed) != expected:
        raise ValueError("action_mask length must match action")
    return parsed


def _int_list(value: object, field: str) -> list[int]:
    """解析整数列表。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{field} shape must be a sequence")
    sequence = cast(Sequence[object], value)
    return [_int(item, field) for item in sequence]


if __name__ == "__main__":  # pragma: no cover - CLI 入口由 Compute/HPC 调用
    raise SystemExit(main())
