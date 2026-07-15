"""多格式 datastore bakeoff 数据侧测试。"""

from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from autovla.dataloader.stores.benchmark import (
    MultiformatDatastoreConfig,
    run_multiformat_datastore_bakeoff,
)
from autovla.dataloader.stores.cli import main as stores_main
from autovla.dataloader.stores.common import load_source_samples
from autovla.dataloader.stores.lerobot_v3_reader import read_lerobot_v3_local_batches
from autovla.dataloader.stores.sample_window_manifest import (
    MANIFEST_VERSION,
    build_sample_window_manifest,
)


def test_shared_manifest_should_be_deterministic_and_field_complete(tmp_path: Path) -> None:
    """验证共享 sample/window manifest 稳定且字段完整。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "source", sample_count=6)
    config = MultiformatDatastoreConfig(
        source_dataset=source_dataset,
        readonly_root=tmp_path,
        working_root=tmp_path / "datasets" / "working" / "autovla_multiformat_bakeoff_gpu200",
        output_dir=tmp_path / "runs" / "tmp" / "task-output",
        max_episodes=2,
        max_samples=5,
        seed=11,
    )

    manifest_left = build_sample_window_manifest(config)
    manifest_right = build_sample_window_manifest(config)

    assert manifest_left.to_json_dict() == manifest_right.to_json_dict()
    payload = manifest_left.to_json_dict()
    assert payload["manifest_version"] == MANIFEST_VERSION
    assert payload["source_format"] == "zjh_lerobot_v21"
    assert payload["seed"] == 11
    assert payload["max_episodes"] == 2
    assert payload["max_samples"] == 5
    assert payload["window_size"] == 1
    assert payload["action_horizon"] == 1
    assert payload["action_dim"] == 3
    assert payload["camera_views"] == [
        "observation.images.left_wrist_rgb",
        "observation.images.head_rgb",
        "observation.images.right_wrist_rgb",
    ]
    assert len(cast(list[str], payload["selected_sample_ids"])) == 5
    assert len(cast(list[str], payload["selected_window_ids"])) == 5
    assert payload["language_present_count"] == 5
    assert payload["state_present_count"] == 5
    assert payload["camera_ref_count"] == 15
    assert isinstance(payload["checksum"], str) and payload["checksum"]


def test_bakeoff_should_emit_four_runnable_candidate_rows_and_tables(tmp_path: Path) -> None:
    """验证四个候选行、runnable 语义、artifact 和 JSON/CSV/Markdown 表。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "source", sample_count=6)
    readonly_root = tmp_path
    working_root = tmp_path / "datasets" / "working" / "autovla_multiformat_bakeoff_gpu200"
    output_dir = tmp_path / "runs" / "tmp" / "AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001"

    result = run_multiformat_datastore_bakeoff(
        MultiformatDatastoreConfig(
            source_dataset=source_dataset,
            readonly_root=readonly_root,
            working_root=working_root,
            output_dir=output_dir,
            max_episodes=2,
            max_samples=6,
            samples_per_shard=3,
            batch_size=2,
            measured_batches=2,
            seed=11,
        )
    )

    row_by_candidate = {row["candidate_id"]: row for row in result.rows}
    assert set(row_by_candidate) == {
        "zjh_lerobot_v21_raw",
        "zjh_lerobot_v3_local",
        "zjh_webdataset_tar",
        "zjh_robodm_container_v1",
    }
    raw_row = row_by_candidate["zjh_lerobot_v21_raw"]
    v3_row = row_by_candidate["zjh_lerobot_v3_local"]
    wds_row = row_by_candidate["zjh_webdataset_tar"]
    robo_row = row_by_candidate["zjh_robodm_container_v1"]

    assert raw_row["status"] == "PASS"
    assert raw_row["source_mode"] == "read_only_raw_source"
    assert raw_row["sample_ids"] == list(result.manifest.selected_sample_ids)
    assert raw_row["window_ids"] == list(result.manifest.selected_window_ids)

    assert v3_row["status"] == "PASS"
    assert v3_row["source_mode"] == "lerobot_v3_local_artifact"
    assert v3_row["sample_ids"] == list(result.manifest.selected_sample_ids)
    assert v3_row["window_ids"] == list(result.manifest.selected_window_ids)
    assert (working_root / "zjh_lerobot_v3_local" / "records" / "sample-000000000.json").is_file()
    assert (working_root / "zjh_lerobot_v3_local" / "sample_index.jsonl").is_file()
    assert (working_root / "zjh_lerobot_v3_local" / "episode_index.jsonl").is_file()

    assert wds_row["status"] == "PASS"
    assert wds_row["prototype_only"] is False
    assert wds_row["sample_ids"] == list(result.manifest.selected_sample_ids)
    assert wds_row["window_ids"] == list(result.manifest.selected_window_ids)
    assert (working_root / "zjh_webdataset_tar" / "shards" / "shard-000000.tar").is_file()
    assert (working_root / "zjh_webdataset_tar" / "sample_index.jsonl").is_file()

    assert robo_row["status"] == "PASS"
    assert robo_row["prototype_only"] is True
    assert robo_row["sample_ids"] == list(result.manifest.selected_sample_ids)
    assert robo_row["window_ids"] == list(result.manifest.selected_window_ids)
    assert (
        working_root / "zjh_robodm_container_v1" / "containers" / "container-000000.vla"
    ).is_file()
    assert (working_root / "zjh_robodm_container_v1" / "sample_index.jsonl").is_file()

    for candidate in (raw_row, v3_row, wds_row, robo_row):
        benchmark = cast(dict[str, object], candidate["benchmark"])
        assert candidate["camera_views"] == [
            "observation.images.left_wrist_rgb",
            "observation.images.head_rgb",
            "observation.images.right_wrist_rgb",
        ]
        assert candidate["language_present"] is True
        assert candidate["state_present"] is True
        assert candidate["action_mask_present"] is True
        assert cast(int, candidate["artifact_file_count"]) >= 1
        assert cast(int, candidate["artifact_size_bytes"]) >= 1
        assert candidate["episode_count"] == result.manifest.episode_count
        assert benchmark["sample_count"] == 6
        assert benchmark["batch_size"] == 2
        assert cast(float, benchmark["p50_ms"]) >= 0.0
        assert cast(float, benchmark["p95_ms"]) >= cast(float, benchmark["p50_ms"])

    assert result.json_path.is_file()
    assert result.csv_path.is_file()
    assert result.markdown_path.is_file()
    assert result.ledger_path.is_file()
    ledger = json.loads(result.ledger_path.read_text(encoding="utf-8"))
    assert ledger["generated_artifacts_tracked"] is False
    assert ledger["source_dataset_mutated"] is False
    ledger_entries = cast(list[dict[str, object]], ledger["entries"])
    assert {entry["candidate"] for entry in ledger_entries} == {
        "zjh_lerobot_v21_raw",
        "zjh_lerobot_v3_local",
        "zjh_webdataset_tar",
        "zjh_robodm_container_v1",
    }
    for entry in ledger_entries:
        assert set(entry) >= {
            "candidate",
            "checksum_manifest",
            "created_by",
            "file_count",
            "path",
            "safe_to_delete_later",
            "size_bytes",
            "tracked_status",
        }
        assert entry["tracked_status"] == "ignored_generated_artifact"


