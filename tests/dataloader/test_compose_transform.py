"""ComposeTransform 行为测试。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from genesisvla.core.types import RawSample
from genesisvla.dataloader.transforms import ComposeTransform


def _raw_sample(**overrides: Any) -> RawSample:
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.zeros((2, 3), dtype=np.float32),
        "state": np.zeros((3,), dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"steps": ()},
    }
    payload.update(overrides)
    return RawSample(**payload)


class AppendStep:
    """把执行步骤追加到样本元数据。"""

    def __init__(self, name: str) -> None:
        self.name = name

    def __call__(self, sample: RawSample) -> RawSample:
        metadata = dict(sample.metadata)
        metadata["steps"] = (*tuple(metadata.get("steps", ())), self.name)
        return replace(sample, metadata=metadata)


class BadOutput:
    """返回非法输出的测试转换。"""

    def __call__(self, sample: RawSample) -> object:
        _ = sample
        return "not-a-sample"


class FailingTransform:
    """抛出可识别错误的测试转换。"""

    def __call__(self, sample: RawSample) -> RawSample:
        _ = sample
        raise ValueError("planned transform failure")


def test_should_apply_compose_transform_in_order() -> None:
    """验证组合转换按声明顺序左到右执行。"""
    transform = ComposeTransform((AppendStep("first"), AppendStep("second")))

    output = transform(_raw_sample())

    assert output.metadata["steps"] == ("first", "second")


def test_should_treat_empty_compose_as_identity() -> None:
    """验证空组合是显式 identity 行为。"""
    sample = _raw_sample()
    transform = ComposeTransform(())

    output = transform(sample)

    assert output is sample


def test_should_reject_non_raw_sample_input() -> None:
    """验证组合转换拒绝非 RawSample 输入。"""
    transform = ComposeTransform(())

    with pytest.raises(TypeError, match="RawSample"):
        transform(object())  # type: ignore[arg-type]


def test_should_reject_non_raw_sample_step_output() -> None:
    """验证转换步骤返回非法类型时给出步骤位置。"""
    transform = ComposeTransform((BadOutput(),))

    with pytest.raises(TypeError, match="step 0"):
        transform(_raw_sample())


def test_should_propagate_transform_failure() -> None:
    """验证转换自身错误不会被无意义吞掉。"""
    transform = ComposeTransform((FailingTransform(),))

    with pytest.raises(ValueError, match="planned transform failure"):
        transform(_raw_sample())
