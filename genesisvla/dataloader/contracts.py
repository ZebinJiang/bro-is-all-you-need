"""M2 dataloader 公共契约。"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, is_dataclass
from types import MappingProxyType
from typing import Any, Protocol, TypeAlias, cast

import numpy as np
from numpy.typing import NDArray

from genesisvla.core.types import ActionMask, NumericArray, RawSample

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]
JsonObject: TypeAlias = Mapping[str, JsonValue]

_CONTRACT_SCHEMA_VERSION = "2.0"
_VERSION_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _empty_params() -> dict[str, object]:
    """返回类型明确的空 transform params。"""
    return {}


def _empty_metadata() -> dict[str, object]:
    """返回类型明确的空 JSON metadata。"""
    return {}


def empty_json_object() -> JsonObject:
    """返回不可变空 JSON object。"""
    return MappingProxyType({})


def _is_dataclass_instance(value: object) -> bool:
    """判断对象是否为 dataclass 实例。"""
    return is_dataclass(value) and not isinstance(value, type)


def _canonical_json_value(value: object, *, path: str) -> JsonValue:
    """递归拥有并校验 JSON 值。"""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return _canonical_json_object(mapping, path=path)
    if isinstance(value, list):
        sequence = cast(list[object], value)
        return tuple(
            _canonical_json_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(sequence)
        )
    if isinstance(value, tuple):
        sequence = cast(tuple[object, ...], value)
        return tuple(
            _canonical_json_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(sequence)
        )
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"JSON float values must be finite at {path}")
        return value
    if isinstance(value, (bytes, bytearray)):
        raise TypeError(f"JSON value at {path} must not be bytes")
    if callable(value) or _is_dataclass_instance(value):
        raise TypeError(f"JSON value at {path} has unsupported type {type(value).__name__}")
    raise TypeError(f"JSON value at {path} has unsupported type {type(value).__name__}")


def _canonical_json_object(value: Mapping[object, object], *, path: str) -> JsonObject:
    """递归拥有并冻结 JSON object。"""
    output: dict[str, JsonValue] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str):
            raise TypeError(f"JSON object keys must be strings at {path}")
        if raw_key in output:
            raise ValueError(f"canonical key collision at {path}.{raw_key}")
        output[raw_key] = _canonical_json_value(raw_value, path=f"{path}.{raw_key}")
    return MappingProxyType({key: output[key] for key in sorted(output)})


def canonical_json_object(value: Mapping[str, object]) -> JsonObject:
    """返回深拷贝、排序且不可变的 JSON object。"""
    return _canonical_json_object(cast(Mapping[object, object], value), path="$")


def json_value_to_plain(value: JsonValue) -> object:
    """把不可变 JSON 值转换为 json.dumps 可直接处理的普通值。"""
    if isinstance(value, Mapping):
        return {key: json_value_to_plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [json_value_to_plain(item) for item in value]
    return value


def json_object_to_plain(value: JsonObject) -> dict[str, object]:
    """把不可变 JSON object 转换为普通 dict。"""
    return {key: json_value_to_plain(item) for key, item in value.items()}


def _assert_no_forbidden_generic_params(name: str, params: JsonObject) -> None:
    """阻止模型专用 tokenizer 或隐式 device transfer 混入通用 transform。"""
    lowered = name.lower()
    if "token" in lowered or "processor" in lowered:
        raise ValueError("generic transform spec must not include model-specific tokenization")

    def visit(mapping: JsonObject) -> None:
        for key, value in mapping.items():
            lowered_key = key.lower()
            if "token" in lowered_key or "processor" in lowered_key:
                raise ValueError(
                    "generic transform params must not include model-specific tokenization"
                )
            if lowered_key in {"device", "cuda", "to_device"}:
                raise ValueError(
                    "generic transform params must not request implicit device transfer"
                )
            if isinstance(value, Mapping):
                visit(value)
            elif isinstance(value, tuple):
                for item in value:
                    if isinstance(item, Mapping):
                        visit(item)

    visit(params)


def _validate_version(value: object, *, name: str) -> None:
    """校验契约版本标识。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    if not _VERSION_RE.fullmatch(value):
        raise ValueError(f"{name} must contain only A-Za-z0-9._-")


