"""WebDataset streaming Training Store backend 契约测试。"""

from __future__ import annotations

import importlib
import json
import tarfile
from pathlib import Path
from typing import Any, cast

import pytest

from autovla.dataloader.perf.benchmark import run_benchmark
from autovla.dataloader.perf.config import BenchmarkMode, PerfBenchmarkConfig


def _video_feature() -> dict[str, object]:
    """构造 WebDataset streaming tiny video metadata。"""
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
    """构造 WebDataset streaming tiny LeRobot-v2 metadata。"""
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
    """只写 WebDataset streaming tiny metadata/info/tasks。"""
    (root / "meta").mkdir(parents=True)
    encoded = json.dumps(_tiny_info(), sort_keys=True)
    (root / "metadata.json").write_text(encoded, encoding="utf-8")
    (root / "meta" / "info.json").write_text(encoded, encoding="utf-8")
    (root / "meta" / "tasks.jsonl").write_text(
        json.dumps({"task_index": 0, "task": "pick the tiny object"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_tiny_zjh_parquet(root: Path) -> None:
    """写出 WebDataset streaming tiny parquet 行, 不写媒体文件。"""
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
                "episode_index": [episode, episode],
                "frame_index": [0, 1],
                "index": [start, start + 1],
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
                "observation.state": [
                    [float(start), 1.25],
                    [float(start + 1), 1.5],
                ],
                "task_index": [0, 0],
            }
        )
        pq.write_table(table, data_dir / f"episode_{episode:06d}.parquet")


def _build_streaming_store(tmp_path: Path) -> tuple[Path, Path]:
    """构建 tiny source-derived webdataset_streaming_v1 store。"""
    dataset = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset)
    _write_tiny_zjh_parquet(dataset)
    build_config = PerfBenchmarkConfig(
        adapter="zjh-adapter",
        dataset=dataset,
        output_dir=tmp_path / "wds-build-report",
        training_store_dir=tmp_path / "derived" / "zjh-demo",
        max_episodes=2,
        max_samples=4,
        mode=cast(BenchmarkMode, "pfs-training-store-build-webdataset"),
        build_scope="full-or-budgeted",
    )

    run_benchmark(build_config, project_root=tmp_path)

    resolved_store = Path(
        (build_config.output_dir / "resolved_store_path.txt").read_text(encoding="utf-8").strip()
    )
    return dataset, resolved_store


def _read_streaming_store(tmp_path: Path, *, dataset: Path, store_dir: Path) -> dict[str, object]:
    """读取 webdataset_streaming_v1 store read report。"""
    read_config = PerfBenchmarkConfig(
        adapter="zjh-adapter",
        dataset=dataset,
        output_dir=tmp_path / "wds-read-report",
        training_store_dir=store_dir,
        max_episodes=2,
        max_samples=4,
        mode=cast(BenchmarkMode, "pfs-training-store-read-webdataset"),
    )

    run_benchmark(read_config, project_root=tmp_path)

    return cast(
        dict[str, object],
        json.loads((store_dir / "reports" / "read_benchmark_report.json").read_text("utf-8")),
    )


def _rewrite_sample_shard_path(store_dir: Path, shard_path: str) -> None:
    """篡改 samples.jsonl 的 shard_path, 用于验证 store 内路径收敛。"""
    index_path = store_dir / "index" / "samples.jsonl"
    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row["shard_path"] = shard_path
    index_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _rewrite_checksum_path(store_dir: Path, *, key: str, path: str) -> None:
    """篡改 checksums.json 的路径字段, 用于验证 checksum 不越界读取。"""
    checksum_path = store_dir / "checksums.json"
    payload = json.loads(checksum_path.read_text(encoding="utf-8"))
    payload["paths"][key] = path
    checksum_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_webdataset_dependency_should_be_perf_scoped_and_quality_pinned() -> None:
    """验证 webdataset 只作为批准的 perf/quality 依赖出现。"""
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    quality_requirements = Path("requirements/quality/quality-requirements.txt").read_text(
        encoding="utf-8"
    )
    quality_constraints = Path("requirements/quality/quality-constraints.txt").read_text(
        encoding="utf-8"
    )

    assert 'perf = ["webdataset==1.0.2"]' in pyproject
    assert "webdataset\n" in quality_requirements
    assert "webdataset==1.0.2" in quality_constraints
    assert "braceexpand==0.1.7" in quality_constraints
    assert "torch" not in pyproject.lower()
    assert "torch" not in quality_requirements.lower()


def test_webdataset_backend_registry_should_select_streaming_backend() -> None:
    """验证 AutoVLA-native registry 隐藏 raw WebDataset API。"""
    module = importlib.import_module("autovla.dataloader.perf.webdataset_streaming_store")
    registry = module.TrainingStoreBackendRegistry.with_default_backends()
    backend = registry.get("webdataset_streaming_v1")

    assert backend.backend_name == "webdataset_streaming_v1"
    assert backend.dependency_mode == "webdataset_package"
    assert backend.describe()["raw_webdataset_api_exposed"] is False


