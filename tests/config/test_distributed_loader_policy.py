"""collective loader 分区配置的 fail-closed 测试。"""

from __future__ import annotations

import pytest

from autovla.config.schema.data import validate_collective_loader_policy


def test_collective_map_rejects_only_sample_repetition() -> None:
    """map collective 接受可证明 exact/裁尾计划并拒绝重复补齐。"""

    validate_collective_loader_policy("map", "drop_global_tail")
    validate_collective_loader_policy("map", "exact_no_pad")
    with pytest.raises(ValueError, match="must not use pad_repeat"):
        validate_collective_loader_policy("map", "pad_repeat")


def test_collective_streaming_requires_exact_nominal_plan() -> None:
    """streaming collective 保留不补样本的 exact 计划。"""

    validate_collective_loader_policy("streaming", "exact_no_pad")
    with pytest.raises(ValueError, match="requires exact_no_pad"):
        validate_collective_loader_policy("streaming", "drop_global_tail")
