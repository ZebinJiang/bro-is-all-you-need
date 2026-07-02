"""Native-loader timing v2 合同测试。"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Mapping, cast

import pytest

from autovla.dataloader.perf.native_loader_timing_v2 import (
    FfmpegToolInfo,
    FrameMaterialization,
    FrameRequest,
    NativeLoaderTimingV2Config,
    build_ffmpeg_rgb_frame_argv,
    resolve_source_video_path,
    run_native_loader_timing_v2,
    validate_core_timing_row,
    validate_materialized_payload,
)


def test_timing_v2_should_emit_three_materialized_run_rows(tmp_path: Path) -> None:
    """验证三个 RUN 候选都必须产出物化 RGB payload 和具体 timing 字段。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "tiny_zjh", sample_count=8)
    working_root = tmp_path / "datasets" / "working" / "autovla_native_loader_timing_v2"
    output_dir = tmp_path / "runs" / "tmp" / "native-loader-v2"

    result = run_native_loader_timing_v2(
        NativeLoaderTimingV2Config(
            source_dataset=source_dataset,
            working_root=working_root,
            output_dir=output_dir,
            worker_count=8,
            batch_size=2,
            max_episodes=4,
            max_samples=8,
            repeats=2,
            warmup_batches=1,
            measured_batches=2,
            ffmpeg_tools=_fake_tools(),
        ),
        frame_materializer=_fake_materializer,
    )

    assert result.conclusion == "READY_FOR_COMPUTE_EXECUTION"
    assert (output_dir / "native-loader-timing-report-v2.md").is_file()
    assert (output_dir / "generated-artifact-ledger.json").is_file()

    by_candidate = {row["candidate"]: row for row in result.rows}
    assert set(by_candidate) == {
        "zjh_lerobot_v21_raw",
        "lerobot_v3_converted",
        "webdataset_converted",
        "robodm_style_converted",
        "zarr_converted",
    }
    for candidate in (
        "zjh_lerobot_v21_raw",
        "webdataset_converted",
        "robodm_style_converted",
    ):
        row = by_candidate[candidate]
        assert row["classification"] == "RUNNABLE_NOW"
        assert row["missing_metrics"] == []
        assert row["worker_count"] == 8
        assert _number(row, "conversion_time_s") >= 0.0
        assert _number(row, "first_batch_latency_ms") >= 0.0
        assert _number(row, "p50_batch_latency_ms") >= 0.0
        assert _number(row, "p95_batch_latency_ms") >= _number(row, "p50_batch_latency_ms")
        assert _number(row, "samples_per_second") > 0.0
        assert _number(row, "frames_per_second") > 0.0
        assert _number(row, "batches_per_second") > 0.0
        assert _number(row, "generated_artifact_size_gb") >= 0.0
        assert _number(row, "generated_file_count") >= 1.0

        candidate_dir = working_root / candidate
        payload = _read_jsonl_first(candidate_dir / "materialized_payload_rows.jsonl")
        assert payload["payload_missing_fields"] == []
        assert payload["action"]
        assert payload["language"]
        assert payload["state"]
        assert payload["action_mask"]
        for camera_key in (
            "camera.rgb_0_materialized",
            "camera.rgb_1_materialized",
            "camera.rgb_2_materialized",
        ):
            proof = cast(Mapping[str, object], payload[camera_key])
            assert proof["dtype"] == "uint8"
            assert proof["shape"] == [2, 2, 3]
            assert proof["byte_length"] == 12
            assert proof["sha256"]
        assert payload["deterministic_payload_hash"]
        validate_materialized_payload(payload)
        validate_core_timing_row(row)

    assert by_candidate["robodm_style_converted"]["prototype_only"] is True
    assert by_candidate["lerobot_v3_converted"]["classification"] == "NOT_RUN_DEPENDENCY_BLOCKED"
    assert by_candidate["zarr_converted"]["classification"] == "NOT_RUN_DEPENDENCY_BLOCKED"


