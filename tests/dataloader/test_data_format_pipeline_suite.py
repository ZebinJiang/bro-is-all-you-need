"""AutoVLA 数据格式流水线套件测试。"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Mapping, cast

import pytest

from autovla.dataloader.format_pipeline import (
    DATA_FORMAT_PIPELINE_SCHEMA_VERSION,
    FORMAT_PIPELINE_CANDIDATES,
    FormatPipelineConfig,
    build_validate_benchmark_pipeline,
    validate_benchmark_payload,
)
from autovla.dataloader.format_pipeline.cli import main as pipeline_cli_main


def test_pipeline_should_build_validate_and_benchmark_all_candidate_statuses(
    tmp_path: Path,
) -> None:
    """验证四个候选都有确定状态, 两个生产化候选写出真实 artifact。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "source", sample_count=6)
    working_root = tmp_path / "datasets" / "working" / "autovla_data_format_pipeline_suite"
    task_root = tmp_path / "runs" / "tmp" / "AUTOVLA-M3-DATA-FORMAT-PIPELINE-SUITE-001"
    output_dir = task_root / "pipeline-output"

    result = build_validate_benchmark_pipeline(
        FormatPipelineConfig(
            source_dataset=source_dataset,
            working_root=working_root,
            output_dir=output_dir,
            max_episodes=1,
            max_samples=6,
            samples_per_shard=3,
            batch_size=2,
            warmup_batches=0,
            measured_batches=2,
            materializer="synthetic",
        )
    )

    assert {manifest.candidate_id for manifest in result.candidate_manifests} == set(
        FORMAT_PIPELINE_CANDIDATES
    )
    assert (working_root / "webdataset_store" / "shards" / "shard-000000.tar").is_file()
    assert (working_root / "robodm_style_store" / "containers" / "container-000000.vla").is_file()
    assert (working_root / "lerobot_v3_store" / "dependency_decision.json").is_file()
    assert result.generated_artifact_ledger == output_dir / "generated-artifact-ledger.json"
    assert (task_root / "generated-artifact-ledger.json").is_file()
    assert (task_root / "data-format-pipeline-validation.md").is_file()

    results_payload = _read_json(output_dir / "data-format-pipeline-results.json")
    benchmark_by_candidate = {
        cast(str, row["candidate"]): row
        for row in cast(list[dict[str, object]], results_payload["benchmark_rows"])
    }
    for candidate in (
        "raw_zjh_lerobot_v21_baseline",
        "webdataset_native",
        "robodm_style",
    ):
        row = benchmark_by_candidate[candidate]
        assert row["benchmark_status"] == "PASS"
        assert row["missing_metrics"] == []
        assert _number(row, "p50_batch_latency_ms") >= 0.0
        assert _number(row, "p95_batch_latency_ms") >= _number(row, "p50_batch_latency_ms")
        assert row["worker_count"] == 8
    assert benchmark_by_candidate["lerobot_v3"]["benchmark_status"] == "NOT_RUN_DEPENDENCY_BLOCKED"

    for manifest in result.candidate_manifests:
        payload = manifest.payload
        assert payload["schema_version"] == DATA_FORMAT_PIPELINE_SCHEMA_VERSION
        assert payload["generated_artifacts_tracked"] is False
        assert payload["no_source_mutation"] is True
        assert payload["no_training"] is True
        assert payload["no_model_load"] is True
        assert payload["no_hf_network"] is True
        assert payload["no_wandb_network"] is True
        assert payload["camera_stream_count"] == 3
        assert payload["action_dim"] == 3
        assert payload["state_dim"] == 3
        assert payload["source_dataset_path"] == source_dataset.as_posix()

    ledger = _read_json(task_root / "generated-artifact-ledger.json")
    entries = cast(list[dict[str, object]], ledger["entries"])
    assert {entry["candidate"] for entry in entries} == set(FORMAT_PIPELINE_CANDIDATES)
    assert all(entry["tracked_status"] == "ignored_generated_artifact" for entry in entries)
    assert all(entry["source_dataset_modified"] is False for entry in entries)


def test_pipeline_should_validate_webdataset_and_robodm_payloads_from_artifacts(
    tmp_path: Path,
) -> None:
    """验证生产化候选读取的是转换后 artifact, 而不是 source 伪引用。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "source", sample_count=4)
    working_root = tmp_path / "working"
    output_dir = tmp_path / "runs" / "pipeline-output"

    build_validate_benchmark_pipeline(
        FormatPipelineConfig(
            source_dataset=source_dataset,
            working_root=working_root,
            output_dir=output_dir,
            candidates=("webdataset_native", "robodm_style"),
            max_episodes=1,
            max_samples=4,
            samples_per_shard=2,
            batch_size=2,
            warmup_batches=0,
            measured_batches=1,
            materializer="synthetic",
        )
    )

    webdataset_index = _read_jsonl(working_root / "webdataset_store" / "sample_index.jsonl")
    robodm_index = _read_jsonl(working_root / "robodm_style_store" / "sample_index.jsonl")
    assert cast(dict[str, object], webdataset_index[0])["shard"] == "shards/shard-000000.tar"
    assert cast(dict[str, object], robodm_index[0])["container"] == (
        "containers/container-000000.vla"
    )
    assert not any(path.is_symlink() for path in working_root.rglob("*"))

    web_manifest = _read_json(working_root / "webdataset_store" / "webdataset_store_manifest.json")
    robo_manifest = _read_json(working_root / "robodm_style_store" / "robodm_style_manifest.json")
    assert web_manifest["dependency_mode"] == "webdataset_package"
    assert robo_manifest["dependency_mode"] == "autovla_owned_no_upstream_robodm_package"
    assert robo_manifest["prototype_only"] is False
    assert web_manifest["checksums"]
    assert robo_manifest["checksums"]


def test_pipeline_config_should_reject_source_output_roots(tmp_path: Path) -> None:
    """验证 source dataset 下不能成为工作或报告输出目录。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "source", sample_count=1)

    with pytest.raises(ValueError, match="working_root"):
        FormatPipelineConfig(
            source_dataset=source_dataset,
            working_root=source_dataset / "derived",
            output_dir=tmp_path / "runs",
        )
    with pytest.raises(ValueError, match="output_dir"):
        FormatPipelineConfig(
            source_dataset=source_dataset,
            working_root=tmp_path / "working",
            output_dir=source_dataset / "runs",
        )


