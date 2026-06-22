"""GenesisVLA 框架输入输出契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, TypeAlias

from genesisvla.core.types.action import ActionChunk, NumericArray
from genesisvla.core.types.sample import BatchSample

LossValue: TypeAlias = float | NumericArray


def _empty_tensors() -> dict[str, NumericArray]:
    """返回空的命名数组映射。"""
    return {}


def _empty_metadata() -> dict[str, Any]:
    """返回空的元数据映射。"""
    return {}


@dataclass(frozen=True, slots=True)
class ModelInput:
    """表示模型或策略调用的最小输入。

    Args:
        batch: 原始样本批。
        tensors: 已由上游转换出的命名数值数组映射。
        metadata: 输入级透传元数据。
    """

    batch: BatchSample
    tensors: Mapping[str, NumericArray] = field(default_factory=_empty_tensors)
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)


@dataclass(frozen=True, slots=True)
class FrameworkOutput:
    """表示框架前向结果的最小结构。

    Args:
        loss: 可选总损失,M1 中允许浮点数或 numpy 数组。
        losses: 命名损失映射。
        metrics: 命名标量指标映射。
        action_pred: 可选预测动作块。
    """

    loss: LossValue | None
    losses: Mapping[str, LossValue]
    metrics: Mapping[str, float]
    action_pred: ActionChunk | None = None
