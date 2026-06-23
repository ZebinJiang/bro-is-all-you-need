"""M2 转换注册表与配置序列化契约测试。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from genesisvla.core.types import RawSample
from genesisvla.dataloader.transforms import (
    ComposeTransform,
    TransformRegistry,
    TransformSpec,
    stable_transform_fingerprint,
)


def _raw_sample(**overrides: Any) -> RawSample:
    """构造小型 RawSample。"""
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.asarray([[1.0, 2.0]], dtype=np.float32),
        "state": np.asarray([0.5, 1.0], dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"steps": ()},
    }
    payload.update(overrides)
    return RawSample(**payload)


class AppendMetadataStep:
    """测试用转换, 将步骤名追加到 metadata。"""

    def __init__(self, name: str) -> None:
        self.name = name

    def __call__(self, sample: RawSample) -> RawSample:
        metadata = dict(sample.metadata)
        metadata["steps"] = (*tuple(metadata.get("steps", ())), self.name)
        return replace(sample, metadata=metadata)

    def serialize(self) -> TransformSpec:
        """序列化为稳定配置。"""
        return TransformSpec(name="append_step", params={"name": self.name})


def _registry() -> TransformRegistry:
    """返回包含测试转换的注册表。"""
    registry = TransformRegistry()
    registry.register(
        "append_step",
        lambda spec: AppendMetadataStep(str(spec.params["name"])),
    )
    return registry


def test_should_apply_transforms_in_order() -> None:
    """验证组合转换按配置顺序执行。"""
    transform = ComposeTransform((AppendMetadataStep("first"), AppendMetadataStep("second")))

    output = transform(_raw_sample())

    assert output.metadata["steps"] == ("first", "second")


def test_should_roundtrip_transform_config() -> None:
    """验证转换配置可序列化并反序列化回等价组合。"""
    original = ComposeTransform((AppendMetadataStep("first"), AppendMetadataStep("second")))
    config = original.serialize()

    restored = ComposeTransform.deserialize(config, registry=_registry())
    output = restored(_raw_sample())

    assert output.metadata["steps"] == ("first", "second")
    assert restored.serialize().canonical() == config.canonical()


def test_should_produce_stable_transform_fingerprint() -> None:
    """验证指纹不受字典键顺序影响。"""
    left = TransformSpec(name="append_step", params={"name": "first", "extra": {"b": 2, "a": 1}})
    right = TransformSpec(name="append_step", params={"extra": {"a": 1, "b": 2}, "name": "first"})

    assert stable_transform_fingerprint((left,)) == stable_transform_fingerprint((right,))


def test_should_fail_on_unknown_transform() -> None:
    """验证未知转换名会失败, 不静默跳过。"""
    config = ComposeTransform.serialize_specs((TransformSpec(name="missing", params={}),))

    with pytest.raises(KeyError, match="missing"):
        ComposeTransform.deserialize(config, registry=_registry())


def test_should_reject_duplicate_registration() -> None:
    """验证重复注册转换名会失败。"""
    registry = _registry()

    with pytest.raises(ValueError, match="append_step"):
        registry.register("append_step", lambda spec: AppendMetadataStep(str(spec.params["name"])))


def test_should_reject_model_specific_tokenization_transform() -> None:
    """验证通用 transform spec 不承载模型专用 tokenizer/processor。"""
    with pytest.raises(ValueError, match="token"):
        TransformSpec(name="qwen_tokenizer", params={})


def test_should_reject_implicit_device_transfer_in_transform_spec() -> None:
    """验证通用 transform spec 不声明隐式 device transfer。"""
    with pytest.raises(ValueError, match="device"):
        TransformSpec(name="append_step", params={"name": "x", "device": "cuda"})
