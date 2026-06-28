"""M2 tiny fixture 文件格式契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import autovla.testing.fixtures as fixture_module


def test_should_generate_real_lerobot_v3_fixture_files(tmp_path: Path) -> None:
    """验证 tiny LeRobot fixture 生成真实目录和 parquet 数据分片。"""
    fixture = fixture_module.tiny_lerobot_fixture(tmp_path / "tiny_lerobot_v3")

    assert fixture.root == tmp_path / "tiny_lerobot_v3"
    assert fixture.provenance["source"] == "generated"
    assert fixture.provenance["format"] == "lerobot-v3"
    assert fixture.provenance["real_format"] == "true"
    assert fixture.provenance["release_tag"] == "v0.5.1"
    assert fixture.provenance["upstream_revision"] == "1396b9fab7aecddd10006c33c47a487ffdcb54b4"
    assert (fixture.root / "meta/info.json").is_file()
    assert (fixture.root / "meta/tasks.jsonl").is_file()
    assert (fixture.root / "meta/stats.json").is_file()
    assert (fixture.root / "meta/episodes/chunk-000/file-000.parquet").is_file()
    assert (fixture.root / "data/chunk-000/file-000.parquet").is_file()

    info = json.loads((fixture.root / "meta/info.json").read_text(encoding="utf-8"))
    summary = fixture_module.describe_parquet_file(fixture.root / "data/chunk-000/file-000.parquet")

    assert info["codebase_version"] == "v3.0"
    assert info["total_frames"] == 4
    assert info["total_episodes"] == 2
    assert summary.row_count == 4
    assert summary.column_types["observation.state"] == "fixed_size_list<float32>[3]"
    assert summary.column_types["action"] == "fixed_size_list<float32>[3]"
    assert summary.column_types["action_mask"] == "fixed_size_list<bool>[3]"
    assert len(fixture.samples) == 2
    assert fixture.samples[0].actions is not None
    np.testing.assert_array_equal(
        fixture.samples[0].metadata["action_mask"],
        np.asarray([[True, True, False], [True, True, False]], dtype=np.bool_),
    )


def test_should_reload_lerobot_v3_fixture_deterministically(tmp_path: Path) -> None:
    """验证真实 LeRobot-format fixture 可从磁盘确定性重载为 RawSample。"""
    fixture = fixture_module.tiny_lerobot_fixture(tmp_path / "tiny_lerobot_v3")
    reloaded = fixture_module.load_tiny_lerobot_fixture(fixture.root)

    assert reloaded.root == fixture.root
    assert reloaded.provenance == fixture.provenance
    assert len(reloaded.samples) == len(fixture.samples)
    for left, right in zip(fixture.samples, reloaded.samples, strict=True):
        assert left.language == right.language
        assert left.robot_tag == right.robot_tag
        assert right.actions is not None
        assert left.actions is not None
        assert right.state is not None
        assert left.state is not None
        np.testing.assert_array_equal(right.actions, left.actions)
        np.testing.assert_array_equal(right.state, left.state)
        np.testing.assert_array_equal(right.metadata["action_mask"], left.metadata["action_mask"])


def test_should_reject_malformed_lerobot_metadata(tmp_path: Path) -> None:
    """验证 LeRobot metadata 和 data 关系不完整时失败。"""
    fixture = fixture_module.tiny_lerobot_fixture(tmp_path / "tiny_lerobot_v3")
    info_path = fixture.root / "meta/info.json"
    info = json.loads(info_path.read_text(encoding="utf-8"))
    info["total_frames"] = 99
    info_path.write_text(json.dumps(info, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="total_frames"):
        fixture_module.load_tiny_lerobot_fixture(fixture.root)


def test_should_reject_missing_lerobot_data_shard(tmp_path: Path) -> None:
    """验证缺少 LeRobot data shard 时失败。"""
    fixture = fixture_module.tiny_lerobot_fixture(tmp_path / "tiny_lerobot_v3")
    (fixture.root / "data/chunk-000/file-000.parquet").unlink()

    with pytest.raises(FileNotFoundError, match=r"data/chunk-000/file-000\.parquet"):
        fixture_module.load_tiny_lerobot_fixture(fixture.root)


def test_should_generate_real_parquet_fixture_file(tmp_path: Path) -> None:
    """验证 tiny Parquet fixture 是实际 parquet 文件而不是内存字典。"""
    fixture = fixture_module.tiny_parquet_fixture(tmp_path / "tiny.parquet")

    assert fixture.path == tmp_path / "tiny.parquet"
    assert fixture.path.is_file()
    assert fixture.provenance["source"] == "generated"
    assert fixture.provenance["format"] == "parquet"
    assert fixture.provenance["real_format"] == "true"
    assert len(fixture.samples) == 2

    summary = fixture_module.describe_parquet_file(fixture.path)
    assert summary.row_count == 4
    assert summary.column_types["state"] == "fixed_size_list<float32>[3]"
    assert summary.column_types["action"] == "fixed_size_list<float32>[3]"
    assert summary.column_types["action_mask"] == "fixed_size_list<bool>[3]"
    assert fixture.path.read_bytes()[-4:] == b"PAR1"


def test_should_reload_parquet_fixture_and_validate_shape(tmp_path: Path) -> None:
    """验证真实 parquet fixture 的 dtype、shape、行数和 null 策略。"""
    fixture = fixture_module.tiny_parquet_fixture(tmp_path / "tiny.parquet")
    reloaded = fixture_module.load_tiny_parquet_fixture(fixture.path)

    assert reloaded.path == fixture.path
    assert reloaded.provenance == fixture.provenance
    assert len(reloaded.samples) == 2
    for sample in reloaded.samples:
        assert sample.actions is not None
        assert sample.actions.shape == (2, 3)
        assert sample.state is not None
        assert sample.state.shape == (3,)
        assert sample.metadata["action_mask"].shape == (2, 3)


def test_should_reject_parquet_missing_required_column(tmp_path: Path) -> None:
    """验证缺少必需 parquet 列时失败。"""
    fixture = fixture_module.tiny_parquet_fixture(tmp_path / "tiny.parquet")
    fixture_module.rewrite_parquet_without_column(fixture.path, "action")

    with pytest.raises(ValueError, match="action"):
        fixture_module.load_tiny_parquet_fixture(fixture.path)


def test_should_reject_parquet_wrong_action_mask_dtype(tmp_path: Path) -> None:
    """验证 action_mask 不允许用整型 parquet 列冒充。"""
    fixture = fixture_module.tiny_parquet_fixture(tmp_path / "tiny.parquet")
    fixture_module.rewrite_parquet_action_mask_as_int(fixture.path)

    with pytest.raises(ValueError, match="action_mask"):
        fixture_module.load_tiny_parquet_fixture(fixture.path)


def test_should_reject_corrupt_parquet_footer(tmp_path: Path) -> None:
    """验证损坏 parquet footer 时失败并保持错误清晰。"""
    fixture = fixture_module.tiny_parquet_fixture(tmp_path / "tiny.parquet")
    fixture.path.write_bytes(fixture.path.read_bytes()[:-4])

    with pytest.raises(ValueError, match="parquet"):
        fixture_module.load_tiny_parquet_fixture(fixture.path)
