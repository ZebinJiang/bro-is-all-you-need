"""M2 转换注册表与配置序列化契约测试。"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import replace
from typing import Any, cast

import numpy as np
import pytest

import genesisvla.dataloader as dataloader
from genesisvla.core.types import RawSample
from genesisvla.dataloader.statistics import FeatureStatistics
from genesisvla.dataloader.transforms import (
    ActionModeTransform,
    ComposeTransform,
    ImageAugment,
    ImageNormalize,
    ImageResize,
    StateActionNormalize,
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

    def to_spec(self) -> TransformSpec:
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
    original = ComposeTransform.from_serializable(
        (AppendMetadataStep("first"), AppendMetadataStep("second"))
    )
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


def test_should_include_implementation_version_in_transform_fingerprint() -> None:
    """验证实现版本进入 transform fingerprint。"""
    left = TransformSpec(name="append_step", implementation_version="1")
    right = TransformSpec(name="append_step", implementation_version="2")

    assert stable_transform_fingerprint((left,)) != stable_transform_fingerprint((right,))


def test_should_own_transform_params_immutably() -> None:
    """验证 TransformSpec 深拷贝并冻结调用方参数。"""
    source: dict[str, object] = {"name": "first", "extra": {"values": [1, 2]}}
    spec = TransformSpec(name="append_step", params=source)
    nested = source["extra"]
    assert isinstance(nested, dict)
    nested["values"] = [99]

    canonical = spec.canonical()
    params = canonical["params"]
    assert isinstance(params, Mapping)
    assert params["extra"] == {"values": [1, 2]}

    with pytest.raises(TypeError):
        cast(MutableMapping[str, object], spec.params)["name"] = "changed"


def test_should_reject_non_json_transform_params() -> None:
    """验证 TransformSpec 只接受严格 JSON 参数。"""
    with pytest.raises(TypeError, match="JSON"):
        TransformSpec(name="append_step", params={"bad": np.asarray([1.0])})
    with pytest.raises(TypeError, match="string"):
        TransformSpec(
            name="append_step",
            params=cast(Mapping[str, object], {1: "collides"}),
        )
    with pytest.raises(ValueError, match="finite"):
        TransformSpec(name="append_step", params={"bad": float("nan")})
    with pytest.raises(ValueError, match="device"):
        TransformSpec(name="append_step", params={"nested": {"device": "cuda"}})


def test_should_fail_serialization_for_runtime_only_transform() -> None:
    """验证未声明 to_spec 的转换不会被动态 getattr 当作公共契约。"""
    transform = ComposeTransform((AppendMetadataStep("runtime-only"),))

    with pytest.raises(TypeError, match="serializable"):
        transform.serialize()


def test_should_validate_transform_context() -> None:
    """验证 TransformContext 提供确定性执行上下文基础字段。"""
    context = dataloader.TransformContext(
        seed=7,
        epoch=2,
        sample_key="episode-1:3",
        sample_index=3,
        worker_id=1,
        worker_count=2,
        rank=0,
        world_size=1,
        metadata={"split": "train"},
    )

    assert context.sample_key == "episode-1:3"
    assert context.metadata["split"] == "train"
    with pytest.raises(ValueError, match="worker"):
        dataloader.TransformContext(worker_id=2, worker_count=2)


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


def test_should_roundtrip_production_transforms_through_default_registry() -> None:
    """验证生产转换可通过 JSON-safe spec 和 fresh registry 重建。"""
    from genesisvla.dataloader.transforms import default_transform_registry

    stats = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([1.0, 2.0], dtype=np.float32),
        std=np.asarray([1.0, 2.0], dtype=np.float32),
    )
    transforms = (
        ImageResize(size=(2, 2), channel_order="HWC"),
        ImageNormalize(
            mean=(0.0, 0.0, 0.0),
            std=(1.0, 1.0, 1.0),
            channel_order="HWC",
            input_range="0_255",
        ),
        ImageAugment(mode="horizontal_flip", probability=1.0, seed=3, channel_order="HWC"),
        StateActionNormalize(action=stats),
        ActionModeTransform(
            mode="delta",
            reference_frame="previous_action",
            first_step_policy="absolute",
        ),
    )
    original = ComposeTransform.from_serializable(transforms)
    plain = original.serialize().canonical()
    steps = tuple(
        TransformSpec(
            name=str(item["name"]),
            params=cast(Mapping[str, object], item["params"]),
            schema_version=str(item["schema_version"]),
            implementation_version=str(item["implementation_version"]),
        )
        for item in cast(list[Mapping[str, object]], plain["steps"])
    )

    restored = ComposeTransform.deserialize(
        ComposeTransform.serialize_specs(steps),
        registry=default_transform_registry(),
    )

    sample = _raw_sample(
        images={"front": np.arange(3 * 3 * 3, dtype=np.uint8).reshape(3, 3, 3)},
        actions=np.asarray([[1.0, 2.0], [2.0, 4.0]], dtype=np.float32),
    )
    left = original(sample)
    right = restored(sample)
    assert left.actions is not None
    assert right.actions is not None
    np.testing.assert_allclose(right.images["front"], left.images["front"])
    np.testing.assert_allclose(right.actions, left.actions)