def _nonempty_string(value: object, *, name: str) -> str:
    """校验非空字符串并返回。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _non_bool_int(value: object, *, name: str) -> int:
    """校验 int 字段且拒绝 bool。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    return value


def _readonly_numeric_array(value: NumericArray, *, name: str) -> NumericArray:
    """复制数值数组并标记只读。"""
    array = np.array(value, copy=True)
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"{name} must be numeric")
    array.setflags(write=False)
    return array


def _readonly_bool_array(value: ActionMask, *, name: str) -> ActionMask:
    """复制 bool 数组并标记只读。"""
    array = strict_bool_array(value, name=name)
    array.setflags(write=False)
    return array


def strict_bool_array(value: object, *, name: str) -> ActionMask:
    """复制 bool 数组/序列, 拒绝数值和字符串的隐式 coercion。"""
    array = np.asarray(value)
    if array.dtype != np.dtype(np.bool_):
        raise TypeError(f"{name} must contain bool values without coercion")
    return np.array(array, dtype=np.bool_, copy=True)


def _readonly_int_array(value: NDArray[np.integer[Any]], *, name: str) -> NDArray[np.int64]:
    """复制 int 数组并标记只读。"""
    array = np.array(value, dtype=np.int64, copy=True)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a 1-D array")
    if not bool(np.all(array > 0)):
        raise ValueError(f"{name} values must be positive")
    array.setflags(write=False)
    return array


@dataclass(frozen=True, slots=True)
class TransformSpec:
    """可序列化、不可变且带版本的转换配置。"""

    name: str
    params: Mapping[str, object] = field(default_factory=_empty_params)
    schema_version: str = _CONTRACT_SCHEMA_VERSION
    implementation_version: str = "1"

    def __post_init__(self) -> None:
        """校验并拥有转换配置。"""
        _nonempty_string(self.name, name="transform name")
        if self.schema_version != _CONTRACT_SCHEMA_VERSION:
            raise ValueError(f"unsupported transform schema_version: {self.schema_version}")
        _validate_version(self.implementation_version, name="implementation_version")
        owned_params = canonical_json_object(self.params)
        _assert_no_forbidden_generic_params(self.name, owned_params)
        object.__setattr__(self, "params", owned_params)

    def canonical(self) -> dict[str, object]:
        """返回稳定 canonical 表示。"""
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "implementation_version": self.implementation_version,
            "params": json_object_to_plain(cast(JsonObject, self.params)),
        }