def test_benchmark_payload_should_reject_missing_or_fake_payload_fields() -> None:
    """验证 BenchmarkPayload 不能缺 action/language/RGB, 也不能接受非 bool mask。"""
    payload = _valid_payload()
    validate_benchmark_payload(payload)

    broken = dict(payload)
    broken["language"] = ""
    with pytest.raises(ValueError, match="language"):
        validate_benchmark_payload(broken)

    broken = dict(payload)
    broken["action_mask"] = [1, 0, 1]
    with pytest.raises(ValueError, match="bool-only"):
        validate_benchmark_payload(broken)

    broken = dict(payload)
    broken["camera.rgb_1"] = {"shape": [2, 2, 3], "dtype": "uint8", "byte_length": 11}
    with pytest.raises(ValueError, match="byte_length"):
        validate_benchmark_payload(broken)


def test_cli_should_emit_stable_pipeline_result_path(tmp_path: Path, capsys: Any) -> None:
    """验证 python -m 等价 CLI 可以执行 build-validate-benchmark。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "source", sample_count=3)
    output_dir = tmp_path / "runs" / "pipeline-output"

    exit_code = pipeline_cli_main(
        [
            "build-validate-benchmark",
            "--source-dataset",
            source_dataset.as_posix(),
            "--working-root",
            (tmp_path / "working").as_posix(),
            "--output-dir",
            output_dir.as_posix(),
            "--max-episodes",
            "1",
            "--max-samples",
            "3",
            "--samples-per-shard",
            "2",
            "--batch-size",
            "1",
            "--warmup-batches",
            "0",
            "--measured-batches",
            "1",
            "--materializer",
            "synthetic",
            "--candidate",
            "webdataset_native",
            "--candidate",
            "robodm_style",
            "--candidate",
            "lerobot_v3",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == (output_dir / "data-format-pipeline-results.json").as_posix()
    assert (output_dir / "data-format-pipeline-results.json").is_file()


def test_readme_dashboard_should_present_autovla_as_active_identity() -> None:
    """验证根 README 不再以 StarVLA 作为 active project branding。"""
    readme = Path("README.md").read_text(encoding="utf-8")

    assert readme.startswith("# AutoVLA")
    assert "AI-Native-VLA-Infra" in readme
    assert "docs/benchmarks/DATA_FORMAT_PIPELINE_SUITE.md" in readme
    assert "WebDataset-native" in readme
    assert "Robo-DM-style" in readme
    assert "LeRobot v3" in readme
    assert "PR #16 remains a draft backend research artifact" in readme
    assert '<h1 align="center">StarVLA' not in readme
    assert "StarVLA: A Lego-like" not in readme


def _tiny_zjh_fixture(root: Path, *, sample_count: int) -> Path:
    """写入 tiny LeRobot-v2.1 fixture。"""
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
                        "video.height": 2,
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
        json.dumps({"task_index": 0, "task": "tiny pipeline task"}) + "\n",
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
    columns: dict[str, object] = {
        "index": list(range(sample_count)),
        "episode_index": [0 for _ in range(sample_count)],
        "frame_index": list(range(sample_count)),
        "timestamp": [float(index) / 30.0 for index in range(sample_count)],
        "task_index": [0 for _ in range(sample_count)],
        "observation.state": [[float(index), 1.0, 2.0] for index in range(sample_count)],
        "action": [[float(index), 0.0, 1.0] for index in range(sample_count)],
        "action_mask": [[True, True, False] for _ in range(sample_count)],
        "language": ["tiny pipeline task" for _ in range(sample_count)],
    }
    arrays = [pa.array(columns[name], type=schema.field(name).type) for name in schema.names]
    table = pa.Table.from_arrays(arrays, schema=schema)
    pq.write_table(table, data_dir / "file-000.parquet")
    return root


def _valid_payload() -> dict[str, object]:
    """构造最小 BenchmarkPayload。"""
    camera = {
        "byte_length": 12,
        "dtype": "uint8",
        "shape": [2, 2, 3],
        "sha256": "abc",
    }
    return {
        "action": [0.0, 1.0, 2.0],
        "action_mask": [True, True, False],
        "camera.rgb_0": dict(camera),
        "camera.rgb_1": dict(camera),
        "camera.rgb_2": dict(camera),
        "episode_id": "episode-000000",
        "language": "tiny task",
        "payload_hash": "hash",
        "payload_missing_fields": [],
        "sample_id": "sample-000000000",
        "source_backend": "webdataset_native",
        "state": [0.0, 1.0, 2.0],
    }


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON object。"""
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def _read_jsonl(path: Path) -> list[object]:
    """读取 JSONL rows。"""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _number(row: Mapping[str, object], key: str) -> float:
    """读取测试用 numeric 字段。"""
    value = row[key]
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    return float(value)
