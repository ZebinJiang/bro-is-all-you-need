"""M2 状态/动作归一化薄适配器。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import numpy as np
from numpy.typing import NDArray

from autovla.core.semantics import AlignmentMode, AlignmentPolicy, TensorLayout
from autovla.core.types import RawSample
from autovla.data.normalization import FeatureStatistics, StatisticsNormalizationTransform
from autovla.dataloader.contracts import TransformSpec, strict_bool_array


def _action_mask(
    actions: NDArray[np.generic], metadata: Mapping[str, object]
) -> NDArray[np.bool_] | None:
    """读取旧 metadata 的 ``[D]`` 或 ``[T,D]`` action mask。"""
    raw_mask = metadata.get("action_mask")
    if raw_mask is None:
        return None
    mask = strict_bool_array(raw_mask, name="action_mask")
    if mask.ndim == 1 and mask.shape[0] == actions.shape[-1]:
        return np.broadcast_to(mask, actions.shape).copy()
    if mask.ndim == 2 and mask.shape == actions.shape:
        return mask.copy()
    raise ValueError("action_mask must have shape [D] or [T,D]")


def _transform(
    values: object,
    statistics: FeatureStatistics,
    *,
    layout: TensorLayout,
    inverse: bool,
) -> NDArray[np.float32]:
    """使用显式旧字段布局调用规范统计执行器。"""
    alignment = (
        AlignmentPolicy(AlignmentMode.EXACT)
        if statistics.layout == layout
        else AlignmentPolicy(AlignmentMode.BROADCAST)
    )
    transform = StatisticsNormalizationTransform(
        statistics,
        value_layout=layout,
        alignment=alignment,
    )
    try:
        return transform.denormalize(values) if inverse else transform.normalize(values)
    except ValueError as exc:
        raise ValueError(f"feature dimension/layout alignment failed: {exc}") from exc


class _StateActionBase:
    """共享旧 RawSample 适配逻辑。"""

    inverse = False

    def __init__(
        self,
        *,
        state: FeatureStatistics | None = None,
        action: FeatureStatistics | None = None,
    ) -> None:
        self.state = state
        self.action = action

    def __call__(self, sample: RawSample) -> RawSample:
        """变换 state/actions 并保留 action mask 为独立输入语义。"""
        state = sample.state
        actions = sample.actions
        if self.state is not None:
            if state is None:
                raise ValueError("state is required for state normalization")
            state = _transform(
                state,
                self.state,
                layout=TensorLayout.feature(),
                inverse=self.inverse,
            )
        if self.action is not None:
            if actions is None:
                raise ValueError("actions are required for action normalization")
            candidate = _transform(
                actions,
                self.action,
                layout=TensorLayout.time_feature(),
                inverse=self.inverse,
            )
            mask = _action_mask(np.asarray(actions), sample.metadata)
            actions = (
                candidate if mask is None else np.where(mask, candidate, actions).astype(np.float32)
            )
        return replace(sample, state=state, actions=actions)


class StateActionNormalize(_StateActionBase):
    """旧正向归一化名称。"""

    def to_spec(self) -> TransformSpec:
        """返回旧注册表可重建配置。"""
        return TransformSpec(
            name="state_action_normalize",
            params={
                "state": self.state.to_json_dict() if self.state is not None else None,
                "action": self.action.to_json_dict() if self.action is not None else None,
            },
        )


class StateActionUnnormalize(_StateActionBase):
    """旧逆向归一化名称。"""

    inverse = True

    def to_spec(self) -> TransformSpec:
        """返回旧注册表可重建配置。"""
        return TransformSpec(
            name="state_action_unnormalize",
            params={
                "state": self.state.to_json_dict() if self.state is not None else None,
                "action": self.action.to_json_dict() if self.action is not None else None,
            },
        )


__all__ = ["StateActionNormalize", "StateActionUnnormalize"]
