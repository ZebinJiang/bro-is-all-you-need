"""GenesisVLA 动作契约测试。"""

from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray

from genesisvla.core.types.action import ActionMask


def _invalid_action_mask_for_runtime_probe() -> ActionMask:
    """构造静态契约外的掩码,仅用于验证运行时拒绝逻辑。"""
    invalid_mask: NDArray[np.float32] = np.ones((2, 7), dtype=np.float32)
    return cast(ActionMask, invalid_mask)


def test_should_validate_action_chunk_shape() -> None:
    """验证动作块的形状字段与数组形状一致。"""
    from genesisvla.core.types.action import ActionChunk

    values = np.zeros((2, 7), dtype=np.float32)
    chunk = ActionChunk(
        values=values,
        mask=None,
        horizon=2,
        action_dim=7,
        normalized=True,
    )

    values[0, 0] = 42.0
    assert chunk.horizon == 2
    assert chunk.action_dim == 7
    assert chunk.values.shape == (2, 7)
    assert chunk.values[0, 0] == 0.0
    assert chunk.values.flags.writeable is False


def test_should_own_action_mask_copy() -> None:
    """验证动作掩码会复制并设为只读。"""
    from genesisvla.core.types.action import ActionChunk

    mask = np.ones((2, 7), dtype=bool)
    chunk = ActionChunk(
        values=np.zeros((2, 7), dtype=np.float32),
        mask=mask,
        horizon=2,
        action_dim=7,
        normalized=True,
    )

    assert chunk.mask is not None
    mask[0, 0] = False
    assert bool(chunk.mask[0, 0]) is True
    assert chunk.mask.flags.writeable is False


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

    names = ("x", "y", "z", "roll", "pitch", "yaw", "gripper")
    space = ActionSpace(horizon=2, action_dim=7, normalized=True, names=names)

    assert space.horizon == 2
    assert space.action_dim == 7
    assert space.normalized is True
    assert space.names == names


def test_should_reject_non_bool_action_mask() -> None:
    """验证动作掩码必须是 bool 类型。"""
    from genesisvla.core.types.action import ActionChunk

    with pytest.raises(ValueError, match=r"mask.*bool"):
        ActionChunk(
            values=np.zeros((2, 7), dtype=np.float32),
            mask=_invalid_action_mask_for_runtime_probe(),
            horizon=2,
            action_dim=7,
            normalized=True,
        )


def test_should_reject_non_finite_action_values() -> None:
    """验证动作数值必须有限。"""
    from genesisvla.core.types.action import ActionChunk

    values = np.zeros((2, 7), dtype=np.float32)
    values[0, 0] = np.nan

    with pytest.raises(ValueError, match="finite"):
        ActionChunk(values=values, mask=None, horizon=2, action_dim=7, normalized=True)


def test_should_reject_invalid_action_names() -> None:
    """验证动作维度名称必须非空、唯一且数量等于动作维度。"""
    from genesisvla.core.types.action import ActionSpace

    with pytest.raises(ValueError, match="names length"):
        ActionSpace(horizon=2, action_dim=3, normalized=True, names=("x", "y"))
    with pytest.raises(ValueError, match="must not be empty"):
        ActionSpace(horizon=2, action_dim=2, normalized=True, names=("x", ""))
    with pytest.raises(ValueError, match="unique"):
        ActionSpace(horizon=2, action_dim=2, normalized=True, names=("x", "x"))
