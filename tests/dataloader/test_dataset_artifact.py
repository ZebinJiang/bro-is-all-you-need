"""Dataset Artifact v1 元数据契约测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from autovla.dataloader.dataset_artifact import (
    ALLOWED_STATISTICS_SCOPES,
    DatasetArtifactV1,
    FingerprintSet,
    build_fingerprint_set,
    fingerprint_payload,
    write_dataset_artifact_preview,
)


def _fingerprints(
    dataset_manifest: dict[str, object],
    modality: dict[str, object],
    transforms: dict[str, object],
    statistics: dict[str, object],
    sample_index: dict[str, object],
    episode_index: dict[str, object],
    checksums: dict[str, object],
) -> FingerprintSet:
    """构造与 Artifact 内容绑定的稳定指纹。"""
    return build_fingerprint_set(
        dataset_payload={
            "checksums": checksums,
            "dataset_manifest": dataset_manifest,
            "episode_index": episode_index,
            "modality": modality,
            "sample_index": sample_index,
        },
        transform_payload=transforms,
        statistics_payload=statistics,
    )


def _artifact(
    *,
    statistics_scope: str = "mixed",
    action_statistics_subset: dict[str, object] | None = None,
    modality: dict[str, object] | None = None,
) -> DatasetArtifactV1:
    """构造最小稳定 Artifact。"""
    dataset_manifest: dict[str, object] = {
        "dataset_id": "tiny-zjh",
        "normalized_dataset_root": "datasets/readonly/tiny-zjh",
        "source_format": "lerobot-v2",
        "statistics_scope": statistics_scope,
    }
    owned_modality: dict[str, object] = modality or {
        "action": {"dtype": "float32", "shape": [3]},
        "cameras": [],
        "language": {"tasks": [{"task_index": 0, "task": "pick"}]},
        "state": {"dtype": "float32", "shape": [2]},
    }
    transforms: dict[str, object] = {
        "preview_only": True,
        "steps": [],
    }
    statistics: dict[str, object] = {
        "action": "not_fit",
        "include_action_statistics": statistics_scope != "vision_language_only",
        "state": "not_fit",
        "statistics_scope": statistics_scope,
    }
    if action_statistics_subset is not None:
        statistics["action_statistics_subset"] = action_statistics_subset
    sample_index: dict[str, object] = {"mode": "placeholder_from_metadata"}
    episode_index: dict[str, object] = {
        "episode_count_from_metadata": 2,
        "mode": "placeholder_from_metadata",
    }
    checksums: dict[str, object] = {
        "metadata_json_sha256": "metadata-sha",
        "tasks_jsonl_sha256": "tasks-sha",
    }
    return DatasetArtifactV1(
        adapter_name="zjh-adapter",
        dataset_manifest=dataset_manifest,
        modality=owned_modality,
        transforms=transforms,
        statistics=statistics,
        sample_index=sample_index,
        episode_index=episode_index,
        checksums=checksums,
        fingerprints=_fingerprints(
            dataset_manifest,
            owned_modality,
            transforms,
            statistics,
            sample_index,
            episode_index,
            checksums,
        ),
    )


def test_should_expose_exact_statistics_scopes() -> None:
    """验证 Artifact v1 只允许三个显式统计范围。"""
    assert ALLOWED_STATISTICS_SCOPES == frozenset({"action_only", "vision_language_only", "mixed"})


def test_should_fingerprint_canonical_payload_deterministically() -> None:
    """验证字典顺序不会影响稳定指纹。"""
    left = fingerprint_payload("dataset", {"b": [2, 1], "a": {"x": "y"}})
    right = fingerprint_payload("dataset", {"a": {"x": "y"}, "b": [2, 1]})

    assert left == right
    assert len(left) == 64


def test_should_roundtrip_dataset_artifact_v1_with_episode_index(tmp_path: Path) -> None:
    """验证 Artifact v1 往返保留 episode_index。"""
    artifact = _artifact(
        action_statistics_subset={
            "feature_key": "action",
            "selection": "policy_rows",
        }
    )
    output_path = write_dataset_artifact_preview(artifact, tmp_path)
    payload = cast(dict[str, object], json.loads(output_path.read_text(encoding="utf-8")))

    loaded = DatasetArtifactV1.from_json_dict(payload)

    assert output_path.name == "dataset_artifact.json"
    assert loaded.schema_version == "autovla.dataset_artifact.v1"
    assert loaded.adapter_name == "zjh-adapter"
    assert loaded.to_json_dict() == artifact.to_json_dict()
    assert loaded.to_json_dict()["episode_index"] == {
        "episode_count_from_metadata": 2,
        "mode": "placeholder_from_metadata",
    }


def test_should_reject_removed_statistics_scope() -> None:
    """验证旧 metadata_only 统计范围不再被接受。"""
    with pytest.raises(ValueError, match="statistics_scope"):
        _artifact(statistics_scope="metadata_only")


def test_should_reject_mixed_without_action_subset() -> None:
    """验证 mixed 数据必须显式声明 action statistics 子集。"""
    with pytest.raises(ValueError, match="action_statistics_subset"):
        _artifact(statistics_scope="mixed")


def test_should_reject_vlm_action_statistics() -> None:
    """验证 vision_language_only 不能贡献 action 归一化统计。"""
    with pytest.raises(ValueError, match="vision_language_only"):
        _artifact(
            statistics_scope="vision_language_only",
            action_statistics_subset={"feature_key": "action"},
        )


def test_should_reject_action_only_without_action_modality() -> None:
    """验证 action_only 必须有 action 数据。"""
    with pytest.raises(ValueError, match="action data"):
        _artifact(statistics_scope="action_only", modality={"language": {"tasks": []}})


def test_should_reject_preview_write_under_readonly_dataset(tmp_path: Path) -> None:
    """验证预览 JSON 不允许写入 datasets/readonly。"""
    output_dir = tmp_path / "datasets" / "readonly" / "tiny-zjh"

    with pytest.raises(ValueError, match="datasets/readonly"):
        write_dataset_artifact_preview(
            _artifact(statistics_scope="action_only"),
            output_dir,
        )

    assert not output_dir.exists()
