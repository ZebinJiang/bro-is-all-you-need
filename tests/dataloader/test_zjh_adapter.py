"""ZJH metadata-only adapter 测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from autovla.dataloader.adapters import get_dataset_adapter, list_dataset_adapter_names
from autovla.dataloader.adapters.zjh import (
    ZJH_ADAPTER_NAME,
    ZJH_ADAPTER_VERSION,
    ZJH_SOURCE_FORMAT,
    ZjhAdapter,
    build_zjh_artifact_preview,
    read_zjh_metadata,
    write_zjh_artifact_preview,
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


def _tiny_info(*, include_action: bool = True) -> dict[str, object]:
    """构造 LeRobot-v2-compatible tiny metadata。"""
    features: dict[str, object] = {
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
    }
    if include_action:
        features["action"] = {
            "dtype": "float32",
            "names": ["left_x", "right_x", "grip"],
            "shape": [3],
        }
    return {
        "chunks_size": 1000,
        "codebase_version": "v2.1",
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "features": features,
        "fps": 30,
        "robot_type": "demo_bot",
        "splits": {"train": "0:2"},
        "total_chunks": 1,
        "total_episodes": 2,
        "total_frames": 4,
        "total_tasks": 1,
        "total_videos": 6,
        "video_path": (
            "videos/chunk-{episode_chunk:03d}/{video_key}/" "episode_{episode_index:06d}.mp4"
        ),
    }


def _action_subset() -> dict[str, object]:
    """返回 mixed 数据的 action 统计子集声明。"""
    return {
        "feature_key": "action",
        "reason": "policy action rows only",
        "selection": "train_split_action_rows",
    }


def _write_tiny_zjh_metadata(root: Path, info: dict[str, object] | None = None) -> None:
    """只写 tiny metadata/info/tasks, 不写 parquet 或媒体。"""
    payload = _tiny_info() if info is None else info
    (root / "meta").mkdir(parents=True)
    encoded = json.dumps(payload, sort_keys=True)
    (root / "metadata.json").write_text(encoded, encoding="utf-8")
    (root / "meta" / "info.json").write_text(encoded, encoding="utf-8")
    (root / "meta" / "tasks.jsonl").write_text(
        json.dumps({"task_index": 0, "task": "pick the tiny object"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_should_expose_adapter_object_interface(tmp_path: Path) -> None:
    """验证 zjh-adapter 暴露对象接口字段和方法。"""
    dataset_root = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset_root)
    adapter = ZjhAdapter()

    metadata = adapter.inspect(dataset_root, project_root=tmp_path)
    plan = adapter.plan_conversion(
        dataset_root,
        tmp_path / "out",
        project_root=tmp_path,
        action_statistics_subset=_action_subset(),
    )

    assert adapter.adapter_name == ZJH_ADAPTER_NAME
    assert adapter.adapter_version == ZJH_ADAPTER_VERSION
    assert adapter.source_format == ZJH_SOURCE_FORMAT
    assert adapter.validate(dataset_root, project_root=tmp_path) == metadata
    assert plan["conversion"] == "dry_run_metadata_preview_only"


def test_should_lookup_zjh_adapter_from_registry() -> None:
    """验证 zjh-adapter 可通过数据适配器注册表查询。"""
    adapter = get_dataset_adapter("zjh-adapter")

    assert list_dataset_adapter_names() == ("zjh-adapter",)
    assert adapter.adapter_name == "zjh-adapter"


def test_should_build_mixed_metadata_only_zjh_preview(tmp_path: Path) -> None:
    """验证 adapter 只依赖 tiny metadata 构造 mixed 预览。"""
    dataset_root = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset_root)

    metadata = read_zjh_metadata(dataset_root, project_root=tmp_path)
    artifact = build_zjh_artifact_preview(
        metadata,
        statistics_scope="mixed",
        action_statistics_subset=_action_subset(),
    )
    output_path = write_zjh_artifact_preview(
        dataset_root,
        tmp_path / "out",
        project_root=tmp_path,
        statistics_scope="mixed",
        action_statistics_subset=_action_subset(),
    )
    artifact_payload = artifact.to_json_dict()
    manifest = cast(dict[str, object], artifact_payload["dataset_manifest"])
    statistics = cast(dict[str, object], artifact_payload["statistics"])
    modality = cast(dict[str, object], artifact_payload["modality"])
    action = cast(dict[str, object], modality["action"])
    state = cast(dict[str, object], modality["state"])
    cameras = cast(list[object], modality["cameras"])
    episode_index = cast(dict[str, object], artifact_payload["episode_index"])
    written = cast(dict[str, object], json.loads(output_path.read_text(encoding="utf-8")))
    written_fingerprints = cast(dict[str, object], written["fingerprints"])

    assert artifact.adapter_name == ZJH_ADAPTER_NAME
    assert manifest["source_uri"] == "tiny_zjh"
    assert manifest["schema_version"] == "autovla.dataset_manifest.v1"
    assert manifest["dataset_fingerprint"]
    assert manifest["transform_fingerprint"]
    assert manifest["statistics_fingerprint"]
    assert manifest["sample_count"] == 4
    assert manifest["episode_count"] == 2
    assert manifest["statistics_scope"] == "mixed"
    assert statistics["statistics_scope"] == "mixed"
    assert statistics["action_statistics_subset"] == _action_subset()
    assert action["shape"] == [3]
    assert state["shape"] == [2]
    assert modality["schema_version"] == "autovla.modality.v1"
    assert modality["action_keys"] == ["left_x", "right_x", "grip"]
    assert modality["state_keys"] == ["joint_a", "joint_b"]
    assert modality["language_keys"] == ["task"]
    assert modality["rate_hz"] == 30
    assert modality["robot_embodiment"] == "demo_bot"
    assert modality["normalization_policy"] == {
        "fit": "not_performed",
        "statistics_scope": "declared_by_statistics_plan",
    }
    assert len(cameras) == 3
    assert episode_index["episode_count_from_metadata"] == 2
    assert written_fingerprints["dataset_fingerprint"]
    assert not (dataset_root / "data").exists()
    assert not (dataset_root / "videos").exists()


def test_should_roundtrip_episode_index_from_adapter(tmp_path: Path) -> None:
    """验证 adapter 产物可往返保留 episode_index。"""
    dataset_root = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset_root)
    adapter = ZjhAdapter()
    artifact = adapter.emit_artifact(
        adapter.inspect(dataset_root, project_root=tmp_path),
        action_statistics_subset=_action_subset(),
    )

    loaded = type(artifact).from_json_dict(artifact.to_json_dict())

    assert loaded.to_json_dict()["episode_index"] == artifact.to_json_dict()["episode_index"]


def test_should_reject_mixed_without_action_subset(tmp_path: Path) -> None:
    """验证 mixed 数据必须显式声明 action 统计子集。"""
    dataset_root = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset_root)
    metadata = read_zjh_metadata(dataset_root, project_root=tmp_path)

    with pytest.raises(ValueError, match="action_statistics_subset"):
        build_zjh_artifact_preview(metadata, statistics_scope="mixed")


def test_should_reject_dialogue_action_statistics(tmp_path: Path) -> None:
    """验证 dialogue/VLM-only 数据不能贡献 action 统计。"""
    dataset_root = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset_root)
    metadata = read_zjh_metadata(dataset_root, project_root=tmp_path)

    with pytest.raises(ValueError, match="vision_language_only"):
        build_zjh_artifact_preview(
            metadata,
            statistics_scope="vision_language_only",
            action_statistics_subset=_action_subset(),
        )


def test_should_reject_action_only_without_action_feature(tmp_path: Path) -> None:
    """验证 action_only 统计必须有 action 特征。"""
    dataset_root = tmp_path / "tiny_zjh"
    info = _tiny_info(include_action=False)
    _write_tiny_zjh_metadata(dataset_root, info)

    with pytest.raises(ValueError, match="action"):
        read_zjh_metadata(dataset_root, project_root=tmp_path)


def test_should_allow_action_only_with_action_feature(tmp_path: Path) -> None:
    """验证 action_only 统计范围可用于有 action 的 metadata。"""
    dataset_root = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset_root)
    metadata = read_zjh_metadata(dataset_root, project_root=tmp_path)
    artifact = build_zjh_artifact_preview(metadata, statistics_scope="action_only")
    statistics = cast(dict[str, object], artifact.to_json_dict()["statistics"])

    assert statistics["statistics_scope"] == "action_only"
    assert statistics["include_action_statistics"] is True


def test_should_reject_duplicate_metadata_checksum_mismatch(tmp_path: Path) -> None:
    """验证 metadata.json 和 meta/info.json 不一致时失败。"""
    dataset_root = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset_root)
    changed = _tiny_info()
    changed["robot_type"] = "other_bot"
    (dataset_root / "meta" / "info.json").write_text(
        json.dumps(changed, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="checksum mismatch"):
        read_zjh_metadata(dataset_root, project_root=tmp_path)


def test_should_reject_preview_write_inside_dataset_root(tmp_path: Path) -> None:
    """验证 adapter 预览不会写回数据集根目录。"""
    dataset_root = tmp_path / "tiny_zjh"
    _write_tiny_zjh_metadata(dataset_root)

    with pytest.raises(ValueError, match="dataset_root"):
        write_zjh_artifact_preview(
            dataset_root,
            dataset_root / "preview",
            project_root=tmp_path,
            action_statistics_subset=_action_subset(),
        )

    assert not (dataset_root / "preview").exists()
