"""数据集统计量结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from genesisvla.core.types import NumericArray

SCHEMA_VERSION = "1.0"
STD_EPSILON = 1e-8


def _empty_metadata() -> dict[str, Any]:
    """返回空的统计量元数据映射。"""
    return {}


@dataclass(frozen=True, slots=True)
class FeatureStatistics:
    """描述单个数值特征组的均值和标准差。

    Args:
        mean: 一维均值数组。
        std: 一维标准差数组,每个元素必须大于 ``STD_EPSILON``。
        names: 可选维度名称,数量不能超过特征维度。
    """

    mean: NumericArray
    std: NumericArray
    names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """校验统计量形状、有限性和标准差安全性。"""
        mean = np.asarray(self.mean, dtype=np.float32)
        std = np.asarray(self.std, dtype=np.float32)
        if mean.ndim != 1:
            raise ValueError("mean must be a 1-D array")
        if std.ndim != 1:
            raise ValueError("std must be a 1-D array")
        if mean.shape != std.shape:
            raise ValueError(f"mean/std shape mismatch: {mean.shape} vs {std.shape}")
        if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(std)):
            raise ValueError("mean and std must contain finite values")
        if np.any(std <= STD_EPSILON):
            raise ValueError("std values must be greater than epsilon")
        if len(self.names) > mean.shape[0]:
            raise ValueError("names length must not exceed feature dimension")
        object.__setattr__(self, "mean", mean)
        object.__setattr__(self, "std", std)
        object.__setattr__(self, "names", tuple(self.names))


@dataclass(frozen=True, slots=True)
class DatasetStatistics:
    """描述一个数据集的状态和动作统计量。

    Args:
        sample_count: 用于估计统计量的样本数,必须为正。
        state: 可选状态统计量。
        action: 可选动作统计量。
        metadata: 小型 JSON 友好元数据。
        schema_version: schema 版本,Tranche A 仅支持 ``"1.0"``。
    """

    sample_count: int
    state: FeatureStatistics | None = None
    action: FeatureStatistics | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验数据集统计量的版本和必需字段。"""
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if self.state is None and self.action is None:
            raise ValueError("at least one of state or action statistics is required")
        object.__setattr__(self, "metadata", dict(self.metadata))
