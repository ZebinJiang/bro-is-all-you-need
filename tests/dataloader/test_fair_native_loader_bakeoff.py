"""PR30 fair native-loader correction tests。"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

from autovla.dataloader.perf.fair_native_loader_bakeoff import (
    CANDIDATES,
    REQUIRED_STAGE_COLUMNS,
    FairNativeLoaderBakeoffConfig,
    run_fair_native_loader_bakeoff,
    validate_benchmark_batch,
    validate_stage_timing_rows,
    validate_timing_row,
)
from autovla.dataloader.perf.native_loader_timing_v2 import (
    FfmpegToolInfo,
    FrameMaterialization,
    FrameRequest,
)


def test_fair_bakeoff_should_run_four_pr30_candidates_with_materialized_rgb(
    tmp_path: Path,
) -> None:
    """验证 PR30 correction 四候选都走 materialized native-loader 路径。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "tiny_zjh", sample_count=8)
    working_root = tmp_path / "datasets" / "working" / "autovla_fair_native_loader_bakeoff_v1"
    output_dir = tmp_path / "runs" / "tmp" / "fair-native-loader"

    result = run_fair_native_loader_bakeoff(
        FairNativeLoaderBakeoffConfig(
            batch_size=2,
            ffmpeg_tools=_fake_tools(),
            gr00t_root=tmp_path / "Isaac-GR00T17",
            max_episodes=4,
            max_samples=8,
            measured_batches=2,
            output_dir=output_dir,
            repeats=2,
            source_dataset=source_dataset,
            warmup_batches=1,
            worker_count=8,
            working_root=working_root,
        ),
        frame_materializer=_fake_materializer,
    )

    assert result.conclusion == "NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY"
    assert result.manifest_path.is_file()
    assert (working_root / "shared-sample-window-manifest.json").is_file()
    assert result.json_path.is_file()
    assert result.csv_path.is_file()
    assert result.markdown_path.is_file()
    assert result.ledger_path.is_file()

    by_candidate = {row["candidate"]: row for row in result.rows}
    assert set(by_candidate) == set(CANDIDATES)
    for candidate in CANDIDATES:
        row = by_candidate[candidate]
        assert row["worker_count"] == 8
        assert row["batch_size"] == 2
        assert row["payload_complete"] is True
        assert row["camera_payload_mode"] == "materialized_rgb"
        assert row["missing_metrics"] == []
        assert row["status"] == "RUNNABLE_NOW"
        assert _number(row, "p99_batch_latency_ms") >= _number(row, "p95_batch_latency_ms")
        validate_timing_row(row)

        candidate_dir = working_root / candidate
        assert (candidate_dir / "loader_contract.json").is_file()
        assert (candidate_dir / "payload_validation.json").is_file()
        assert (candidate_dir / "timing_result.json").is_file()
        assert (candidate_dir / "timing_result.csv").is_file()
        assert (candidate_dir / "timing_result.md").is_file()

    assert (working_root / "zjh_lerobot_v3_local" / "data" / "chunk-000").is_dir()
    assert (working_root / "zjh_webdataset_tar" / "shards" / "shard-000000.tar").is_file()
    assert (working_root / "zjh_robodm_container_v1" / "sample_index.jsonl").is_file()


