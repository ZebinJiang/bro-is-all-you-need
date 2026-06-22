"""GenesisVLA 原始样本与批样本契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from genesisvla.core.types.action import ImageLike, NumericArray


def _empty_metadata() -> dict[str, Any]:
    """返回空的元数据映射。"""
    return {}


@dataclass(frozen=True, slots=True)
class RawSample:
    """表示进入 GenesisVLA 管线前的单条多模态样本。

    Args:
        images: 按模态名索引的图像数组映射,至少包含一个模态。
        language: 样本对应的语言指令,去除空白后不能为空。
        actions: 可选二维动作数组,形状为 ``(horizon, action_dim)``。
        state: 可选机器人状态数组,存在时至少是一维数组。
        robot_tag: 机器人或数据来源标识,去除空白后不能为空。
        metadata: 透传元数据。该映射按拥有输入处理,不做深拷贝。
    """

    images: Mapping[str, ImageLike]
    language: str
    actions: NumericArray | None
    state: NumericArray | None
    robot_tag: str
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        """校验样本字段满足 M1 核心契约。"""
        if not self.images:
            raise ValueError("images must not be empty")
        if not self.language.strip():
            raise ValueError("language must not be empty")
        if not self.robot_tag.strip():
            raise ValueError("robot_tag must not be empty")
        if self.actions is not None and self.actions.ndim != 2:
            raise ValueError("action shape must be 2-D (horizon, action_dim)")
        if self.state is not None and self.state.ndim < 1:
            raise ValueError("state must be at least 1-D")


@dataclass(frozen=True, slots=True)
class BatchSample:
    """表示由多条原始样本组成的批。

    Args:
        samples: 非空样本元组。
        metadata: 批级透传元数据。该映射按拥有输入处理,不做深拷贝。
    """

    samples: tuple[RawSample, ...]
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        """校验批样本不能为空。"""
        if not self.samples:
            raise ValueError("samples must not be empty")

    @property
    def batch_size(self) -> int:
        """返回批内样本数量。"""
        return len(self.samples)