def test_config_should_reject_output_inside_source_dataset(tmp_path: Path) -> None:
    """验证 source dataset 不能作为输出根。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "source", sample_count=1)

    with pytest.raises(ValueError, match="working_root"):
        MultiformatDatastoreConfig(
            source_dataset=source_dataset,
            readonly_root=tmp_path,
            working_root=source_dataset / "derived",
            output_dir=tmp_path / "runs",
        )
    with pytest.raises(ValueError, match="output_dir"):
        MultiformatDatastoreConfig(
            source_dataset=source_dataset,
            readonly_root=tmp_path,
            working_root=tmp_path / "datasets" / "working",
            output_dir=source_dataset / "runs",
        )


def test_cli_should_load_yaml_and_materialize_manifest_and_tables(tmp_path: Path) -> None:
    """验证 CLI 能从 YAML 配置执行 bounded bakeoff。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "source", sample_count=6)
    working_root = tmp_path / "datasets" / "working" / "autovla_multiformat_bakeoff_gpu200"
    output_dir = tmp_path / "runs" / "tmp" / "wave2-output"
    config_path = tmp_path / "multiformat_bakeoff.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "source_dataset": source_dataset.as_posix(),
                "readonly_root": tmp_path.as_posix(),
                "working_root": working_root.as_posix(),
                "output_dir": output_dir.as_posix(),
                "max_episodes": 2,
                "max_samples": 6,
                "samples_per_shard": 3,
                "batch_size": 2,
                "measured_batches": 2,
                "seed": 11,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    exit_code = stores_main(["run", "--config", str(config_path)])

    assert exit_code == 0
    assert (
        working_root / "multiformat_bakeoff" / "multiformat_sample_window_manifest.json"
    ).is_file()
    assert (output_dir / "load-benchmark.json").is_file()
    assert (output_dir / "load-benchmark.csv").is_file()
    assert (output_dir / "load-benchmark.md").is_file()


