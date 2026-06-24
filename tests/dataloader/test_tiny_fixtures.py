"""M2 tiny fixture 契约测试。"""

from __future__ import annotations

import numpy as np

from genesisvla.testing.fixtures import tiny_lerobot_fixture, tiny_parquet_fixture


def test_should_create_deterministic_tiny_lerobot_fixture() -> None:
    """验证 tiny LeRobot fixture 小型、确定、字段齐全。"""
    left = tiny_lerobot_fixture()
    right = tiny_lerobot_fixture()

    assert len(left.samples) == 2
    assert left.provenance["source"] == "generated"
    assert left.provenance["real_format"] == "false"
    for sample in left.samples:
        assert sample.images["front"].shape == (2, 2, 3)
        assert sample.language
        assert sample.robot_tag == "tiny-arm"
        assert sample.state is not None
        assert sample.actions is not None
        assert "action_mask" in sample.metadata
    assert left.samples[0].actions is not None
    assert right.samples[0].actions is not None
    np.testing.assert_array_equal(left.samples[0].actions, right.samples[0].actions)


def test_should_create_deterministic_tiny_parquet_fixture() -> None:
    """验证 tiny Parquet fixture 使用内存记录表达, 不需要外部下载。"""
    fixture = tiny_parquet_fixture()

    assert fixture.provenance["format"] == "parquet-like-in-memory"
    assert fixture.provenance["real_format"] == "false"
    assert len(fixture.records) == 2
    assert fixture.records[0]["robot_tag"] == "tiny-arm"
    assert fixture.records[0]["language"]
    assert "padding_mask" in fixture.records[1]
