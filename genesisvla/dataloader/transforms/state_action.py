"""状态与动作归一化转换。"""

from __future__ import annotations

from dataclasses import replace

from genesisvla.core.types import NumericArray, RawSample
from genesisvla.dataloader.statistics import DatasetStatistics, FeatureStatistics


def _require_statistics(
    statistics: FeatureStatistics | None,
    field_name: str,
) -> FeatureStatistics:
    """读取字段统计量,缺失时抛出清晰错误。"""
    if statistics is None:
        raise ValueError(f"{field_name} statistics are required")
    return statistics


def _normalize_feature(
    values: NumericArray,
    statistics: FeatureStatistics,
    field_name: str,
) -> NumericArray:
    """使用 ``(x - mean) / std`` 归一化数组。"""
    _validate_value_shape(values, statistics, field_name)
    return (values - statistics.mean) / statistics.std


def _unnormalize_feature(
    values: NumericArray,
    statistics: FeatureStatistics,
    field_name: str,
) -> NumericArray:
    """使用 ``x * std + mean`` 反归一化数组。"""
    _validate_value_shape(values, statistics, field_name)
    return values * statistics.std + statistics.mean


def _validate_value_shape(
    values: NumericArray,
    statistics: FeatureStatistics,
    field_name: str,
) -> None:
    """校验样本字段和统计量维度一致。"""
    feature_dim = statistics.mean.shape[0]
    if field_name == "state":
        if values.ndim != 1 or values.shape[0] != feature_dim:
            raise ValueError(f"state shape must be ({feature_dim},), got {tuple(values.shape)}")
        return
    if values.ndim != 2 or values.shape[1] != feature_dim:
        raise ValueError(
            f"actions shape must be (horizon, {feature_dim}), got {tuple(values.shape)}"
        )


class StateActionNormalize:
    """按数据集统计量归一化 RawSample 的状态和动作。

    Args:
        statistics: 数据集统计量。
        normalize_state: 是否归一化 ``sample.state``。
        normalize_actions: 是否归一化 ``sample.actions``。
    """

    def __init__(
        self,
        statistics: DatasetStatistics,
        *,
        normalize_state: bool = True,
        normalize_actions: bool = True,
    ) -> None:
        """保存统计量和字段开关。"""
        self.statistics = statistics
        self.normalize_state = normalize_state
        self.normalize_actions = normalize_actions

    def __call__(self, sample: RawSample) -> RawSample:
        """返回归一化后的样本,不原地修改输入数组。"""
        state = sample.state
        actions = sample.actions

        if self.normalize_state:
            if state is None:
                raise ValueError("state is required for normalization")
            state_stats = _require_statistics(self.statistics.state, "state")
            state = _normalize_feature(state, state_stats, "state")

        if self.normalize_actions:
            if actions is None:
                raise ValueError("actions are required for normalization")
            action_stats = _require_statistics(self.statistics.action, "actions")
            actions = _normalize_feature(actions, action_stats, "actions")

        if state is sample.state and actions is sample.actions:
            return sample
        return replace(sample, state=state, actions=actions)


class StateActionUnnormalize:
    """按数据集统计量反归一化 RawSample 的状态和动作。"""

    def __init__(
        self,
        statistics: DatasetStatistics,
        *,
        unnormalize_state: bool = True,
        unnormalize_actions: bool = True,
    ) -> None:
        """保存统计量和字段开关。"""
        self.statistics = statistics
        self.unnormalize_state = unnormalize_state
        self.unnormalize_actions = unnormalize_actions

    def __call__(self, sample: RawSample) -> RawSample:
        """返回反归一化后的样本,不原地修改输入数组。"""
        state = sample.state
        actions = sample.actions

        if self.unnormalize_state:
            if state is None:
                raise ValueError("state is required for unnormalization")
            state_stats = _require_statistics(self.statistics.state, "state")
            state = _unnormalize_feature(state, state_stats, "state")

        if self.unnormalize_actions:
            if actions is None:
                raise ValueError("actions are required for unnormalization")
            action_stats = _require_statistics(self.statistics.action, "actions")
            actions = _unnormalize_feature(actions, action_stats, "actions")

        if state is sample.state and actions is sample.actions:
            return sample
        return replace(sample, state=state, actions=actions)
