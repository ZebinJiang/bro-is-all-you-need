"""R3 秩感知统计量和 NumPy 执行测试。"""

from __future__ import annotations

import json

import numpy as np
import pytest

from autovla.core.semantics import AlignmentMode, AlignmentPolicy, TensorLayout
from autovla.data.normalization import (
    FeatureNormalizationStatistics,
    FeatureStatistics,
    NormalizationStatistics,
    StatisticsNormalizationTransform,
)


def test_should_construct_and_serialize_all_supported_statistics_layouts() -> None:
    """验证标量、``[D]``、``[T]``、``[T,D]`` 和 embodiment 映射。"""
    scalar = FeatureStatistics(
        method="mean_std",
        layout=TensorLayout.scalar(),
        mean=np.asarray(1.0),
        std=np.asarray(2.0),
    )
    vector = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([1.0, 2.0]),
        std=np.asarray([2.0, 4.0]),
        names=("x", "y"),
    )
    temporal = FeatureStatistics(
        method="min_max",
        layout=TensorLayout.time(),
        minimum=np.asarray([0.0, 1.0]),
        maximum=np.asarray([1.0, 3.0]),
    )
    per_horizon = FeatureStatistics(
        method="quantile",
        layout=TensorLayout.time_feature(),
        lower_quantile=np.asarray([[0.0, 1.0], [2.0, 3.0]]),
        upper_quantile=np.asarray([[1.0, 3.0], [4.0, 7.0]]),
        valid_mask=np.asarray([True, False]),
        valid_mask_layout=TensorLayout.time(),
        names=("joint", "gripper"),
    )
    collection = NormalizationStatistics(
        {"state": vector, "scalar": scalar, "time": temporal},
        embodiments={"arm-a": {"action": per_horizon}},
    )

    payload = collection.to_json_dict()
    json.dumps(payload, allow_nan=False)
    restored = NormalizationStatistics.from_json_dict(payload)

    assert restored.fingerprint == collection.fingerprint
    restored_action = restored.for_feature("action", embodiment="arm-a")
    assert restored_action.layout.axes == TensorLayout.time_feature().axes
    assert restored.for_feature("action", embodiment="arm-a").layout.sizes == (2, 2)
    assert FeatureNormalizationStatistics is FeatureStatistics


def test_should_own_arrays_and_reject_nonfinite_active_values() -> None:
    """验证数组所有权、只读性和活动槽有限值规则。"""
    mean = np.asarray([1.0, 2.0])
    stats = FeatureStatistics(method="mean_std", mean=mean, std=np.ones(2))
    mean[0] = 99.0
    assert stats.mean is not None
    assert stats.mean[0] == 1.0
    with pytest.raises(ValueError, match="read-only"):
        stats.mean[0] = 3.0
    with pytest.raises(ValueError, match="non-finite active"):
        FeatureStatistics(
            method="mean_std",
            mean=np.asarray([np.nan]),
            std=np.asarray([1.0]),
        )


def test_should_allow_json_safe_nonfinite_inactive_slots() -> None:
    """验证非活动统计槽可用 null 往返且不会参与执行。"""
    stats = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([1.0, np.nan]),
        std=np.asarray([2.0, np.nan]),
        valid_mask=np.asarray([True, False]),
    )
    payload = stats.to_json_dict()
    json.dumps(payload, allow_nan=False)
    restored = FeatureStatistics.from_json_dict(payload)
    assert restored.fingerprint == stats.fingerprint


def test_should_apply_constant_identity_without_hidden_epsilon() -> None:
    """验证活动常量特征必须显式 identity, 且数值保持原样。"""
    with pytest.raises(ValueError, match="constant"):
        FeatureStatistics(method="mean_std", mean=np.asarray([2.0]), std=np.asarray([0.0]))
    stats = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([2.0]),
        std=np.asarray([0.0]),
        constant_feature_policy="identity",
    )
    transform = StatisticsNormalizationTransform(stats)
    value = np.asarray([7.0], dtype=np.float32)
    np.testing.assert_array_equal(transform.normalize(value), value)
    np.testing.assert_array_equal(transform.denormalize(value), value)


def test_should_roundtrip_exact_broadcast_and_time_alignment() -> None:
    """验证 exact、``[D]`` 广播和显式时间索引往返。"""
    vector = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([1.0, 2.0]),
        std=np.asarray([2.0, 4.0]),
    )
    values = np.asarray([[3.0, 6.0], [5.0, 10.0]], dtype=np.float32)
    broadcast = StatisticsNormalizationTransform(
        vector,
        value_layout=TensorLayout.time_feature(),
        alignment=AlignmentPolicy(AlignmentMode.BROADCAST),
    )
    np.testing.assert_allclose(broadcast.denormalize(broadcast.normalize(values)), values)

    per_time = FeatureStatistics(
        method="mean_std",
        layout=TensorLayout.time_feature(),
        mean=np.asarray([[1.0, 2.0], [10.0, 20.0], [3.0, 4.0]]),
        std=np.ones((3, 2)),
    )
    indexed = StatisticsNormalizationTransform(
        per_time,
        value_layout=TensorLayout.time_feature(),
        alignment=AlignmentPolicy(AlignmentMode.TIME_INDEX, (2, 0)),
    )
    np.testing.assert_allclose(indexed.denormalize(indexed.normalize(values)), values)


def test_should_execute_explicit_pad_time_without_activating_padded_statistics() -> None:
    """验证 pad-time 计划可执行, pad 统计槽保持非活动。"""
    stats = FeatureStatistics(
        method="mean_std",
        layout=TensorLayout.time_feature(),
        mean=np.asarray([[1.0], [2.0]]),
        std=np.ones((2, 1)),
    )
    transform = StatisticsNormalizationTransform(
        stats,
        value_layout=TensorLayout.time_feature(3, 1),
        alignment=AlignmentPolicy(AlignmentMode.PAD_TIME),
    )
    values = np.asarray([[2.0], [4.0], [9.0]], dtype=np.float32)
    np.testing.assert_allclose(transform.normalize(values), [[1.0], [2.0], [9.0]])


def test_should_reject_layout_mismatch_without_explicit_policy() -> None:
    """验证 ``[D]`` 统计量不会隐式匹配 ``[T,D]`` 数据。"""
    stats = FeatureStatistics(
        method="mean_std", mean=np.asarray([0.0, 0.0]), std=np.asarray([1.0, 1.0])
    )
    transform = StatisticsNormalizationTransform(
        stats,
        value_layout=TensorLayout.time_feature(),
    )
    with pytest.raises(ValueError, match="exact"):
        transform.normalize(np.ones((2, 2), dtype=np.float32))
