"""GenesisVLA 动作契约测试。"""

import numpy as np
import pytest


def test_should_validate_action_chunk_shape() -> None:
    """验证动作块的形状字段与数组形状一致。"""
    from genesisvla.core.types.action import ActionChunk

    chunk = ActionChunk(
        values=np.zeros((2, 7), dtype=np.float32),
        mask=None,
        horizon=2,
        action_dim=7,
        normalized=True,
    )

    assert chunk.horizon == 2
    assert chunk.action_dim == 7
    assert chunk.values.shape == (2, 7)


def test_should_reject_invalid_action_mask_shape() -> None:
    """验证动作掩码形状不一致时会被拒绝。"""
    from genesisvla.core.types.action import ActionChunk

    with pytest.raises(ValueError):
        ActionChunk(
            values=np.zeros((2, 7), dtype=np.float32),
            mask=np.ones((2, 6), dtype=bool),
            horizon=2,
            action_dim=7,
            normalized=True,
        )


def test_should_create_action_space() -> None:
    """验证动作空间会保留维度、归一化标记和名称。"""
    from genesisvla.core.types.action import ActionSpace

    space = ActionSpace(horizon=2, action_dim=7, normalized=True, names=("x", "y"))

    assert space.horizon == 2
    assert space.action_dim == 7
    assert space.normalized is True
    assert space.names == ("x", "y")
