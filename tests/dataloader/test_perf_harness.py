"""AutoVLA DataLoader 性能 Harness 测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from autovla.dataloader.perf.benchmark import run_benchmark
from autovla.dataloader.perf.config import (
    BenchmarkMode,
    PerfBenchmarkConfig,
    load_perf_benchmark_config,
)
from autovla.dataloader.perf.metrics import PerfMetrics, percentile
from autovla.dataloader.perf.profiler import parse_nvidia_smi_csv
from autovla.dataloader.perf.report import (
    build_fast_training_view_schema,
    classify_perf_report,
    write_baseline_comparison_report,
)


def _video_feature() -> dict[str, object]:
    """构造 tiny video metadata。"""
    return {
        "dtype": "video",
        "info": {
            "has_audio": False,
            "video.channels": 3,
            "video.codec": "h264",
            "video.fps": 30,
            "video.height": 16,
            "video.pix_fmt": "yuv420p",
            "video.width": 16,
        },
        "names": None,
        "shape": [16, 16, 3],
        "video_info": {
            "video.codec": "h264",
            "video.height": 16,
            "video.pix_fmt": "yuv420p",
            "video.width": 16,
        },
    }


def _tiny_info() -> dict[str, object]:
    """构造 LeRobot-v2-compatible tiny metadata。"""
    return {
        "chunks_size": 1000,
        "codebase_version": "v2.1",
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "features": {
            "action": {"dtype": "float32", "names": ["left_x", "right_x"], "shape": [2]},
            "episode_index": {"dtype": "int64", "names": None, "shape": [1]},
            "frame_index": {"dtype": "int64", "names": None, "shape": [1]},
            "index": {"dtype": "int64", "names": None, "shape": [1]},
            "is_first": {"dtype": "bool", "names": None, "shape": [1]},
            "is_last": {"dtype": "bool", "names": None, "shape": [1]},
            "is_terminal": {"dtype": "bool", "names": None, "shape": [1]},
            "observation.images.head_rgb": _video_feature(),
            "observation.images.left_wrist_rgb": _video_feature(),
            "observation.images.right_wrist_rgb": _video_feature(),
            "observation.state": {
                "dtype": "float32",
                "names": ["joint_a", "joint_b"],
                "shape": [2],
            },
            "task_index": {"dtype": "int64", "names": None, "shape": [1]},
            "timestamp": {"dtype": "float32", "names": None, "shape": [1]},
        },
        "fps": 30,
        "robot_type": "demo_bot",
        "splits": {"train": "0:2"},
        "total_chunks": 1,
        "total_episodes": 2,
        "total_frames": 4,
        "total_tasks": 1,
        "total_videos": 6,
        "video_path": (
            "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4"
        ),
    }


def _write_tiny_zjh_metadata(root: Path) -> None:
    """只写 tiny metadata/info/tasks, 不写 parquet 或媒体。"""
    (root / "meta").mkdir(parents=True)
    encoded = json.dumps(_tiny_info(), sort_keys=True)
    (root / "metadata.json").write_text(encoded, encoding="utf-8")
    (root / "meta" / "info.json").write_text(encoded, encoding="utf-8")
    (root / "meta" / "tasks.jsonl").write_text(
        json.dumps({"task_index": 0, "task": "pick the tiny object"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _config(tmp_path: Path, *, mode: BenchmarkMode = "metadata-only") -> PerfBenchmarkConfig:
    """构造默认 perf benchmark 配置。"""
    dataset = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset)
    return PerfBenchmarkConfig(
        adapter="zjh-adapter",
        dataset=dataset,
        output_dir=tmp_path / "perf-output",
        max_episodes=4,
        max_samples=512,
        mode=mode,
    )


def test_perf_config_should_roundtrip_and_validate_output_dir(tmp_path: Path) -> None:
    """验证配置 JSON 往返和输出目录安全边界。"""
    config = _config(tmp_path)
    config_path = tmp_path / "config.json"
    config.write_json(config_path)

    loaded = load_perf_benchmark_config(config_path)

    assert loaded == config
    with pytest.raises(ValueError, match="dataset root"):
        PerfBenchmarkConfig(
            adapter="zjh-adapter",
            dataset=config.dataset,
            output_dir=config.dataset / "inside",
            max_episodes=1,
            max_samples=1,
            mode="metadata-only",
        )


def test_perf_config_should_reject_invalid_fields(tmp_path: Path) -> None:
    """验证配置字段错误明确指向字段名。"""
    dataset = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset)

    with pytest.raises(ValueError, match="adapter"):
        PerfBenchmarkConfig(
            adapter="",
            dataset=dataset,
            output_dir=tmp_path / "out",
            max_episodes=1,
            max_samples=1,
            mode="metadata-only",
        )
    with pytest.raises(ValueError, match="max_samples"):
        PerfBenchmarkConfig(
            adapter="zjh-adapter",
            dataset=dataset,
            output_dir=tmp_path / "out",
            max_episodes=1,
            max_samples=0,
            mode="metadata-only",
        )
    with pytest.raises(ValueError, match="mode"):
        PerfBenchmarkConfig(
            adapter="zjh-adapter",
            dataset=dataset,
            output_dir=tmp_path / "out",
            max_episodes=1,
            max_samples=1,
            mode=cast(BenchmarkMode, "full-conversion"),
        )


def test_metrics_should_roundtrip_percentiles_and_missing_metrics() -> None:
    """验证 metrics schema、p50/p95 和缺失指标显式记录。"""
    metrics = PerfMetrics.from_latencies(
        samples=8,
        episodes=2,
        batch_latencies_ms=[10.0, 20.0, 30.0, 40.0],
        adapter_inspect_time_ms=5.0,
        index_build_time_ms=2.0,
        media_decode_time_ms=0.0,
        transform_time_ms=0.0,
        tokenization_time_ms=0.0,
        collate_time_ms=1.0,
        compute_placeholder_time_ms=10.0,
        missing_metrics=("gpu_util_pct", "hbm_bw_pct"),
    )
    payload = metrics.to_json_dict()

    assert percentile([10.0, 20.0, 30.0, 40.0], 50.0) == 25.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 95.0) == 38.5
    assert payload["batch_latency_ms_p50"] == 25.0
    assert payload["batch_latency_ms_p95"] == 38.5
    assert set(cast(list[str], payload["missing_metrics"])) >= {"gpu_util_pct", "hbm_bw_pct"}
    assert PerfMetrics.from_json_dict(payload).to_json_dict() == payload


def test_classification_should_warn_and_fail_on_data_wait() -> None:
    """验证 data wait 规则会给出 WARN/FAIL。"""
    warning_metrics = PerfMetrics.from_latencies(
        samples=4,
        episodes=1,
        batch_latencies_ms=[20.0],
        data_wait_time_ms=15.0,
        compute_placeholder_time_ms=20.0,
        missing_metrics=("gpu_util_pct",),
    )
    failing_metrics = PerfMetrics.from_latencies(
        samples=4,
        episodes=1,
        batch_latencies_ms=[20.0],
        data_wait_time_ms=80.0,
        compute_placeholder_time_ms=20.0,
        media_decode_time_ms=45.0,
    )

    assert classify_perf_report(warning_metrics).classification == "WARN"
    assert classify_perf_report(failing_metrics).classification == "FAIL"
    assert "predecode" in "\n".join(classify_perf_report(failing_metrics).recommendations)


def test_metadata_only_benchmark_should_write_bounded_reports(tmp_path: Path) -> None:
    """验证 metadata-only benchmark 只读 tiny metadata 并写出稳定报告。"""
    config = _config(tmp_path)

    result = run_benchmark(config, project_root=tmp_path)

    report = json.loads((config.output_dir / "perf_report.json").read_text(encoding="utf-8"))
    dataset_summary = json.loads(
        (config.output_dir / "dataset_probe_summary.json").read_text(encoding="utf-8")
    )
    environment = json.loads((config.output_dir / "environment.json").read_text(encoding="utf-8"))

    assert result.classification.classification in {"PASS", "WARN", "INSUFFICIENT_TELEMETRY"}
    assert report["config"]["mode"] == "metadata-only"
    assert report["metrics"]["samples_per_second"] >= 0.0
    assert dataset_summary["sample_count"] == 4
    assert dataset_summary["episode_count"] == 2
    assert dataset_summary["row_level_scan"] is False
    assert dataset_summary["media_decode"] is False
    assert environment["external_effects"] == {
        "checkpoint_read": False,
        "dataset_write": False,
        "full_conversion": False,
        "hf_network": False,
        "model_load": False,
        "real_training": False,
        "slurm_submission": False,
        "wandb_network": False,
    }
    assert not (config.dataset / "perf_report.json").exists()


def test_bounded_decode_should_require_compute_context(tmp_path: Path) -> None:
    """验证 bounded-decode 不允许在非 compute context 运行。"""
    config = _config(tmp_path, mode="bounded-decode")

    with pytest.raises(RuntimeError, match="compute node"):
        run_benchmark(config, project_root=tmp_path, compute_context=False)


def test_bounded_decode_should_read_tiny_media_bytes_in_compute_context(tmp_path: Path) -> None:
    """验证 bounded-decode 在 compute context 中执行有界媒体读取。"""
    config = _config(tmp_path, mode="bounded-decode")
    media_path = (
        config.dataset
        / "videos"
        / "chunk-000"
        / "observation.images.head_rgb"
        / "episode_000000.mp4"
    )
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"\x00" * 128)

    result = run_benchmark(config, project_root=tmp_path, compute_context=True)
    payload = json.loads((config.output_dir / "perf_report.json").read_text(encoding="utf-8"))
    metrics = cast(dict[str, object], payload["metrics"])
    summary = cast(dict[str, object], payload["dataset_probe_summary"])
    disk_read = metrics["disk_read_mb_s"]
    missing_metrics = metrics["missing_metrics"]

    assert result.metrics.media_decode_time_ms > 0.0
    assert isinstance(disk_read, float)
    assert disk_read > 0.0
    assert summary["media_files_read"] == 1
    assert isinstance(missing_metrics, list)
    assert "media_decode_time_ms" not in missing_metrics


def test_cli_should_run_metadata_only_and_reject_invalid_config(tmp_path: Path) -> None:
    """验证 python -m CLI 成功和失败路径。"""
    config = _config(tmp_path)
    config_path = tmp_path / "perf-config.json"
    config.write_json(config_path)

    success = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.dataloader.perf",
            "benchmark",
            "--config",
            str(config_path),
        ],
        check=False,
        cwd=Path.cwd(),
        env={**os.environ, "AUTOVLA_EXPECT_NO_REAL_TRAINING": "1"},
        text=True,
        capture_output=True,
    )
    bad_config = tmp_path / "bad.json"
    bad_config.write_text("{bad json", encoding="utf-8")
    failure = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.dataloader.perf",
            "benchmark",
            "--config",
            str(bad_config),
        ],
        check=False,
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
    )

    assert success.returncode == 0, success.stderr
    assert "perf_report.json" in success.stdout
    assert failure.returncode == 2
    assert "config" in failure.stderr


def test_gpu_telemetry_parser_should_mark_missing_and_parse_fixture() -> None:
    """验证 GPU telemetry 缺失和 nvidia-smi CSV fixture 解析。"""
    assert parse_nvidia_smi_csv("") == {
        "gpu_memory_used_mb": "missing",
        "gpu_util_pct": "missing",
        "hbm_bw_pct": "missing",
    }
    assert parse_nvidia_smi_csv("17, 2048, 33\n") == {
        "gpu_memory_used_mb": 2048.0,
        "gpu_util_pct": 17.0,
        "hbm_bw_pct": 33.0,
    }


def test_baseline_comparison_and_fast_training_view_schema(tmp_path: Path) -> None:
    """验证 baseline comparison 和 Fast Training View schema 输出。"""
    metrics = PerfMetrics.from_latencies(
        samples=4,
        episodes=1,
        batch_latencies_ms=[10.0],
        data_wait_time_ms=30.0,
        compute_placeholder_time_ms=10.0,
        missing_metrics=("gpu_util_pct",),
    )
    perf_payload = {
        "classification": classify_perf_report(metrics).to_json_dict(),
        "metrics": metrics.to_json_dict(),
    }
    baseline_summary: dict[str, object] = {
        "dataloader_waits": {"nonzero_count": 1, "max_seconds": 3.5, "p95_seconds": 3.5},
        "schema_version": "autovla.baseline_metrics.v1",
        "status": {"classification": "cancelled_partial"},
    }

    report_path = write_baseline_comparison_report(
        baseline_summary,
        perf_payload,
        tmp_path / "baseline-comparison-report.md",
    )
    schema = build_fast_training_view_schema()

    assert "cancelled_partial" in report_path.read_text(encoding="utf-8")
    assert "data_wait_time_ms" in report_path.read_text(encoding="utf-8")
    assert set(schema) >= {
        "deterministic_sampler_state",
        "episode_to_sample_index",
        "local_nvme_staging_manifest",
        "performance_counters_schema",
        "predecoded_frame_cache_policy",
        "pretokenized_language_policy",
        "sample_to_shard_index",
        "shard_manifest",
    }


def test_perf_docs_should_publish_required_sections() -> None:
    """验证 perf harness 文档包含要求章节和 anti-patterns。"""
    docs = [
        Path("autovla/dataloader/perf/MODULE.md"),
        Path("docs/architecture/DATALOADER_PERFORMANCE_HARNESS.md"),
        Path("docs/architecture/FAST_TRAINING_VIEW.md"),
        Path("docs/architecture/AI_NATIVE_VLA_INFRA.md"),
        Path("docs/architecture/ROADMAP.md"),
    ]
    required = (
        "purpose",
        "public contracts",
        "directory structure",
        "extension points",
        "invariants",
        "performance requirements",
        "anti-patterns",
    )

    for path in docs:
        text = path.read_text(encoding="utf-8").lower()
        for section in required:
            assert section in text, f"{path} missing {section}"
    module_text = docs[0].read_text(encoding="utf-8").lower()
    assert "running perf probes on login node" in module_text
    assert "training directly from slow interchange loader" in module_text