def test_raw_candidate_root_should_emit_isaac_required_meta_surface(tmp_path: Path) -> None:
    """验证 raw candidate root 已具备 Isaac 所需的标准 meta surface。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "source", sample_count=6)
    result = run_multiformat_datastore_bakeoff(
        MultiformatDatastoreConfig(
            source_dataset=source_dataset,
            readonly_root=tmp_path,
            working_root=tmp_path / "datasets" / "working" / "autovla_multiformat_bakeoff_gpu200",
            output_dir=tmp_path / "runs" / "tmp" / "wave8-output",
            max_episodes=2,
            max_samples=6,
            samples_per_shard=3,
            batch_size=2,
            measured_batches=2,
            seed=11,
        )
    )

    raw_root = Path(cast(str, result.rows[0]["candidate_root"]))

    assert (raw_root / "meta" / "info.json").is_file()
    assert (raw_root / "meta" / "episodes.jsonl").is_file()
    assert (raw_root / "meta" / "tasks.jsonl").is_file()
    assert (raw_root / "meta" / "modality.json").is_file()
    assert (raw_root / "meta" / "stats.json").is_file()
    assert (raw_root / "data").exists()
    assert (raw_root / "videos").exists()


def test_lerobot_v3_local_candidate_should_not_depend_on_records_json_only_layout(
    tmp_path: Path,
) -> None:
    """验证本地 v3 candidate 即使移除 records 目录也能通过真实布局读取。"""
    source_dataset = _tiny_zjh_fixture(tmp_path / "source", sample_count=6)
    result = run_multiformat_datastore_bakeoff(
        MultiformatDatastoreConfig(
            source_dataset=source_dataset,
            readonly_root=tmp_path,
            working_root=tmp_path / "datasets" / "working" / "autovla_multiformat_bakeoff_gpu200",
            output_dir=tmp_path / "runs" / "tmp" / "wave8-output",
            max_episodes=2,
            max_samples=6,
            samples_per_shard=3,
            batch_size=2,
            measured_batches=2,
            seed=11,
        )
    )

    row_by_candidate = {row["candidate_id"]: row for row in result.rows}
    v3_root = Path(cast(str, row_by_candidate["zjh_lerobot_v3_local"]["candidate_root"]))

    assert (v3_root / "meta" / "info.json").is_file()
    assert (v3_root / "meta" / "episodes.jsonl").is_file()
    assert (v3_root / "meta" / "tasks.jsonl").is_file()
    assert (v3_root / "meta" / "modality.json").is_file()
    assert (v3_root / "meta" / "stats.json").is_file()
    assert (v3_root / "data" / "chunk-000" / "episode_000000.parquet").is_file()

    if (v3_root / "records").exists():
        shutil.rmtree(v3_root / "records")

    payloads = read_lerobot_v3_local_batches(v3_root, [0, 1])

    assert len(payloads) == 2
    assert payloads[0]["source_mode"] == "lerobot_v3_local_artifact"
    assert isinstance(payloads[0]["camera_refs"], list)


def test_source_samples_should_accept_mapping_camera_refs(tmp_path: Path) -> None:
    """验证真实 mapping 形态的相机列可被规范化为字符串路径。"""
    source_dataset = _tiny_zjh_fixture(
        tmp_path / "source",
        sample_count=2,
        camera_ref_mode="mapping",
    )
    config = MultiformatDatastoreConfig(
        source_dataset=source_dataset,
        readonly_root=tmp_path,
        working_root=tmp_path / "datasets" / "working" / "autovla_multiformat_bakeoff_gpu200",
        output_dir=tmp_path / "runs" / "tmp" / "mapping-camera-output",
        max_episodes=1,
        max_samples=2,
        seed=11,
    )

    samples = load_source_samples(config)

    assert len(samples) == 2
    assert samples[0].camera_refs == (
        "videos/chunk-000/observation.images.left_wrist_rgb/episode_000000.mp4",
        "videos/chunk-000/observation.images.head_rgb/episode_000000.mp4",
        "videos/chunk-000/observation.images.right_wrist_rgb/episode_000000.mp4",
    )


def test_source_samples_should_reject_malformed_mapping_camera_refs(tmp_path: Path) -> None:
    """验证坏 mapping 相机列会按字段 fail-closed。"""
    source_dataset = _tiny_zjh_fixture(
        tmp_path / "source",
        sample_count=1,
        camera_ref_mode="malformed_mapping",
    )
    config = MultiformatDatastoreConfig(
        source_dataset=source_dataset,
        readonly_root=tmp_path,
        working_root=tmp_path / "datasets" / "working" / "autovla_multiformat_bakeoff_gpu200",
        output_dir=tmp_path / "runs" / "tmp" / "bad-mapping-camera-output",
        max_episodes=1,
        max_samples=1,
        seed=11,
    )

    with pytest.raises(
        ValueError,
        match=r"observation\.images\.left_wrist_rgb\.path must be a non-empty string",
    ):
        load_source_samples(config)


def _tiny_zjh_fixture(
    root: Path,
    *,
    sample_count: int,
    camera_ref_mode: str = "string",
) -> Path:
    """写入 tiny ZJH/LeRobot v2.1 fixture。"""
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
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake video placeholder")

    metadata = {
        "codebase_version": "v2.1",
        "fps": 10,
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
        "video_path": (
            "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4"
        ),
    }
    meta_dir = root / "meta"
    meta_dir.mkdir(parents=True)
    (meta_dir / "info.json").write_text(json.dumps(metadata), encoding="utf-8")
    tasks = [
        json.dumps({"task_index": 0, "task": "pick up the bellows"}),
        json.dumps({"task_index": 1, "task": "place the bellows"}),
    ]
    (meta_dir / "tasks.jsonl").write_text("\n".join(tasks) + "\n", encoding="utf-8")

    rows: list[dict[str, object]] = []
    for index in range(sample_count):
        left_path = f"videos/chunk-000/{cameras[0]}/episode_000000.mp4"
        head_path = f"videos/chunk-000/{cameras[1]}/episode_000000.mp4"
        right_path = f"videos/chunk-000/{cameras[2]}/episode_000000.mp4"
        if camera_ref_mode == "string":
            left_camera: object = left_path
            head_camera: object = head_path
            right_camera: object = right_path
        elif camera_ref_mode == "mapping":
            left_camera = {"path": left_path, "timestamp": float(index) * 0.1}
            head_camera = {"path": head_path, "timestamp": float(index) * 0.1}
            right_camera = {"path": right_path, "timestamp": float(index) * 0.1}
        elif camera_ref_mode == "malformed_mapping":
            left_camera = {"path": "", "timestamp": float(index) * 0.1}
            head_camera = {"path": head_path, "timestamp": float(index) * 0.1}
            right_camera = {"path": right_path, "timestamp": float(index) * 0.1}
        else:
            raise ValueError(f"unsupported camera_ref_mode: {camera_ref_mode}")
        rows.append(
            {
                "observation.images.left_wrist_rgb": left_camera,
                "observation.images.head_rgb": head_camera,
                "observation.images.right_wrist_rgb": right_camera,
                "observation.state": [float(index), float(index + 1), float(index + 2)],
                "action": [float(index), float(index + 0.25), float(index + 0.5)],
                "is_first": index == 0,
                "is_last": index == sample_count - 1,
                "is_terminal": index == sample_count - 1,
                "timestamp": float(index) * 0.1,
                "frame_index": index,
                "episode_index": 0,
                "index": index,
                "task_index": index % 2,
                "annotation.human.action.task_description": (
                    "pick up the bellows" if index % 2 == 0 else "place the bellows"
                ),
            }
        )
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, data_dir / "episode_000000.parquet")
    return root
