"""M2 转换配置、注册表与组合转换。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from typing import cast

from genesisvla.core.protocols import TransformProtocol
from genesisvla.core.types import RawSample
from genesisvla.dataloader.contracts import (
    ComposeConfig,
    SerializableTransformProtocol,
    TransformSpec,
)

TransformFactory = Callable[["TransformSpec"], TransformProtocol]


def stable_transform_fingerprint(specs: Sequence[TransformSpec]) -> str:
    """计算稳定转换配置指纹。"""
    payload = {
        "fingerprint_schema_version": "2.0",
        "steps": [spec.canonical() for spec in specs],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class TransformRegistry:
    """按名称解析转换配置的注册表。"""

    def __init__(self) -> None:
        self._factories: dict[str, TransformFactory] = {}

    def register(self, name: str, factory: TransformFactory) -> None:
        """注册转换工厂。"""
        if name in self._factories:
            raise ValueError(f"transform already registered: {name}")
        TransformSpec(name=name, params={})
        self._factories[name] = factory

    def create(self, spec: TransformSpec) -> TransformProtocol:
        """从 TransformSpec 创建转换对象。"""
        try:
            factory = self._factories[spec.name]
        except KeyError as exc:
            raise KeyError(f"unknown transform: {spec.name}") from exc
        return factory(spec)


class ComposeTransform:
    """按顺序执行多个 RawSample 转换。"""

    def __init__(
        self,
        transforms: Sequence[TransformProtocol],
        *,
        config: ComposeConfig | None = None,
    ) -> None:
        self._transforms = tuple(transforms)
        self._config = config

    def __call__(self, sample: object) -> RawSample:
        """顺序执行转换并校验每一步输出。"""
        if not isinstance(sample, RawSample):
            raise TypeError("ComposeTransform input must be RawSample")
        current = sample
        for index, transform in enumerate(self._transforms):
            object_transform = cast(Callable[[RawSample], object], transform)
            output = object_transform(current)
            if not isinstance(output, RawSample):
                raise TypeError(f"transform step {index} must return RawSample")
            current = output
        return current

    def serialize(self) -> ComposeConfig:
        """返回构造时声明的显式序列化配置。"""
        if self._config is None:
            raise TypeError("ComposeTransform is not serializable without explicit specs")
        return self._config

    @classmethod
    def from_serializable(
        cls,
        transforms: Sequence[SerializableTransformProtocol],
    ) -> "ComposeTransform":
        """从显式 to_spec 协议构造可序列化组合。"""
        specs = tuple(transform.to_spec() for transform in transforms)
        return cls(cast(Sequence[TransformProtocol], transforms), config=ComposeConfig(specs))

    @staticmethod
    def serialize_specs(specs: Sequence[TransformSpec]) -> ComposeConfig:
        """从 TransformSpec 序列创建组合配置。"""
        return ComposeConfig(tuple(specs))

    @classmethod
    def deserialize(
        cls,
        config: ComposeConfig,
        *,
        registry: TransformRegistry,
    ) -> "ComposeTransform":
        """从组合配置和注册表恢复组合转换。"""
        transforms = tuple(registry.create(spec) for spec in config.steps)
        return cls(transforms, config=config)