def test_webdataset_streaming_build_should_emit_manifest_and_tar_shards(tmp_path: Path) -> None:
    """验证 streaming backend 写出 deterministic manifest 和 tar shard。"""
    dataset, store_dir = _build_streaming_store(tmp_path)

    manifest = json.loads((store_dir / "training_store_manifest.json").read_text("utf-8"))

    assert manifest["backend"] == "webdataset_streaming_v1"
    assert manifest["dependency_mode"] == "webdataset_package"
    assert manifest["storage_backend"] == "pfs_shared"
    assert manifest["local_stage_used"] is False
    assert manifest["sample_count"] == 4
    assert manifest["episode_count"] == 2
    assert manifest["shard_count"] == 1
    assert manifest["shard_format"] == "tar"
    assert manifest["comparator_mode_supported"] == ["action_state_mask_only"]
    assert manifest["action_state_mask_only_supported"] is True
    assert manifest["full_training_window_supported"] is False
    assert manifest["generated_artifacts_tracked"] is False
    assert manifest["external_effects"]["real_training"] is False
    assert manifest["source_dataset"] == dataset.as_posix()
    assert (store_dir / "shards" / "shard-000000.tar").is_file()
    assert not (dataset / "training_store_manifest.json").exists()


def test_webdataset_streaming_read_should_preserve_action_state_mask(tmp_path: Path) -> None:
    """验证 WebDataset streaming iterator 读取 action/state/mask payload。"""
    dataset, store_dir = _build_streaming_store(tmp_path)

    report = _read_streaming_store(tmp_path, dataset=dataset, store_dir=store_dir)

    comparison = cast(dict[str, object], report["comparison"])
    first_sample = cast(dict[str, object], comparison["first_sample_preview"])
    assert report["checksums_verified"] is True
    assert comparison["store_format"] == "webdataset_streaming_v1"
    assert comparison["streaming_iterator"] == "webdataset.WebDataset"
    assert comparison["comparator_mode"] == "action_state_mask_only"
    assert comparison["comparator_valid"] is True
    assert comparison["raw_payload_hash"] == comparison["store_payload_hash"]
    assert comparison["full_training_window_supported"] is False
    assert comparison["media_payload_equivalent"] is False
    assert first_sample["actions"] == [[0.0, 0.25]]
    assert first_sample["state"] == [0.0, 1.25]
    assert first_sample["action_mask"] == [[True, True]]
    assert first_sample["sample_id"] == "sample-000000000"


def test_webdataset_streaming_tar_members_should_use_wds_basename_grouping(
    tmp_path: Path,
) -> None:
    """验证 shard 成员由 WebDataset basename grouping 组织。"""
    _dataset, store_dir = _build_streaming_store(tmp_path)

    with tarfile.open(store_dir / "shards" / "shard-000000.tar", "r") as shard:
        names = sorted(member.name for member in shard.getmembers() if member.isfile())

    assert "sample-000000000.action.npy" in names
    assert "sample-000000000.state.npy" in names
    assert "sample-000000000.action_mask.npy" in names
    assert "sample-000000000.json" in names
    assert {name.split(".", maxsplit=1)[0] for name in names} == {
        "sample-000000000",
        "sample-000000001",
        "sample-000000002",
        "sample-000000003",
    }
    assert not list((store_dir / "shards").glob("sample-*"))


def test_webdataset_streaming_backend_should_fail_closed_for_external_inputs(
    tmp_path: Path,
) -> None:
    """验证 remote URL、pipe 和越界 store/source 输入 fail-closed。"""
    module = importlib.import_module("autovla.dataloader.perf.webdataset_streaming_store")
    backend = module.WebDatasetStreamingTrainingStoreBackend()

    with pytest.raises(ValueError, match="local filesystem"):
        backend.validate_source("https://example.invalid/dataset")
    with pytest.raises(ValueError, match="local filesystem"):
        backend.validate_source("pipe:curl https://example.invalid/data.tar")
    with pytest.raises(ValueError, match="dataset root"):
        backend.validate_store_target(source=tmp_path / "dataset", output=tmp_path / "dataset")


@pytest.mark.parametrize("escape_kind", ["absolute", "parent-relative"])
def test_webdataset_streaming_read_should_reject_escaped_shard_paths(
    tmp_path: Path,
    escape_kind: str,
) -> None:
    """验证 sample index 中的 shard 路径不能逃逸 store_dir。"""
    dataset, store_dir = _build_streaming_store(tmp_path)
    original_shard = store_dir / "shards" / "shard-000000.tar"
    if escape_kind == "absolute":
        replacement = original_shard.as_posix()
    else:
        escaped_shard = store_dir.parent / "escaped-shard.tar"
        escaped_shard.write_bytes(original_shard.read_bytes())
        replacement = "../escaped-shard.tar"
    _rewrite_sample_shard_path(store_dir, replacement)

    with pytest.raises(ValueError, match="store-relative path"):
        _read_streaming_store(tmp_path, dataset=dataset, store_dir=store_dir)


@pytest.mark.parametrize("escape_kind", ["absolute", "parent-relative"])
def test_webdataset_streaming_read_should_reject_escaped_checksum_paths(
    tmp_path: Path,
    escape_kind: str,
) -> None:
    """验证 checksums.json 中的路径不能逃逸 store_dir。"""
    dataset, store_dir = _build_streaming_store(tmp_path)
    original_fields = store_dir / "index" / "fields.json"
    if escape_kind == "absolute":
        replacement = original_fields.as_posix()
    else:
        escaped_fields = store_dir.parent / "escaped-fields.json"
        escaped_fields.write_bytes(original_fields.read_bytes())
        replacement = "../escaped-fields.json"
    _rewrite_checksum_path(store_dir, key="fields", path=replacement)

    with pytest.raises(ValueError, match="store-relative path"):
        _read_streaming_store(tmp_path, dataset=dataset, store_dir=store_dir)
