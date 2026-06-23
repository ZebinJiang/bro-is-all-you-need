"""GenesisVLA 转换协议测试。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from genesisvla.core.protocols import TransformProtocol
from genesisvla.core.types import RawSample


def _raw_sample(**overrides: Any) -> RawSample:
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.zeros((2, 3), dtype=np.float32),
        "state": np.zeros((3,), dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"episode_id": "ep-transform"},
    }
    payload.update(overrides)
    return RawSample(**payload)


class MetadataTransform:
    """用于验证结构化转换协议的最小实现。"""

    def __call__(self, sample: RawSample) -> RawSample:
        metadata = dict(sample.metadata)
        metadata["stage"] = "protocol"
        return replace(sample, metadata=metadata)


def test_should_accept_transform_protocol_implementation() -> None:
    """验证显式协议注解接受结构匹配实现。"""
    transform: TransformProtocol = MetadataTransform()

    output = transform(_raw_sample())

    assert output.metadata["stage"] == "protocol"


def test_should_apply_transform_to_raw_sample_without_runtime_protocol_check() -> None:
    """验证协议通过调用形状工作,不依赖运行时 isinstance 检查。"""
    transform: TransformProtocol = MetadataTransform()
    sample = _raw_sample(metadata={"episode_id": "ep-001"})

    output = transform(sample)

    assert output is not sample
    assert output.images is sample.images
    assert output.actions is sample.actions
    assert output.state is sample.state
    assert output.metadata["episode_id"] == "ep-001"
    assert output.metadata["stage"] == "protocol"