@dataclass(frozen=True, slots=True)
class ComposeConfig:
    """组合转换的可序列化配置。"""

    steps: tuple[TransformSpec, ...]
    schema_version: str = _CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验组合配置版本并拥有步骤元组。"""
        if self.schema_version != _CONTRACT_SCHEMA_VERSION:
            raise ValueError(f"unsupported compose schema_version: {self.schema_version}")
        object.__setattr__(self, "steps", tuple(self.steps))

    def canonical(self) -> dict[str, object]:
        """返回稳定 canonical 表示。"""
        return {
            "schema_version": self.schema_version,
            "steps": [step.canonical() for step in self.steps],
        }


class SerializableTransformProtocol(Protocol):
    """定义可序列化 RawSample 转换的公开协议。"""

    def __call__(self, sample: RawSample) -> RawSample:
        """转换单条 RawSample。"""
        ...

    def to_spec(self) -> TransformSpec:
        """返回可重建转换的 TransformSpec。"""
        ...


@dataclass(frozen=True, slots=True)
class TransformContext:
    """描述转换执行的确定性上下文。"""

    seed: int = 0
    epoch: int = 0
    sample_key: str | None = None
    sample_index: int | None = None
    worker_id: int = 0
    worker_count: int = 1
    rank: int = 0
    world_size: int = 1
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        """校验上下文字段并拥有 metadata。"""
        for name in ("seed", "epoch", "worker_id", "worker_count", "rank", "world_size"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
        if self.epoch < 0:
            raise ValueError("epoch must be non-negative")
        if self.sample_index is not None:
            sample_index = _non_bool_int(self.sample_index, name="sample_index")
            if sample_index < 0:
                raise ValueError("sample_index must be non-negative")
        if self.sample_key is not None and not self.sample_key.strip():
            raise ValueError("sample_key must not be empty")
        if self.worker_count <= 0 or not 0 <= self.worker_id < self.worker_count:
            raise ValueError("worker_id must be in [0, worker_count)")
        if self.world_size <= 0 or not 0 <= self.rank < self.world_size:
            raise ValueError("rank must be in [0, world_size)")
        object.__setattr__(self, "metadata", canonical_json_object(self.metadata))

    def canonical(self) -> dict[str, object]:
        """返回 JSON 安全上下文表示。"""
        return {
            "seed": self.seed,
            "epoch": self.epoch,
            "sample_key": self.sample_key,
            "sample_index": self.sample_index,
            "worker_id": self.worker_id,
            "worker_count": self.worker_count,
            "rank": self.rank,
            "world_size": self.world_size,
            "metadata": json_object_to_plain(cast(JsonObject, self.metadata)),
        }

    def fingerprint(self) -> str:
        """返回上下文稳定指纹。"""
        encoded = json.dumps(
            self.canonical(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class CollatedBatch:
    """M2 numpy-only typed mini-batch 契约。"""

    images: Mapping[str, NumericArray]
    language: tuple[str, ...]
    actions: NumericArray | None
    state: NumericArray | None
    robot_tag: tuple[str, ...]
    action_mask: ActionMask | None
    metadata: tuple[Mapping[str, object], ...] = ()
    sample_source: tuple[Mapping[str, object], ...] = ()
    action_horizon: NDArray[np.int64] | None = None
    action_dim: NDArray[np.int64] | None = None

    def __post_init__(self) -> None:
        """校验 batch-major 形状与 canonical action mask。"""
        batch_size = len(self.language)
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if len(self.robot_tag) != batch_size:
            raise ValueError("robot_tag length must match batch_size")

        owned_images = self._owned_images(batch_size)
        owned_actions = (
            _readonly_numeric_array(self.actions, name="actions")
            if self.actions is not None
            else None
        )
        owned_state = (
            _readonly_numeric_array(self.state, name="state") if self.state is not None else None
        )
        if owned_actions is not None and owned_actions.ndim != 3:
            raise ValueError("actions must have shape [B,H,D]")
        if owned_actions is not None and owned_actions.shape[0] != batch_size:
            raise ValueError("actions batch dimension must match batch_size")
        if owned_state is not None and owned_state.shape[0] != batch_size:
            raise ValueError("state batch dimension must match batch_size")

        owned_mask = self._owned_action_mask(owned_actions)
        owned_horizon, owned_dim = self._owned_action_sizes(owned_actions, batch_size)
        owned_metadata = self._owned_metadata(batch_size)
        owned_source = self._owned_sample_source(batch_size, owned_metadata)

        object.__setattr__(self, "images", owned_images)
        object.__setattr__(self, "actions", owned_actions)
        object.__setattr__(self, "state", owned_state)
        object.__setattr__(self, "action_mask", owned_mask)
        object.__setattr__(self, "metadata", owned_metadata)
        object.__setattr__(self, "sample_source", owned_source)
        object.__setattr__(self, "action_horizon", owned_horizon)
        object.__setattr__(self, "action_dim", owned_dim)

    @property
    def batch_size(self) -> int:
        """返回 batch size。"""
        return len(self.language)

    def _owned_images(self, batch_size: int) -> Mapping[str, NumericArray]:
        """拥有并校验图像 batch。"""
        if not self.images:
            raise ValueError("images must not be empty")
        output: dict[str, NumericArray] = {}
        for name, value in self.images.items():
            array = _readonly_numeric_array(value, name=f"images.{name}")
            if array.shape[0] != batch_size:
                raise ValueError("image batch dimension must match batch_size")
            output[str(name)] = array
        return MappingProxyType(output)

    def _owned_action_mask(self, actions: NumericArray | None) -> ActionMask | None:
        """拥有并校验 canonical `[B,H,D]` action mask。"""
        if actions is None:
            if self.action_mask is not None:
                raise ValueError("action_mask requires actions")
            return None
        if self.action_mask is None:
            mask = np.ones(actions.shape, dtype=np.bool_)
        else:
            mask = strict_bool_array(self.action_mask, name="action_mask")
        if mask.shape != actions.shape:
            raise ValueError("action_mask must have shape [B,H,D] matching actions")
        return _readonly_bool_array(mask, name="action_mask")

    def _owned_action_sizes(
        self,
        actions: NumericArray | None,
        batch_size: int,
    ) -> tuple[NDArray[np.int64] | None, NDArray[np.int64] | None]:
        """拥有或推导每条样本的原始 action horizon/dim。"""
        if actions is None:
            return None, None
        horizon = (
            np.full((batch_size,), actions.shape[1], dtype=np.int64)
            if self.action_horizon is None
            else np.asarray(self.action_horizon, dtype=np.int64)
        )
        dim = (
            np.full((batch_size,), actions.shape[2], dtype=np.int64)
            if self.action_dim is None
            else np.asarray(self.action_dim, dtype=np.int64)
        )
        if horizon.shape != (batch_size,) or dim.shape != (batch_size,):
            raise ValueError("action_horizon and action_dim must match batch_size")
        if bool(np.any(horizon > actions.shape[1])) or bool(np.any(dim > actions.shape[2])):
            raise ValueError("action_horizon/action_dim must fit padded action shape")
        return (
            _readonly_int_array(horizon, name="action_horizon"),
            _readonly_int_array(dim, name="action_dim"),
        )

    def _owned_metadata(self, batch_size: int) -> tuple[JsonObject, ...]:
        """拥有并校验 per-sample metadata。"""
        if not self.metadata:
            return tuple(empty_json_object() for _ in range(batch_size))
        if len(self.metadata) != batch_size:
            raise ValueError("metadata length must match batch_size")
        return tuple(canonical_json_object(item) for item in self.metadata)

    def _owned_sample_source(
        self,
        batch_size: int,
        metadata: tuple[JsonObject, ...],
    ) -> tuple[JsonObject, ...]:
        """拥有并校验 per-sample source provenance。"""
        if self.sample_source:
            if len(self.sample_source) != batch_size:
                raise ValueError("sample_source length must match batch_size")
            return tuple(canonical_json_object(item) for item in self.sample_source)
        sources: list[JsonObject] = []
        for item in metadata:
            source = item.get("sample_source", empty_json_object())
            if not isinstance(source, Mapping):
                raise TypeError("sample_source metadata must be a JSON object")
            sources.append(canonical_json_object(cast(Mapping[str, object], source)))
        return tuple(sources)

    def to_legacy_dict(self) -> dict[str, Any]:
        """转换为旧 dict batch 形态。"""
        return {
            "images": dict(self.images),
            "language": self.language,
            "actions": self.actions,
            "state": self.state,
            "robot_tag": self.robot_tag,
            "action_mask": self.action_mask,
            "action_horizon": self.action_horizon,
            "action_dim": self.action_dim,
            "sample_source": tuple(
                json_object_to_plain(cast(JsonObject, item)) for item in self.sample_source
            ),
            "metadata": tuple(
                json_object_to_plain(cast(JsonObject, item)) for item in self.metadata
            ),
        }