def test_converted_candidates_should_time_from_artifacts_without_materializer(
    tmp_path: Path,
) -> None:
    """验证 converted 候选的 measured timing 不再回读 source 视频。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "tiny_zjh", sample_count=8)
    working_root = tmp_path / "datasets" / "working" / "autovla_native_loader_timing_v2"
    output_dir = tmp_path / "runs" / "tmp" / "native-loader-v2"
    materializer_calls = 0

    def _counting_materializer(request: FrameRequest) -> FrameMaterialization:
        nonlocal materializer_calls
        materializer_calls += 1
        return _fake_materializer(request)

    result = run_native_loader_timing_v2(
        NativeLoaderTimingV2Config(
            source_dataset=source_dataset,
            working_root=working_root,
            output_dir=output_dir,
            worker_count=8,
            batch_size=2,
            max_episodes=4,
            max_samples=8,
            repeats=2,
            warmup_batches=1,
            measured_batches=2,
            ffmpeg_tools=_fake_tools(),
        ),
        frame_materializer=_counting_materializer,
    )

    raw_conversion_calls = 8 * 3
    raw_timing_calls = (1 + 2 * 2) * 2 * 3
    webdataset_conversion_calls = 8 * 3
    robodm_conversion_calls = 8 * 3
    assert materializer_calls == (
        raw_conversion_calls
        + raw_timing_calls
        + webdataset_conversion_calls
        + robodm_conversion_calls
    )

    by_candidate = {row["candidate"]: row for row in result.rows}
    assert by_candidate["zjh_lerobot_v21_raw"]["timing_source"] == "source_parquet_ffmpeg"
    assert by_candidate["webdataset_converted"]["timing_source"] == "converted_webdataset_artifact"
    assert (
        by_candidate["robodm_style_converted"]["timing_source"] == "converted_robodm_style_artifact"
    )
    assert (working_root / "webdataset_converted" / "shards" / "shard-000000.tar").is_file()
    assert (working_root / "robodm_style_converted" / "sample_index.jsonl").is_file()


def test_timing_v2_should_reject_stream_ref_payloads() -> None:
    """验证 RUN payload 不能用 stream/path 引用冒充物化 RGB。"""
    payload: dict[str, object] = {
        "action": [[1.0, 2.0, 3.0]],
        "action_mask": [[True, True, True]],
        "camera.rgb_0": {"decode": "deferred"},
        "camera.rgb_1_materialized": {"byte_length": 12, "dtype": "uint8", "shape": [2, 2, 3]},
        "camera.rgb_2_materialized": {"byte_length": 12, "dtype": "uint8", "shape": [2, 2, 3]},
        "deterministic_payload_hash": "abc",
        "language": "tiny task",
        "payload_missing_fields": [],
        "state": [0.0, 1.0, 2.0],
    }

    with pytest.raises(ValueError, match=r"camera\.rgb_0_materialized"):
        validate_materialized_payload(payload)


def test_timing_v2_should_reject_bad_core_timing_fields() -> None:
    """验证 timing 字段不能是 missing、not_recorded 或非空 missing_metrics。"""
    row: dict[str, object] = {
        "batch_size": 2,
        "batches_per_second": 1.0,
        "candidate": "zjh_lerobot_v21_raw",
        "conversion_time_s": 0.0,
        "episode_count": 4,
        "first_batch_latency_ms": "not_recorded",
        "frames_per_second": 8.0,
        "generated_artifact_size_gb": 0.0,
        "generated_file_count": 1,
        "max_batch_latency_ms": 1.0,
        "measured_batches": 2,
        "missing_metrics": [],
        "native_loader": "raw_zjh_lerobot_v21_ffmpeg",
        "p50_batch_latency_ms": 1.0,
        "p95_batch_latency_ms": 1.0,
        "repeats": 2,
        "rss_mb": 128.0,
        "sample_count": 8,
        "samples_per_second": 8.0,
        "total_measured_time_s": 1.0,
        "warmup_batches": 1,
        "worker_count": 8,
    }

    with pytest.raises(ValueError, match="first_batch_latency_ms"):
        validate_core_timing_row(row)
    row["first_batch_latency_ms"] = 1.0
    row["missing_metrics"] = ["rss_mb"]
    with pytest.raises(ValueError, match="missing_metrics"):
        validate_core_timing_row(row)


def test_timing_v2_should_reject_uncontained_video_paths(tmp_path: Path) -> None:
    """验证视频路径必须保持在 readonly source root 内。"""
    root = tmp_path / "dataset"
    root.mkdir()
    safe = root / "videos" / "chunk-000" / "camera" / "episode_000000.mp4"
    safe.parent.mkdir(parents=True)
    safe.write_bytes(b"fake")

    assert resolve_source_video_path(root, "videos/chunk-000/camera/episode_000000.mp4") == safe

    for value in (
        "../outside.mp4",
        "https://example.invalid/video.mp4",
        "pipe:cat /etc/passwd",
        "/etc/passwd",
    ):
        with pytest.raises(ValueError):
            resolve_source_video_path(root, value)


def test_timing_v2_should_build_ffmpeg_argv_without_shell(tmp_path: Path) -> None:
    """验证 ffmpeg frame materializer 只暴露 argv list, 不需要 shell 拼接。"""
    video_path = tmp_path / "episode.mp4"
    video_path.write_bytes(b"fake")

    argv = build_ffmpeg_rgb_frame_argv(
        ffmpeg_path=Path("/usr/bin/ffmpeg"),
        video_path=video_path,
        timestamp_s=0.25,
        width=2,
        height=2,
    )

    assert isinstance(argv, list)
    assert argv[0] == "/usr/bin/ffmpeg"
    assert "shell=True" not in " ".join(argv)
    assert "pipe:1" in argv
    assert "-f" in argv
    assert "rawvideo" in argv


def _fake_tools() -> FfmpegToolInfo:
    """构造不调用系统命令的工具发现结果。"""
    return FfmpegToolInfo(
        ffmpeg_path=Path("/usr/bin/ffmpeg"),
        ffmpeg_version="ffmpeg version 4.4.2-test",
        ffprobe_path=Path("/usr/bin/ffprobe"),
        ffprobe_version="ffprobe version 4.4.2-test",
    )


def _fake_materializer(request: FrameRequest) -> FrameMaterialization:
    """用确定性字节模拟 ffmpeg stdout RGB 结果。"""
    seed = f"{request.stream_key}:{request.frame_index}".encode("utf-8")
    raw = (seed * 8)[:12]
    return FrameMaterialization(
        byte_length=len(raw),
        dtype="uint8",
        height=2,
        rgb_bytes=raw,
        sha256="",
        width=2,
    )


def _tiny_zjh_fixture(root: Path, *, sample_count: int) -> Path:
    """写入带三路视频文件占位的 tiny LeRobot-v2.1 fixture。"""
    pa: Any = importlib.import_module("pyarrow")
    pq: Any = importlib.import_module("pyarrow.parquet")

    data_dir = root / "data" / "chunk-000"
    data_dir.mkdir(parents=True)
    cameras = (
        "observation.images.left_wrist_rgb",
        "observation.images.head_rgb",
        "observation.images.right_wrist_rgb",
    )
    for camera in cameras:
        video_path = root / "videos" / "chunk-000" / camera / "episode_000000.mp4"
        video_path.parent.mkdir(parents=True)
        video_path.write_bytes(b"fake video placeholder")

    metadata = {
        "codebase_version": "v2.1",
        "features": {
            "action": {"dtype": "float32", "shape": [3]},
            "observation.state": {"dtype": "float32", "shape": [3]},
            **{
                camera: {
                    "dtype": "video",
                    "shape": [2, 2, 3],
                    "video_info": {
                        "video.codec": "h264",
                        "video.fps": 30,
                        "video.height": 2,
                        "video.pix_fmt": "yuv420p",
                        "video.width": 2,
                    },
                }
                for camera in cameras
            },
        },
        "fps": 30,
        "total_episodes": 1,
        "total_frames": sample_count,
        "total_videos": 3,
        "video_path": (
            "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4"
        ),
    }
    (root / "metadata.json").write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    (root / "meta").mkdir()
    (root / "meta" / "tasks.jsonl").write_text(
        json.dumps({"task_index": 0, "task": "tiny timing task"}) + "\n",
        encoding="utf-8",
    )

    schema = pa.schema(
        [
            pa.field("index", pa.int64(), nullable=False),
            pa.field("episode_index", pa.int64(), nullable=False),
            pa.field("frame_index", pa.int64(), nullable=False),
            pa.field("timestamp", pa.float64(), nullable=False),
            pa.field("task_index", pa.int64(), nullable=False),
            pa.field("observation.state", pa.list_(pa.float32(), 3), nullable=False),
            pa.field("action", pa.list_(pa.float32(), 3), nullable=False),
            pa.field("action_mask", pa.list_(pa.bool_(), 3), nullable=False),
            pa.field("language", pa.string(), nullable=False),
        ]
    )
    columns: dict[str, Any] = {
        "index": list(range(sample_count)),
        "episode_index": [0 for _ in range(sample_count)],
        "frame_index": list(range(sample_count)),
        "timestamp": [float(index) / 30.0 for index in range(sample_count)],
        "task_index": [0 for _ in range(sample_count)],
        "observation.state": [[float(index), 1.0, 2.0] for index in range(sample_count)],
        "action": [[float(index), 0.0, 1.0] for index in range(sample_count)],
        "action_mask": [[True, True, False] for _ in range(sample_count)],
        "language": ["tiny timing task" for _ in range(sample_count)],
    }
    arrays = [pa.array(columns[name], type=schema.field(name).type) for name in schema.names]
    table = pa.Table.from_arrays(arrays, schema=schema)
    pq.write_table(table, data_dir / "file-000.parquet")
    return root


def _read_jsonl_first(path: Path) -> dict[str, object]:
    """读取 JSONL 第一行。"""
    line = path.read_text(encoding="utf-8").splitlines()[0]
    loaded: object = json.loads(line)
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def _number(row: Mapping[str, object], key: str) -> float:
    """读取测试用 numeric 字段。"""
    value = row[key]
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    return float(value)
