"""AutoVLA DataLoader 性能 Harness 测试。"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from autovla.dataloader.perf import training_store as training_store_module
from autovla.dataloader.perf.benchmark import run_benchmark
from autovla.dataloader.perf.config import (
    BenchmarkMode,
    BuildScope,
    PerfBenchmarkConfig,
    load_perf_benchmark_config,
)
from autovla.dataloader.perf.metrics import PerfMetrics, percentile
from autovla.dataloader.perf.profiler import parse_nvidia_smi_csv
from autovla.dataloader.perf.report import (
    build_fast_training_view_schema,
    classify_perf_report,
    classify_training_store_comparison,
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


def _write_tiny_zjh_parquet(root: Path) -> None:
    """写出 tiny source-derived parquet 行, 只用于单元测试。"""
    pa = cast(Any, importlib.import_module("pyarrow"))
    pq = cast(Any, importlib.import_module("pyarrow.parquet"))
    data_dir = root / "data" / "chunk-000"
    data_dir.mkdir(parents=True, exist_ok=True)
    for episode in range(2):
        start = episode * 2
        table = pa.table(
            {
                "action": [
                    [float(start), 0.25],
                    [float(start + 1), 0.5],
                ],
                "observation.state": [
                    [float(start), 1.25],
                    [float(start + 1), 1.5],
                ],
                "episode_index": [episode, episode],
                "frame_index": [0, 1],
                "index": [start, start + 1],
                "task_index": [0, 0],
                "observation.images.head_rgb": [
                    {"path": f"videos/head/{episode:06d}_0.mp4", "timestamp": 0.0},
                    {"path": f"videos/head/{episode:06d}_1.mp4", "timestamp": 1.0},
                ],
                "observation.images.left_wrist_rgb": [
                    {"path": f"videos/left/{episode:06d}_0.mp4", "timestamp": 0.0},
                    {"path": f"videos/left/{episode:06d}_1.mp4", "timestamp": 1.0},
                ],
                "observation.images.right_wrist_rgb": [
                    {"path": f"videos/right/{episode:06d}_0.mp4", "timestamp": 0.0},
                    {"path": f"videos/right/{episode:06d}_1.mp4", "timestamp": 1.0},
                ],
            }
        )
        pq.write_table(table, data_dir / f"episode_{episode:06d}.parquet")


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


def test_training_store_config_should_roundtrip_pfs_store_dir(tmp_path: Path) -> None:
    """验证 Training Store mode 和 PFS store 目录进入配置契约。"""
    dataset = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset)
    config = PerfBenchmarkConfig(
        adapter="zjh-adapter",
        dataset=dataset,
        output_dir=tmp_path / "perf-output",
        training_store_dir=tmp_path / "training-store",
        max_episodes=2,
        max_samples=4,
        mode="store-build-bounded",
    )
    config_path = tmp_path / "store-config.json"
    config.write_json(config_path)

    loaded = load_perf_benchmark_config(config_path)

    assert loaded == config
    assert loaded.to_json_dict()["training_store_dir"] == (tmp_path / "training-store").as_posix()
    with pytest.raises(ValueError, match="training_store_dir"):
        PerfBenchmarkConfig(
            adapter="zjh-adapter",
            dataset=dataset,
            output_dir=tmp_path / "perf-output",
            training_store_dir=dataset / "store",
            max_episodes=2,
            max_samples=4,
            mode="store-build-bounded",
        )


def test_persistent_training_store_config_should_roundtrip_build_scope(tmp_path: Path) -> None:
    """验证 persistent PFS mode 和 build_scope 进入配置契约。"""
    dataset = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset)
    config = PerfBenchmarkConfig(
        adapter="zjh-adapter",
        dataset=dataset,
        output_dir=tmp_path / "store-build-report",
        training_store_dir=tmp_path / "derived" / "zjh-demo",
        max_episodes=2,
        max_samples=4,
        mode="pfs-training-store-build",
        build_scope="full-or-budgeted",
    )
    config_path = tmp_path / "persistent-config.json"
    config.write_json(config_path)

    loaded = load_perf_benchmark_config(config_path)

    assert loaded == config
    assert loaded.to_json_dict()["build_scope"] == "full-or-budgeted"
    with pytest.raises(ValueError, match="build_scope"):
        PerfBenchmarkConfig(
            adapter="zjh-adapter",
            dataset=dataset,
            output_dir=tmp_path / "out",
            training_store_dir=tmp_path / "derived" / "zjh-demo",
            max_episodes=1,
            max_samples=1,
            mode="pfs-training-store-build",
            build_scope=cast(BuildScope, "unsafe"),
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
    assert "PFS-backed Training Store" in "\n".join(
        classify_perf_report(failing_metrics).recommendations
    )


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


def test_store_build_bounded_should_write_pfs_training_store(tmp_path: Path) -> None:
    """验证 bounded Training Store builder 写出 PFS v0 store 契约。"""
    base_config = _config(tmp_path)
    config = PerfBenchmarkConfig(
        adapter=base_config.adapter,
        dataset=base_config.dataset,
        output_dir=base_config.output_dir,
        training_store_dir=tmp_path / "training-store",
        max_episodes=base_config.max_episodes,
        max_samples=base_config.max_samples,
        mode="store-build-bounded",
    )

    result = run_benchmark(config, project_root=tmp_path)

    store_dir = cast(Path, config.training_store_dir)
    manifest = json.loads((store_dir / "training_store_manifest.json").read_text(encoding="utf-8"))
    build_report = json.loads((store_dir / "build_report.json").read_text(encoding="utf-8"))
    sample_rows = (store_dir / "sample_index.jsonl").read_text(encoding="utf-8").splitlines()
    first_sample = json.loads(sample_rows[0])
    shard_path = store_dir / "shards" / "shard-000000.npz"

    assert result.output_dir == config.output_dir
    assert manifest["storage_backend"] == "pfs_shared"
    assert manifest["local_stage_used"] is False
    assert manifest["store_format"] == "npz_jsonl_v0"
    assert manifest["sample_count"] == 4
    assert manifest["episode_count"] == 2
    assert manifest["external_effects"]["real_training"] is False
    assert (store_dir / "episode_index.jsonl").is_file()
    assert (store_dir / "stats" / "action_statistics.json").is_file()
    assert (store_dir / "checksums.json").is_file()
    assert build_report["full_dataset_conversion"] is False
    assert build_report["full_media_predecode"] is False
    assert first_sample["sample_id"] == "sample-000000"
    assert first_sample["episode_id"] == "episode-000000"
    assert first_sample["action_horizon"] == 1
    assert first_sample["action_dim"] == 2
    assert first_sample["action_mask_shape"] == [1, 2]
    assert first_sample["robot_tag"] == "demo_bot"
    assert first_sample["sample_source"]["source_format"] == "lerobot-v2-compatible"
    with np.load(shard_path) as shard:
        assert shard["actions"].shape == (4, 1, 2)
        assert shard["action_mask"].shape == (4, 1, 2)


def test_store_read_benchmark_should_compare_against_raw_decode(tmp_path: Path) -> None:
    """验证 Training Store read benchmark 输出 raw/store 对比指标。"""
    store_dir = tmp_path / "training-store"
    base_config = _config(tmp_path)
    build_config = PerfBenchmarkConfig(
        adapter=base_config.adapter,
        dataset=base_config.dataset,
        output_dir=tmp_path / "perf-build",
        training_store_dir=store_dir,
        max_episodes=base_config.max_episodes,
        max_samples=base_config.max_samples,
        mode="store-build-bounded",
    )
    run_benchmark(build_config, project_root=tmp_path)
    read_config = PerfBenchmarkConfig(
        adapter=build_config.adapter,
        dataset=build_config.dataset,
        output_dir=tmp_path / "perf-read",
        training_store_dir=store_dir,
        max_episodes=build_config.max_episodes,
        max_samples=build_config.max_samples,
        mode="store-read-benchmark",
    )

    result = run_benchmark(read_config, project_root=tmp_path)

    report = json.loads((store_dir / "read_benchmark_report.json").read_text(encoding="utf-8"))
    comparison = cast(dict[str, object], report["comparison"])
    store_p50 = comparison["training_store_batch_latency_ms_p50"]
    store_p95 = comparison["training_store_batch_latency_ms_p95"]
    file_open_count = comparison["pfs_file_open_count"]
    missing_telemetry = comparison["missing_telemetry"]
    assert result.classification.classification in {"PASS", "WARN", "INSUFFICIENT_TELEMETRY"}
    assert isinstance(store_p50, (float, int))
    assert isinstance(store_p95, (float, int))
    assert store_p50 >= 0.0
    assert store_p95 >= 0.0
    assert "raw_batch_latency_ms_p50" in comparison
    assert "raw_batch_latency_ms_p95" in comparison
    assert "speedup_vs_raw_decode" in comparison
    assert comparison["decode_avoided_ratio"] == 1.0
    assert isinstance(file_open_count, int)
    assert file_open_count >= 3
    assert isinstance(missing_telemetry, list)
    assert "gpu_util_pct" in missing_telemetry
    assert (read_config.output_dir / "perf_report.json").is_file()


def test_persistent_store_build_should_resolve_fingerprint_layout(tmp_path: Path) -> None:
    """验证 persistent builder 写入 fingerprinted derived path 和任务要求 layout。"""
    dataset = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset)
    _write_tiny_zjh_parquet(dataset)
    store_root = tmp_path / "datasets" / "derived" / "autovla_training_store" / "zjh-demo"
    build_config = PerfBenchmarkConfig(
        adapter="zjh-adapter",
        dataset=dataset,
        output_dir=tmp_path / "store-build-report",
        training_store_dir=store_root,
        max_episodes=2,
        max_samples=4,
        mode="pfs-training-store-build",
        build_scope="full-or-budgeted",
    )

    result = run_benchmark(build_config, project_root=tmp_path)

    resolved_path = (
        (build_config.output_dir / "resolved_store_path.txt").read_text(encoding="utf-8").strip()
    )
    resolved_store = Path(resolved_path)
    manifest = json.loads(
        (resolved_store / "training_store_manifest.json").read_text(encoding="utf-8")
    )
    build_report = json.loads(
        (resolved_store / "reports" / "build_report.json").read_text(encoding="utf-8")
    )
    checksums = json.loads((resolved_store / "checksums.json").read_text(encoding="utf-8"))
    sample_rows = (resolved_store / "sample_index.jsonl").read_text(encoding="utf-8").splitlines()
    first_sample = json.loads(sample_rows[0])

    assert result.output_dir == build_config.output_dir
    assert resolved_store.parent.parent == store_root
    assert resolved_store.parent.name == manifest["dataset_id"]
    assert manifest["storage_backend"] == "pfs_shared"
    assert manifest["local_stage_used"] is False
    assert manifest["build_scope"] == "full"
    assert manifest["store_status"] == "FULL_STORE_READY"
    assert manifest["dataset_name"] == manifest["dataset_id"]
    assert manifest["source_dataset"] == dataset.as_posix()
    assert manifest["statistics_plan_path"] == "statistics_plan.json"
    assert manifest["external_effects"]["real_training"] is False
    assert manifest["real_training"] is False
    assert manifest["model_loading"] is False
    assert manifest["dataset_source_modified"] is False
    assert manifest["sample_count"] == 4
    assert manifest["episode_count"] == 2
    assert build_report["classification"] == "FULL_STORE_READY"
    assert build_report["source_kind"] == "source_derived_parquet"
    assert (resolved_store / "statistics_plan.json").is_file()
    assert (resolved_store / "reports" / "read_benchmark_report.json").is_file()
    assert "statistics_plan" in checksums["files"]
    assert first_sample["sample_source"]["parquet_path"] == "data/chunk-000/episode_000000.parquet"
    assert first_sample["window_start"] == 0


def test_persistent_store_build_should_classify_budgeted_partial(tmp_path: Path) -> None:
    """验证 budgeted partial 不会被冒充为 full store ready。"""
    dataset = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset)
    _write_tiny_zjh_parquet(dataset)
    build_config = PerfBenchmarkConfig(
        adapter="zjh-adapter",
        dataset=dataset,
        output_dir=tmp_path / "store-build-report",
        training_store_dir=tmp_path / "derived" / "zjh-demo",
        max_episodes=1,
        max_samples=2,
        mode="pfs-training-store-build",
        build_scope="budgeted_partial",
    )

    run_benchmark(build_config, project_root=tmp_path)

    resolved_store = Path(
        (build_config.output_dir / "resolved_store_path.txt").read_text(encoding="utf-8").strip()
    )
    manifest = json.loads(
        (resolved_store / "training_store_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["build_scope"] == "budgeted_partial"
    assert manifest["store_status"] == "PARTIAL_STORE_READY_FOR_FORMAT_REVIEW"
    assert manifest["sample_count"] == 2
    assert manifest["episode_count"] == 1


def test_persistent_store_read_should_write_reports_layout(tmp_path: Path) -> None:
    """验证 persistent read benchmark 使用 resolved store 并写 reports/read。"""
    dataset = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset)
    _write_tiny_zjh_parquet(dataset)
    build_config = PerfBenchmarkConfig(
        adapter="zjh-adapter",
        dataset=dataset,
        output_dir=tmp_path / "store-build-report",
        training_store_dir=tmp_path / "derived" / "zjh-demo",
        max_episodes=2,
        max_samples=4,
        mode="pfs-training-store-build",
        build_scope="full-or-budgeted",
    )
    run_benchmark(build_config, project_root=tmp_path)
    resolved_store = Path(
        (build_config.output_dir / "resolved_store_path.txt").read_text(encoding="utf-8").strip()
    )
    read_config = PerfBenchmarkConfig(
        adapter=build_config.adapter,
        dataset=build_config.dataset,
        output_dir=tmp_path / "store-read-report",
        training_store_dir=resolved_store,
        max_episodes=2,
        max_samples=4,
        mode="pfs-training-store-read",
    )

    result = run_benchmark(read_config, project_root=tmp_path)

    read_report = json.loads(
        (resolved_store / "reports" / "read_benchmark_report.json").read_text(encoding="utf-8")
    )
    comparison = cast(dict[str, object], read_report["comparison"])
    assert result.output_dir == read_config.output_dir
    assert read_report["checksums_verified"] is True
    assert read_report["store_status"] == "FULL_STORE_READY"
    assert comparison["decode_avoided_ratio"] == 1.0
    assert "speedup_vs_raw_decode" in comparison
    assert (read_config.output_dir / "perf_report.json").is_file()


def test_persistent_store_read_should_only_open_needed_shards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 full store read benchmark 不会把全量 shard 当作 bounded hot path。"""
    monkeypatch.setattr(training_store_module, "TRAINING_STORE_SHARD_TARGET_SAMPLES", 2)
    dataset = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset)
    _write_tiny_zjh_parquet(dataset)
    build_config = PerfBenchmarkConfig(
        adapter="zjh-adapter",
        dataset=dataset,
        output_dir=tmp_path / "store-build-report",
        training_store_dir=tmp_path / "derived" / "zjh-demo",
        max_episodes=2,
        max_samples=4,
        mode="pfs-training-store-build",
        build_scope="full-or-budgeted",
    )
    run_benchmark(build_config, project_root=tmp_path)
    resolved_store = Path(
        (build_config.output_dir / "resolved_store_path.txt").read_text(encoding="utf-8").strip()
    )
    read_config = PerfBenchmarkConfig(
        adapter=build_config.adapter,
        dataset=build_config.dataset,
        output_dir=tmp_path / "store-read-report",
        training_store_dir=resolved_store,
        max_episodes=1,
        max_samples=2,
        mode="pfs-training-store-read",
    )

    run_benchmark(read_config, project_root=tmp_path)

    manifest = json.loads(
        (resolved_store / "training_store_manifest.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (resolved_store / "reports" / "read_benchmark_report.json").read_text(encoding="utf-8")
    )
    comparison = cast(dict[str, object], report["comparison"])
    assert manifest["shard_count"] == 2
    assert report["sample_count"] == 2
    assert comparison["pfs_file_open_count"] == 6
    assert comparison["pfs_metadata_ops_estimate"] < manifest["sample_count"] + 10


def test_store_metric_contract_should_pass_job_1833_decode_bottleneck_case() -> None:
    """验证 job 1833 数值使用 effective raw comparator。"""
    comparison: dict[str, object] = {
        "decode_avoided_ratio": 1.0,
        "raw_batch_latency_ms_p50": 2.86716,
        "raw_batch_latency_ms_p95": 2.86716,
        "raw_comparison_basis": "media_decode_bottleneck",
        "raw_effective_batch_latency_ms_p50": 25.963794,
        "raw_effective_batch_latency_ms_p95": 25.963794,
        "raw_media_decode_time_ms": 25.963794,
        "speedup_vs_raw_decode": 25.963794 / 9.233619,
        "training_store_batch_latency_ms_p50": 9.233619,
        "training_store_batch_latency_ms_p95": 9.233619,
    }

    classification = classify_training_store_comparison(comparison)
    speedup = comparison["speedup_vs_raw_decode"]

    assert comparison["raw_effective_batch_latency_ms_p50"] == pytest.approx(25.963794)
    assert isinstance(speedup, (float, int))
    assert speedup > 2.0
    assert classification.classification == "PASS"
    assert "media_decode_bottleneck" in "\n".join(classification.reasons)


def test_store_metric_contract_should_not_fake_media_speedup_when_decode_missing() -> None:
    """验证缺少 raw media decode 时回退 raw batch comparator。"""
    comparison: dict[str, object] = {
        "decode_avoided_ratio": 1.0,
        "raw_batch_latency_ms_p50": 20.0,
        "raw_batch_latency_ms_p95": 25.0,
        "raw_comparison_basis": "raw_batch_latency",
        "raw_effective_batch_latency_ms_p50": 20.0,
        "raw_effective_batch_latency_ms_p95": 25.0,
        "raw_media_decode_time_ms": "missing",
        "speedup_vs_raw_decode": 20.0 / 12.0,
        "training_store_batch_latency_ms_p50": 12.0,
        "training_store_batch_latency_ms_p95": 12.0,
    }

    classification = classify_training_store_comparison(comparison)

    assert classification.classification == "WARN"
    assert "media_decode_bottleneck" not in "\n".join(classification.reasons)


def test_store_metric_contract_should_keep_raw_batch_basis_when_not_decode_dominated() -> None:
    """验证非 media-dominated 时保持 raw batch comparator。"""
    comparison: dict[str, object] = {
        "decode_avoided_ratio": 1.0,
        "raw_batch_latency_ms_p50": 20.0,
        "raw_batch_latency_ms_p95": 24.0,
        "raw_comparison_basis": "raw_batch_latency",
        "raw_effective_batch_latency_ms_p50": 20.0,
        "raw_effective_batch_latency_ms_p95": 24.0,
        "raw_media_decode_time_ms": 5.0,
        "speedup_vs_raw_decode": 20.0 / 8.0,
        "training_store_batch_latency_ms_p50": 8.0,
        "training_store_batch_latency_ms_p95": 8.0,
    }

    classification = classify_training_store_comparison(comparison)

    assert classification.classification == "PASS"
    assert "raw_batch_latency" in "\n".join(classification.reasons)


def test_store_read_benchmark_should_emit_effective_raw_comparator(tmp_path: Path) -> None:
    """验证 store-read 报告写出 effective raw comparator 字段。"""
    store_dir = tmp_path / "training-store"
    base_config = _config(tmp_path)
    build_config = PerfBenchmarkConfig(
        adapter=base_config.adapter,
        dataset=base_config.dataset,
        output_dir=tmp_path / "perf-build",
        training_store_dir=store_dir,
        max_episodes=base_config.max_episodes,
        max_samples=base_config.max_samples,
        mode="store-build-bounded",
    )
    run_benchmark(build_config, project_root=tmp_path)
    build_report_path = store_dir / "build_report.json"
    build_report = json.loads(build_report_path.read_text(encoding="utf-8"))
    raw_baseline = cast(dict[str, object], build_report["raw_bounded_decode_baseline"])
    raw_baseline.update(
        {
            "raw_batch_latency_ms_p50": 2.86716,
            "raw_batch_latency_ms_p95": 2.86716,
            "raw_media_decode_time_ms": 25.963794,
        }
    )
    build_report_path.write_text(
        json.dumps(build_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    read_config = PerfBenchmarkConfig(
        adapter=build_config.adapter,
        dataset=build_config.dataset,
        output_dir=tmp_path / "perf-read",
        training_store_dir=store_dir,
        max_episodes=build_config.max_episodes,
        max_samples=build_config.max_samples,
        mode="store-read-benchmark",
    )

    result = run_benchmark(read_config, project_root=tmp_path)

    report = json.loads((store_dir / "read_benchmark_report.json").read_text(encoding="utf-8"))
    comparison = cast(dict[str, object], report["comparison"])
    missing_telemetry = comparison["missing_telemetry"]
    speedup = comparison["speedup_vs_raw_decode"]
    assert result.classification.classification == "PASS"
    assert comparison["raw_comparison_basis"] == "media_decode_bottleneck"
    assert comparison["raw_effective_batch_latency_ms_p50"] == pytest.approx(25.963794)
    assert comparison["raw_effective_batch_latency_ms_p95"] == pytest.approx(25.963794)
    assert isinstance(speedup, (float, int))
    assert speedup > 2.0
    assert isinstance(missing_telemetry, list)
    assert "raw_batch_latency_ms_p50" not in missing_telemetry
    assert "raw_media_decode_time_ms" not in missing_telemetry


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
        "performance_counters_schema",
        "pfs_language_token_policy",
        "pfs_prepacked_frame_policy",
        "pfs_training_store_manifest",
        "sample_to_shard_index",
        "shard_manifest",
    }
    assert "local_nvme_staging_manifest" not in schema


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
