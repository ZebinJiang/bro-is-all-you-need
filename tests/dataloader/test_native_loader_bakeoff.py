"""Native-loader W8 bakeoff harness 测试。"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, cast

import autovla.testing.fixtures as fixture_module
from autovla.dataloader.perf.native_loader_bakeoff import (
    NATIVE_LOADER_CANDIDATE_IDS,
    NativeLoaderBakeoffConfig,
    run_native_loader_bakeoff,
)


def test_native_loader_bakeoff_should_emit_required_outputs(tmp_path: Path) -> None:
    """验证 CLI 等价执行写出报告、ledger 和五个候选输出目录。"""
    fixture = fixture_module.tiny_lerobot_fixture(tmp_path / "tiny_zjh")
    working_root = tmp_path / "datasets" / "working" / "autovla_format_native_loader_bakeoff"
    output_dir = tmp_path / "runs" / "tmp" / "native-loader"

    result = run_native_loader_bakeoff(
        NativeLoaderBakeoffConfig(
            source_dataset=fixture.root,
            working_root=working_root,
            output_dir=output_dir,
            gr00t_root=tmp_path / "Isaac-GR00T17",
            worker_count=8,
            max_episodes=2,
            max_samples=4,
            repeats=3,
            candidates=NATIVE_LOADER_CANDIDATE_IDS,
        )
    )

    assert result.conclusion == "READY_FOR_COMPUTE_BENCHMARK"
    assert (output_dir / "native-loader-backend-bakeoff-report.md").is_file()
    assert (output_dir / "generated-artifact-ledger.json").is_file()
    assert set(result.candidate_dirs) == set(NATIVE_LOADER_CANDIDATE_IDS)

    ledger = _read_json(output_dir / "generated-artifact-ledger.json")
    assert ledger["generated_artifacts_tracked"] is False
    assert ledger["source_dataset_mutated"] is False
    for entry in cast(list[dict[str, object]], ledger["entries"]):
        assert entry["tracked_status"] == "ignored_generated_artifact"
        assert str(entry["path"]).startswith(working_root.as_posix())


def test_native_loader_bakeoff_should_classify_blocked_candidates(tmp_path: Path) -> None:
    """验证 GR00T、LeRobot v3 和 Zarr 只写明确 not-run reason。"""
    fixture = fixture_module.tiny_lerobot_fixture(tmp_path / "tiny_zjh")
    result = run_native_loader_bakeoff(
        NativeLoaderBakeoffConfig(
            source_dataset=fixture.root,
            working_root=tmp_path / "datasets" / "working" / "autovla_format_native_loader_bakeoff",
            output_dir=tmp_path / "runs" / "tmp" / "native-loader",
            gr00t_root=tmp_path / "Isaac-GR00T17",
            worker_count=8,
            max_episodes=2,
            max_samples=4,
            repeats=3,
            candidates=NATIVE_LOADER_CANDIDATE_IDS,
        )
    )

    by_id = {row["candidate_id"]: row for row in result.rows}
    assert by_id["zjh_lerobot_v21_raw"]["classification"] == "NOT_RUN_UNSAFE_OR_UNAVAILABLE"
    assert by_id["lerobot_v3_converted"]["classification"] == "NOT_RUN_DEPENDENCY_BLOCKED"
    assert by_id["zarr_converted"]["classification"] == "NOT_RUN_DEPENDENCY_BLOCKED"
    for candidate_id in (
        "zjh_lerobot_v21_raw",
        "lerobot_v3_converted",
        "zarr_converted",
    ):
        reason_path = result.candidate_dirs[candidate_id] / "not_run_reason.json"
        reason = _read_json(reason_path)
        reason_effects = cast(dict[str, object], reason["external_effects"])
        assert reason["candidate_id"] == candidate_id
        assert reason["classification"] == by_id[candidate_id]["classification"]
        assert reason_effects["model_load"] is False
        assert reason_effects["real_training"] is False


def test_native_loader_bakeoff_should_validate_runnable_payloads(tmp_path: Path) -> None:
    """验证两个 runnable converted 候选证明 action、语言和三路 RGB 引用。"""
    fixture = fixture_module.tiny_lerobot_fixture(tmp_path / "tiny_zjh")
    result = run_native_loader_bakeoff(
        NativeLoaderBakeoffConfig(
            source_dataset=fixture.root,
            working_root=tmp_path / "datasets" / "working" / "autovla_format_native_loader_bakeoff",
            output_dir=tmp_path / "runs" / "tmp" / "native-loader",
            gr00t_root=tmp_path / "Isaac-GR00T17",
            worker_count=8,
            max_episodes=2,
            max_samples=4,
            repeats=3,
            candidates=("webdataset_converted", "robodm_style_converted"),
        )
    )

    by_id = {row["candidate_id"]: row for row in result.rows}
    assert by_id["webdataset_converted"]["classification"] == "RUNNABLE_NOW"
    assert by_id["robodm_style_converted"]["classification"] == "RUNNABLE_NOW"
    assert by_id["robodm_style_converted"]["prototype_only"] is True

    for candidate_id in ("webdataset_converted", "robodm_style_converted"):
        candidate_dir = result.candidate_dirs[candidate_id]
        validation = _read_json(candidate_dir / "payload_contract_validation.json")
        manifest = _read_json(candidate_dir / "conversion_manifest.json")
        first_payload = _read_json(candidate_dir / "benchmark_payload_rows.jsonl")

        assert validation["payload_valid"] is True
        assert validation["worker_count"] == 8
        assert validation["candidate_id"] == candidate_id
        assert validation["payload_missing_fields"] == []
        assert validation["camera_stream_count"] == 3
        assert manifest["source_dataset_mutated"] is False
        assert manifest["generated_artifacts_tracked"] is False
        assert first_payload["action_shape"] == [1, 3]
        assert first_payload["action_dtype"] == "float32"
        assert first_payload["language"]
        camera_shapes = cast(dict[str, object], first_payload["camera_shapes"])
        camera_dtypes = cast(dict[str, object], first_payload["camera_dtypes"])
        assert len(camera_shapes) == 3
        assert set(camera_dtypes.values()) == {"video_stream_ref"}
        assert first_payload["source_backend"] == candidate_id
        assert not first_payload["payload_missing_fields"]
        assert first_payload["payload_hash"]


def test_native_loader_bakeoff_should_record_real_w8_worker_evidence(tmp_path: Path) -> None:
    """验证 runnable 候选必须记录真实八 worker 参与证据。"""
    source_dataset = _eight_row_lerobot_fixture(tmp_path / "tiny_zjh_w8")
    output_dir = tmp_path / "runs" / "tmp" / "native-loader"
    result = run_native_loader_bakeoff(
        NativeLoaderBakeoffConfig(
            source_dataset=source_dataset,
            working_root=tmp_path / "datasets" / "working" / "autovla_format_native_loader_bakeoff",
            output_dir=output_dir,
            gr00t_root=tmp_path / "Isaac-GR00T17",
            worker_count=8,
            max_episodes=4,
            max_samples=8,
            repeats=3,
            candidates=("webdataset_converted", "robodm_style_converted"),
        )
    )

    by_id = {row["candidate_id"]: row for row in result.rows}
    for candidate_id in ("webdataset_converted", "robodm_style_converted"):
        evidence = cast(dict[str, object], by_id[candidate_id]["worker_execution_evidence"])
        result_payload = _read_json(output_dir / f"{candidate_id}-result.json")
        validation = _read_json(
            result.candidate_dirs[candidate_id] / "payload_contract_validation.json"
        )
        worker_ids = cast(list[str], evidence["worker_ids"])
        per_worker_counts = cast(dict[str, int], evidence["per_worker_sample_counts"])

        assert evidence["requested_worker_count"] == 8
        assert evidence["observed_worker_count"] == 8
        assert evidence["worker_execution_mode"] == "thread_pool"
        assert evidence["worker_count_evidence_status"] == "PASS"
        assert evidence["every_worker_observed_sample"] is True
        assert len(worker_ids) == 8
        assert sorted(worker_ids) == [f"worker-{index:03d}" for index in range(8)]
        assert set(per_worker_counts.values()) == {1}
        assert result_payload["worker_execution_evidence"] == evidence
        assert validation["worker_count_evidence_status"] == "PASS"
        assert validation["worker_execution_evidence"] == evidence


def test_native_loader_bakeoff_should_reject_source_or_symlink_outputs(tmp_path: Path) -> None:
    """验证输出根不能是 source dataset, 且 symlink-only 输出无效。"""
    fixture = fixture_module.tiny_lerobot_fixture(tmp_path / "tiny_zjh")

    try:
        NativeLoaderBakeoffConfig(
            source_dataset=fixture.root,
            working_root=fixture.root,
            output_dir=tmp_path / "runs" / "tmp" / "native-loader",
            gr00t_root=tmp_path / "Isaac-GR00T17",
            worker_count=8,
            max_episodes=2,
            max_samples=4,
            repeats=3,
            candidates=("webdataset_converted",),
        )
    except ValueError as exc:
        assert "source dataset" in str(exc)
    else:  # pragma: no cover - 失败分支只用于保持错误消息清晰
        raise AssertionError("source dataset output root should fail")

    try:
        NativeLoaderBakeoffConfig(
            source_dataset=fixture.root,
            working_root=tmp_path / "datasets" / "working" / "autovla_format_native_loader_bakeoff",
            output_dir=tmp_path / "runs" / "tmp" / "native-loader",
            gr00t_root=tmp_path / "Isaac-GR00T17",
            worker_count=8,
            max_episodes=2,
            max_samples=4,
            repeats=3,
            candidates=("webdataset_converted",),
            symlink_only_output=True,
        )
    except ValueError as exc:
        assert "symlink-only" in str(exc)
    else:  # pragma: no cover - 失败分支只用于保持错误消息清晰
        raise AssertionError("symlink-only output should fail")


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON object 或 JSONL 第一行。"""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        text = text.splitlines()[0]
    loaded = json.loads(text)
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def _eight_row_lerobot_fixture(root: Path) -> Path:
    """写入八行 tiny LeRobot-like parquet, 用于证明八个 worker 都处理样本。"""
    pa: Any = importlib.import_module("pyarrow")
    pq: Any = importlib.import_module("pyarrow.parquet")
    data_dir = root / "data" / "chunk-000"
    data_dir.mkdir(parents=True, exist_ok=True)
    action_dim = 3
    schema = pa.schema(
        [
            pa.field("index", pa.int64(), nullable=False),
            pa.field("episode_index", pa.int64(), nullable=False),
            pa.field("frame_index", pa.int64(), nullable=False),
            pa.field("timestamp", pa.float64(), nullable=False),
            pa.field("task_index", pa.int64(), nullable=False),
            pa.field("observation.state", pa.list_(pa.float32(), action_dim), nullable=False),
            pa.field("action", pa.list_(pa.float32(), action_dim), nullable=False),
            pa.field("action_mask", pa.list_(pa.bool_(), action_dim), nullable=False),
            pa.field("language", pa.string(), nullable=False),
            pa.field("robot_tag", pa.string(), nullable=False),
            pa.field("sample_source", pa.string(), nullable=False),
        ]
    )
    columns = {
        "index": list(range(8)),
        "episode_index": [index // 2 for index in range(8)],
        "frame_index": [index % 2 for index in range(8)],
        "timestamp": [float(index) / 10.0 for index in range(8)],
        "task_index": [0 for _ in range(8)],
        "observation.state": [[float(index), float(index + 1), 1.0] for index in range(8)],
        "action": [[float(index), float(index + 2), 0.0] for index in range(8)],
        "action_mask": [[True, True, False] for _ in range(8)],
        "language": [f"tiny w8 task {index}" for index in range(8)],
        "robot_tag": ["tiny-arm" for _ in range(8)],
        "sample_source": [json.dumps({"fixture": "w8", "index": index}) for index in range(8)],
    }
    arrays = [pa.array(columns[name], type=schema.field(name).type) for name in schema.names]
    table = pa.Table.from_arrays(arrays, schema=schema)
    pq.write_table(table, data_dir / "file-000.parquet")
    return root