def test_adapter_v1_should_emit_stage_profiles_and_summary_tables(tmp_path: Path) -> None:
    """验证 adapter-v1 审计输出包含完整 stage 表和保守决策。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "tiny_zjh", sample_count=8)
    working_root = tmp_path / "datasets" / "working" / "autovla_fair_native_loader_bakeoff_v2"
    output_dir = tmp_path / "runs" / "tmp" / "adapter-v1"

    result = run_fair_native_loader_bakeoff(
        FairNativeLoaderBakeoffConfig(
            adapter_version="adapter_v1",
            batch_size=2,
            ffmpeg_tools=_fake_tools(),
            gr00t_root=tmp_path / "Isaac-GR00T17",
            max_episodes=4,
            max_samples=8,
            measured_batches=2,
            output_dir=output_dir,
            repeats=2,
            source_dataset=source_dataset,
            warmup_batches=1,
            worker_count=8,
            working_root=working_root,
        ),
        frame_materializer=_fake_materializer,
    )

    assert result.stage_timing_v1_json_path.is_file()
    assert result.adapter_summary_json_path.is_file()
    assert result.adapter_bottleneck_json_path.is_file()
    assert result.backend_decision_status_path.is_file()

    stage_rows = json.loads(result.stage_timing_v1_json_path.read_text(encoding="utf-8"))["rows"]
    validate_stage_timing_rows(stage_rows)
    assert set(REQUIRED_STAGE_COLUMNS) <= set(stage_rows[0])
    assert all(row["adapter_version"] == "adapter_v1" for row in stage_rows)
    assert all(row["worker_count_label"] == "configured_8" for row in stage_rows)
    assert all(row["actual_worker_count"] == "not_measured" for row in stage_rows)
    assert all(row["total_ms"] != "" for row in stage_rows)
    assert any(
        row["candidate"] == "zjh_webdataset_tar"
        and row["stage"] == "reader_init"
        and row["cache_miss_count"] == 1
        for row in stage_rows
    )
    assert any(
        row["candidate"] == "zjh_webdataset_tar"
        and row["stage"] == "batch_read"
        and row["persistent_reader_enabled"] is True
        for row in stage_rows
    )
    assert any(
        row["candidate"] == "zjh_robodm_container_v1"
        and row["stage"] == "reader_init"
        and row["persistent_reader_enabled"] is True
        for row in stage_rows
    )
    assert any(
        row["candidate"] == "zjh_lerobot_v3_local"
        and row["stage"] == "reader_init"
        and row["cache_miss_count"] == 1
        for row in stage_rows
    )

    summary = json.loads(result.adapter_summary_json_path.read_text(encoding="utf-8"))
    assert summary["decision_status"] == "NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY"
    assert {row["candidate"] for row in summary["rows"]} == set(CANDIDATES)
    assert all(row["adapter_version"] == "adapter_v1" for row in summary["rows"])
    assert all(row["worker_count_label"] == "configured_8" for row in summary["rows"])
    assert all(row["actual_worker_count"] == "not_measured" for row in summary["rows"])
    webdataset_summary = next(
        row for row in summary["rows"] if row["candidate"] == "zjh_webdataset_tar"
    )
    assert webdataset_summary["p50_ms_v0_baseline"] == 224.916599
    assert webdataset_summary["p50_ms_v1"] != webdataset_summary["p50_ms_v0_baseline"]
    assert "improvement_ratio_samples_per_second" in webdataset_summary

    decision_text = result.backend_decision_status_path.read_text(encoding="utf-8")
    assert "No final backend winner is selected" in decision_text
    assert "adapter-v0 baseline" in decision_text


def test_fair_bakeoff_should_reject_camera_refs_only_payload() -> None:
    """验证 camera_refs 不能冒充三路 RGB payload。"""
    payload: dict[str, object] = {
        "action": [[1.0, 2.0, 3.0]],
        "action_mask": [[True, True, True]],
        "camera_refs": ["a.mp4", "b.mp4", "c.mp4"],
        "deterministic_payload_hash": "abc",
        "episode_id": "episode-000000",
        "language": "task",
        "payload_hash": "abc",
        "payload_missing_fields": [],
        "sample_id": "sample-000000001",
        "state": [0.0, 1.0, 2.0],
    }

    with pytest.raises(ValueError, match=r"camera\.rgb_0_materialized"):
        validate_benchmark_batch(payload)


def test_fair_bakeoff_should_reject_missing_core_timing_field() -> None:
    """验证 runnable timing row 不允许缺核心字段。"""
    row: dict[str, object] = {
        "batch_size": 2,
        "batches_per_second": 1.0,
        "camera_payload_mode": "materialized_rgb",
        "candidate": "zjh_lerobot_v21_raw",
        "conversion_time_s": 0.0,
        "cpu_system_pct": 0.0,
        "cpu_user_pct": 0.0,
        "episode_count": 1,
        "file_open_count": 1,
        "first_batch_latency_ms": 1.0,
        "frames_per_second": 6.0,
        "generated_artifact_size_gb": 0.0,
        "generated_file_count": 1,
        "loader_init_time_s": 0.0,
        "max_batch_latency_ms": 2.0,
        "measured_batches": 2,
        "missing_metrics": [],
        "native_loader": "autovla_lerobot_v21_native_ffmpeg_materialized_reader",
        "p50_batch_latency_ms": 1.0,
        "p95_batch_latency_ms": 2.0,
        "p99_batch_latency_ms": 2.0,
        "payload_complete": True,
        "read_mb_s": 0.0,
        "repeats": 2,
        "rss_mb": 128.0,
        "rss_mb_max": 128.0,
        "sample_count": 4,
        "samples_per_second": 4.0,
        "total_measured_time_s": 1.0,
        "warmup_batches": 1,
        "worker_count": 8,
    }
    validate_timing_row(row)
    row["first_batch_latency_ms"] = "not_recorded"
    with pytest.raises(ValueError, match="first_batch_latency_ms"):
        validate_timing_row(row)


def test_pr30_docs_should_mark_previous_multiformat_numbers_invalidated() -> None:
    """验证 PR 可见文档不再把旧数字当成 active winner/baseline。"""
    root = Path(__file__).resolve().parents[2]
    telemetry = (root / "docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md").read_text(
        encoding="utf-8"
    )
    readme = (root / "README.md").read_text(encoding="utf-8")
    audit = (root / "docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md").read_text(encoding="utf-8")
    v2 = (root / "docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md").read_text(encoding="utf-8")

    assert "PR #30 prior multiformat benchmark numbers are invalidated" in telemetry
    assert "preloaded `SourceSample` lookup" in telemetry
    assert "no final backend winner" in telemetry.lower()
    assert "PR #30 prior multiformat benchmark numbers are invalidated" in readme
    assert "adapter-v0 baseline" in audit
    assert "actual_worker_count=not_measured" in audit
    assert "NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY" in audit
    assert "does not run GPU200" in readme
    assert "worker_count_label: `configured_8`" in v2
    assert "actual_worker_count: `not_measured`" in v2


def test_fair_bakeoff_module_should_expose_cli_help() -> None:
    """验证 python -m 入口不会静默空跑。"""
    completed = subprocess.run(
        [sys.executable, "-m", "autovla.dataloader.perf.fair_native_loader_bakeoff", "--help"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert completed.returncode == 0
    assert "--source-dataset" in completed.stdout


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


def _number(row: Mapping[str, object], key: str) -> float:
    """读取测试用 numeric 字段。"""
    value = row[key]
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    return float(value)
