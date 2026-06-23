"""M2 转换配置、注册表与组合转换。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from genesisvla.core.protocols import TransformProtocol
from genesisvla.core.types import RawSample

TransformFactory = Callable[["TransformSpec"], TransformProtocol]


def _empty_params() -> dict[str, Any]:
    """返回带明确类型的空 transform 参数。"""
    return {}


def _canonical_value(value: Any) -> Any:
    """递归转换为稳定 JSON 值。"""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        return {
            str(key): _canonical_value(mapping[key])
            for key in sorted(mapping.keys(), key=lambda item: str(item))
        }
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in cast(tuple[Any, ...], value)]
    if isinstance(value, list):
        return [_canonical_value(item) for item in cast(list[Any], value)]
    return value


def _assert_no_forbidden_generic_params(name: str, params: Mapping[str, Any]) -> None:
    """阻止模型专用 tokenizer 或隐式 device transfer 混入通用 transform。"""
    lowered = name.lower()
    if "token" in lowered or "processor" in lowered:
        raise ValueError("generic transform spec must not include model-specific tokenization")
    for key in params:
        lowered_key = str(key).lower()
        if "token" in lowered_key or "processor" in lowered_key:
            raise ValueError(
                "generic transform params must not include model-specific tokenization"
            )
        if lowered_key in {"device", "cuda", "to_device"}:
            raise ValueError("generic transform params must not request implicit device transfer")


@dataclass(frozen=True, slots=True)
class TransformSpec:
    """可序列化转换配置。"""

    name: str
    params: Mapping[str, Any] = field(default_factory=_empty_params)

    def __post_init__(self) -> None:
        """校验转换配置名称和禁止项。"""
        if not self.name.strip():
            raise ValueError("transform name must not be empty")
        _assert_no_forbidden_generic_params(self.name, self.params)

    def canonical(self) -> dict[str, Any]:
        """返回稳定 canonical 表示。"""
        return {"name": self.name, "params": _canonical_value(dict(self.params))}


def stable_transform_fingerprint(specs: Sequence[TransformSpec]) -> str:
    """计算稳定转换配置指纹。"""
    payload = [spec.canonical() for spec in specs]
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
        _assert_no_forbidden_generic_params(name, {})
        self._factories[name] = factory

    def create(self, spec: TransformSpec) -> TransformProtocol:
        """从 TransformSpec 创建转换对象。"""
        try:
            factory = self._factories[spec.name]
        except KeyError as exc:
            raise KeyError(f"unknown transform: {spec.name}") from exc
        return factory(spec)


@dataclass(frozen=True, slots=True)
class ComposeConfig:
    """组合转换的可序列化配置。"""

    steps: tuple[TransformSpec, ...]

    def canonical(self) -> dict[str, Any]:
        """返回稳定 canonical 表示。"""
        return {"steps": [step.canonical() for step in self.steps]}


class ComposeTransform:
    """按顺序执行多个 RawSample 转换。"""

    def __init__(self, transforms: Sequence[TransformProtocol]) -> None:
        self._transforms = tuple(transforms)

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
        """序列化所有支持 serialize 的步骤。"""
        specs: list[TransformSpec] = []
        for index, transform in enumerate(self._transforms):
            serialize = getattr(transform, "serialize", None)
            if not callable(serialize):
                raise TypeError(f"transform step {index} does not support serialize()")
            spec = serialize()
            if not isinstance(spec, TransformSpec):
                raise TypeError(f"transform step {index} serialize() must return TransformSpec")
            specs.append(spec)
        return ComposeConfig(tuple(specs))

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
        return cls(transforms)
