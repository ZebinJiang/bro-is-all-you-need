"""实现唯一的秩感知、不可变归一化统计量契约。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Literal, cast

import numpy as np
from numpy.typing import NDArray

from autovla.core.semantics import (
    AlignmentMode,
    AlignmentPolicy,
    AxisName,
    MaskKind,
    MaskSemantics,
    TensorLayout,
    resolve_alignment,
)

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
NormalizationMethod = Literal["identity", "mean_std", "min_max", "quantile"]


class ConstantFeaturePolicy(str, Enum):
    """声明活动常量特征是报错还是保持恒等。"""

    RAISE = "raise"
    IDENTITY = "identity"


def _owned_array(value: object, *, name: str) -> FloatArray:
    """拥有浮点数组; 非有限值在活动掩码确定后统一校验。"""
    array = np.array(value, dtype=np.float64, copy=True)
    array.setflags(write=False)
    return array


def _owned_bool(value: object, *, name: str) -> BoolArray:
    """拥有严格 bool 数组, 拒绝数值隐式转换。"""
    array = np.asarray(value)
    if array.dtype != np.dtype(np.bool_):
        raise TypeError(f"{name} must use strict bool dtype")
    owned = np.array(array, dtype=np.bool_, copy=True)
    owned.setflags(write=False)
    return owned


def _encode_array(value: FloatArray | BoolArray | None) -> object:
    """把数组转换为 JSON 安全值; 非活动非有限槽编码为 null。"""
    if value is None:
        return None
    if value.dtype == np.dtype(np.bool_):
        return value.tolist()
    flat: list[float | None] = [float(item) if np.isfinite(item) else None for item in value.flat]
    return np.asarray(flat, dtype=object).reshape(value.shape).tolist()


def _decode_array(value: object, *, name: str) -> FloatArray | None:
    """从 JSON 数组恢复浮点数组, 并把 null 恢复为非活动 NaN。"""
    if value is None:
        return None

    def convert(item: object) -> object:
        if isinstance(item, (list, tuple)):
            return [convert(child) for child in cast(Sequence[object], item)]
        if item is None:
            return float("nan")
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(f"{name} must contain numbers or null")
        return float(item)

    return _owned_array(convert(value), name=name)


def _align_numpy(
    value: FloatArray | BoolArray,
    *,
    source_layout: TensorLayout,
    target_layout: TensorLayout,
    target_shape: tuple[int, ...],
    policy: AlignmentPolicy,
    broadcast: bool = True,
) -> FloatArray | BoolArray:
    """按核心对齐计划生成只读广播视图或时间索引副本。"""
    plan = resolve_alignment(
        source_layout=source_layout,
        source_shape=tuple(int(size) for size in value.shape),
        target_layout=target_layout,
        target_shape=target_shape,
        policy=policy,
    )
    aligned = value
    aligned_layout = source_layout
    if plan.time_indices:
        source_time_axis = source_layout.index(AxisName.TIME)
        if -1 in plan.time_indices:
            output_shape = list(aligned.shape)
            output_shape[source_time_axis] = len(plan.time_indices)
            padded = np.full(output_shape, plan.pad_value, dtype=aligned.dtype)
            for target_index, source_index in enumerate(plan.time_indices):
                if source_index < 0:
                    continue
                target_slice: list[slice | int] = [slice(None)] * aligned.ndim
                source_slice: list[slice | int] = [slice(None)] * aligned.ndim
                target_slice[source_time_axis] = target_index
                source_slice[source_time_axis] = source_index
                padded[tuple(target_slice)] = aligned[tuple(source_slice)]
            aligned = padded
        else:
            aligned = np.take(aligned, plan.time_indices, axis=source_time_axis)
    permutation = [
        aligned_layout.index(axis) for axis in target_layout.axes if axis in aligned_layout.axes
    ]
    if permutation != list(range(aligned.ndim)):
        aligned = np.transpose(aligned, permutation)
    reshaped = np.reshape(aligned, plan.reshape)
    result = np.broadcast_to(reshaped, target_shape) if broadcast else reshaped
    return cast(FloatArray | BoolArray, result)


@dataclass(frozen=True, slots=True, init=False)
class FeatureStatistics:
    """描述标量、``[D]``、``[T]`` 或 ``[T,D]`` 的规范统计量。

    ``layout`` 是含义真源; 兼容调用省略布局时只使用明确的 ``[feature]``
    默认值, 不会根据输入秩猜测轴。二维统计量必须显式给出布局。
    """

    method: NormalizationMethod
    layout: TensorLayout
    mean: FloatArray | None
    std: FloatArray | None
    minimum: FloatArray | None
    maximum: FloatArray | None
    lower_quantile: FloatArray | None
    upper_quantile: FloatArray | None
    valid_mask: BoolArray | None
    valid_mask_semantics: MaskSemantics | None
    names: tuple[str, ...]
    constant_feature_policy: ConstantFeaturePolicy
    alignment: AlignmentPolicy

    def __init__(
        self,
        *,
        method: NormalizationMethod = "mean_std",
        layout: TensorLayout | Sequence[AxisName | str] | None = None,
        mean: object | None = None,
        std: object | None = None,
        minimum: object | None = None,
        maximum: object | None = None,
        lower_quantile: object | None = None,
        upper_quantile: object | None = None,
        center: object | None = None,
        scale: object | None = None,
        valid_mask: object | None = None,
        valid_mask_layout: TensorLayout | Sequence[AxisName | str] | None = None,
        names: Sequence[object] = (),
        constant_feature_policy: ConstantFeaturePolicy | str = ConstantFeaturePolicy.RAISE,
        zero_variance_policy: ConstantFeaturePolicy | str | None = None,
        alignment: AlignmentPolicy | None = None,
    ) -> None:
        """构造并校验统计量, 兼容旧 ``center/scale`` 和零方差字段。"""
        if method not in {"identity", "mean_std", "min_max", "quantile"}:
            raise ValueError(f"unsupported normalization method: {method}")
        if mean is not None and center is not None:
            raise ValueError("mean and center are aliases and cannot both be supplied")
        if std is not None and scale is not None:
            raise ValueError("std and scale are aliases and cannot both be supplied")
        mean = mean if mean is not None else center
        std = std if std is not None else scale
        tensor_layout = (
            layout
            if isinstance(layout, TensorLayout)
            else TensorLayout.feature() if layout is None else TensorLayout(layout)
        )
        policy_value = zero_variance_policy or constant_feature_policy
        constant_policy = ConstantFeaturePolicy(policy_value)
        arrays = {
            "mean": None if mean is None else _owned_array(mean, name="mean"),
            "std": None if std is None else _owned_array(std, name="std"),
            "minimum": None if minimum is None else _owned_array(minimum, name="minimum"),
            "maximum": None if maximum is None else _owned_array(maximum, name="maximum"),
            "lower_quantile": (
                None
                if lower_quantile is None
                else _owned_array(lower_quantile, name="lower_quantile")
            ),
            "upper_quantile": (
                None
                if upper_quantile is None
                else _owned_array(upper_quantile, name="upper_quantile")
            ),
        }
        required = {
            "identity": (),
            "mean_std": ("mean", "std"),
            "min_max": ("minimum", "maximum"),
            "quantile": ("lower_quantile", "upper_quantile"),
        }[method]
        if any(arrays[name] is None for name in required):
            raise ValueError(f"normalization method {method!r} lacks required arrays")
        present = [array for array in arrays.values() if array is not None]
        if not present:
            if tensor_layout.rank != 0:
                raise ValueError("parameter-free identity statistics require scalar layout")
            shape: tuple[int, ...] = ()
        else:
            shape = tuple(int(size) for size in present[0].shape)
            if any(array.shape != shape for array in present):
                raise ValueError("normalization statistic arrays must share one shape")
            if len(shape) != tensor_layout.rank:
                raise ValueError("statistics array rank must match explicit layout")
            if any(size <= 0 for size in shape):
                raise ValueError("statistics dimensions must be positive")
        tensor_layout = tensor_layout.with_sizes(shape)

        mask = None if valid_mask is None else _owned_bool(valid_mask, name="valid_mask")
        mask_semantics = None
        if mask is not None:
            mask_layout = (
                valid_mask_layout
                if isinstance(valid_mask_layout, TensorLayout)
                else tensor_layout if valid_mask_layout is None else TensorLayout(valid_mask_layout)
            )
            mask_semantics = MaskSemantics(MaskKind.STATISTICS, mask_layout)
            try:
                active = cast(
                    BoolArray,
                    _align_numpy(
                        mask,
                        source_layout=mask_layout,
                        target_layout=tensor_layout,
                        target_shape=shape,
                        policy=AlignmentPolicy(AlignmentMode.BROADCAST),
                    ),
                )
            except ValueError as exc:
                raise ValueError("valid_mask cannot align to statistics layout") from exc
        else:
            active = np.ones(shape, dtype=np.bool_)

        for name, array in arrays.items():
            if array is not None and bool(np.any(~np.isfinite(array[active]))):
                raise ValueError(f"{name} contains non-finite active values")
        denominator: FloatArray | None = None
        if method == "mean_std":
            denominator = arrays["std"]
        elif method == "min_max":
            assert arrays["minimum"] is not None and arrays["maximum"] is not None
            denominator = arrays["maximum"] - arrays["minimum"]
        elif method == "quantile":
            assert arrays["lower_quantile"] is not None and arrays["upper_quantile"] is not None
            denominator = arrays["upper_quantile"] - arrays["lower_quantile"]
        if denominator is not None:
            negative = denominator < 0.0
            if bool(np.any(negative & active)):
                if method == "mean_std":
                    raise ValueError("std must not be negative on active values")
                if method == "min_max":
                    raise ValueError("maximum must not be lower than minimum on active values")
                raise ValueError(
                    "upper_quantile must not be lower than lower_quantile on active values"
                )
            constant = denominator == 0.0
            if constant_policy is ConstantFeaturePolicy.RAISE and bool(np.any(constant & active)):
                raise ValueError("active statistics contain a constant feature")

        string_names = tuple(str(name) for name in names)
        if any(not name.strip() for name in string_names) or len(set(string_names)) != len(
            string_names
        ):
            raise ValueError("feature names must be non-empty and unique")
        if string_names:
            if not tensor_layout.contains(AxisName.FEATURE):
                raise ValueError("feature names require an explicit feature axis")
            if len(string_names) != shape[tensor_layout.index(AxisName.FEATURE)]:
                raise ValueError("feature names length must match the feature axis")

        object.__setattr__(self, "method", method)
        object.__setattr__(self, "layout", tensor_layout)
        for name, array in arrays.items():
            object.__setattr__(self, name, array)
        object.__setattr__(self, "valid_mask", mask)
        object.__setattr__(self, "valid_mask_semantics", mask_semantics)
        object.__setattr__(self, "names", string_names)
        object.__setattr__(self, "constant_feature_policy", constant_policy)
        object.__setattr__(self, "alignment", alignment or AlignmentPolicy())

    @property
    def shape(self) -> tuple[int, ...]:
        """返回统计数组形状。"""
        for value in (
            self.mean,
            self.minimum,
            self.lower_quantile,
            self.valid_mask,
        ):
            if value is not None:
                if value is self.valid_mask and self.valid_mask_semantics is not None:
                    continue
                return tuple(int(size) for size in value.shape)
        return ()

    @property
    def dimension(self) -> int | None:
        """返回兼容的特征维度; 无特征轴时返回 ``None``。"""
        if not self.layout.contains(AxisName.FEATURE):
            return None
        return self.shape[self.layout.index(AxisName.FEATURE)]

    @property
    def center(self) -> FloatArray | None:
        """返回 ``mean`` 的兼容别名。"""
        return self.mean

    @property
    def scale(self) -> FloatArray | None:
        """返回 ``std`` 的兼容别名。"""
        return self.std

    @property
    def zero_variance_policy(self) -> str:
        """返回旧字段名对应的常量特征策略。"""
        return self.constant_feature_policy.value

    def active_mask(self) -> BoolArray:
        """返回与统计布局同形的活动掩码, 常量 identity 槽会关闭。"""
        shape = self.shape
        if self.valid_mask is None:
            active = np.ones(shape, dtype=np.bool_)
        else:
            assert self.valid_mask_semantics is not None
            active = np.array(
                _align_numpy(
                    self.valid_mask,
                    source_layout=self.valid_mask_semantics.layout,
                    target_layout=self.layout,
                    target_shape=shape,
                    policy=AlignmentPolicy(AlignmentMode.BROADCAST),
                ),
                dtype=np.bool_,
                copy=True,
            )
        _, denominator = self.parameters()
        if (
            denominator is not None
            and self.constant_feature_policy is ConstantFeaturePolicy.IDENTITY
        ):
            active &= denominator != 0.0
        active.setflags(write=False)
        return active

    def parameters(self) -> tuple[FloatArray | None, FloatArray | None]:
        """返回统一的偏移和尺度, 不执行 epsilon 修补。"""
        if self.method == "identity":
            return None, None
        if self.method == "mean_std":
            return self.mean, self.std
        if self.method == "min_max":
            assert self.minimum is not None and self.maximum is not None
            return self.minimum, self.maximum - self.minimum
        assert self.lower_quantile is not None and self.upper_quantile is not None
        return self.lower_quantile, self.upper_quantile - self.lower_quantile

    def to_json_dict(self) -> dict[str, object]:
        """返回带布局、掩码和策略的 JSON 安全表示。"""
        return {
            "schema_version": "autovla.feature_statistics.v2",
            "method": self.method,
            "layout": self.layout.to_json_dict(),
            "mean": _encode_array(self.mean),
            "std": _encode_array(self.std),
            "minimum": _encode_array(self.minimum),
            "maximum": _encode_array(self.maximum),
            "lower_quantile": _encode_array(self.lower_quantile),
            "upper_quantile": _encode_array(self.upper_quantile),
            "valid_mask": _encode_array(self.valid_mask),
            "valid_mask_layout": (
                None
                if self.valid_mask_semantics is None
                else self.valid_mask_semantics.layout.to_json_dict()
            ),
            "names": list(self.names),
            "constant_feature_policy": self.constant_feature_policy.value,
            "alignment": self.alignment.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, object]) -> "FeatureStatistics":
        """从 v2 JSON 表示恢复统计量。"""
        if payload.get("schema_version") != "autovla.feature_statistics.v2":
            raise ValueError("unsupported feature statistics schema_version")
        layout_payload = payload.get("layout")
        alignment_payload = payload.get("alignment")
        if not isinstance(layout_payload, Mapping) or not isinstance(alignment_payload, Mapping):
            raise TypeError("statistics layout and alignment must be JSON objects")
        alignment_mapping = cast(Mapping[str, object], alignment_payload)
        mask_layout_payload = payload.get("valid_mask_layout")
        time_indices = alignment_mapping.get("time_indices", [])
        if not isinstance(time_indices, (list, tuple)):
            raise TypeError("alignment time_indices must be a JSON array")
        return cls(
            method=cast(NormalizationMethod, payload["method"]),
            layout=TensorLayout.from_json_dict(cast(Mapping[str, object], layout_payload)),
            mean=_decode_array(payload.get("mean"), name="mean"),
            std=_decode_array(payload.get("std"), name="std"),
            minimum=_decode_array(payload.get("minimum"), name="minimum"),
            maximum=_decode_array(payload.get("maximum"), name="maximum"),
            lower_quantile=_decode_array(payload.get("lower_quantile"), name="lower_quantile"),
            upper_quantile=_decode_array(payload.get("upper_quantile"), name="upper_quantile"),
            valid_mask=payload.get("valid_mask"),
            valid_mask_layout=(
                None
                if mask_layout_payload is None
                else TensorLayout.from_json_dict(cast(Mapping[str, object], mask_layout_payload))
            ),
            names=cast(Sequence[object], payload.get("names", [])),
            constant_feature_policy=str(payload.get("constant_feature_policy", "raise")),
            alignment=AlignmentPolicy(
                AlignmentMode(str(alignment_mapping.get("mode", "exact"))),
                tuple(cast(Sequence[int], time_indices)),
                float(cast(float | int, alignment_mapping.get("pad_value", 0.0))),
            ),
        )

    @property
    def fingerprint(self) -> str:
        """返回包含布局、掩码、方法和策略的稳定指纹。"""
        encoded = json.dumps(
            self.to_json_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


# 两个公开名称必须保持对象身份, 避免第二套规范实现。
FeatureNormalizationStatistics = FeatureStatistics


def _empty_embodiments() -> dict[str, Mapping[str, FeatureStatistics]]:
    """返回类型明确的空 embodiment 统计映射。"""
    return {}


@dataclass(frozen=True, slots=True)
class NormalizationStatistics:
    """按特征和可选 embodiment 保存规范统计量集合。"""

    features: Mapping[str, FeatureStatistics]
    embodiments: Mapping[str, Mapping[str, FeatureStatistics]] = field(
        default_factory=_empty_embodiments
    )
    schema_version: str = "autovla.normalization_statistics.v2"

    def __post_init__(self) -> None:
        """校验名称和对象类型并冻结两级映射。"""
        if self.schema_version != "autovla.normalization_statistics.v2":
            raise ValueError("unsupported normalization statistics schema_version")
        if not self.features:
            raise ValueError("normalization features must not be empty")

        def freeze(values: Mapping[str, FeatureStatistics]) -> Mapping[str, FeatureStatistics]:
            output: dict[str, FeatureStatistics] = {}
            for name, value in values.items():
                if not str(name).strip():
                    raise TypeError("statistics maps require non-empty names")
                output[str(name)] = value
            return MappingProxyType(output)

        object.__setattr__(self, "features", freeze(self.features))
        object.__setattr__(
            self,
            "embodiments",
            MappingProxyType(
                {
                    str(embodiment): freeze(values)
                    for embodiment, values in self.embodiments.items()
                    if str(embodiment).strip()
                }
            ),
        )

    def for_feature(self, name: str, *, embodiment: str | None = None) -> FeatureStatistics:
        """优先返回 embodiment 专用统计量, 再回退到全局特征。"""
        if embodiment is not None and name in self.embodiments.get(embodiment, {}):
            return self.embodiments[embodiment][name]
        try:
            return self.features[name]
        except KeyError as exc:
            raise KeyError(f"normalization statistics missing feature {name!r}") from exc

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 安全表示。"""
        return {
            "schema_version": self.schema_version,
            "features": {
                name: value.to_json_dict() for name, value in sorted(self.features.items())
            },
            "embodiments": {
                embodiment: {name: value.to_json_dict() for name, value in sorted(values.items())}
                for embodiment, values in sorted(self.embodiments.items())
            },
        }

    # 旧调用使用 to_dict; 保持同一实现而不是复制序列化逻辑。
    to_dict = to_json_dict

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, object]) -> "NormalizationStatistics":
        """从严格映射恢复全局和 embodiment 统计量。"""
        if payload.get("schema_version") != "autovla.normalization_statistics.v2":
            raise ValueError("unsupported normalization statistics schema_version")
        raw_features = payload.get("features")
        raw_embodiments = payload.get("embodiments", {})
        if not isinstance(raw_features, Mapping) or not isinstance(raw_embodiments, Mapping):
            raise TypeError("statistics features and embodiments must be mappings")

        def decode(values: Mapping[object, object]) -> dict[str, FeatureStatistics]:
            output: dict[str, FeatureStatistics] = {}
            for name, value in values.items():
                if not isinstance(name, str) or not isinstance(value, Mapping):
                    raise TypeError("statistics entries must map strings to JSON objects")
                output[name] = FeatureStatistics.from_json_dict(cast(Mapping[str, object], value))
            return output

        feature_mapping = cast(Mapping[object, object], raw_features)
        embodiment_mapping = cast(Mapping[object, object], raw_embodiments)
        embodiments: dict[str, Mapping[str, FeatureStatistics]] = {}
        for embodiment, values in embodiment_mapping.items():
            if not isinstance(embodiment, str) or not isinstance(values, Mapping):
                raise TypeError("embodiment statistics entries must be mappings")
            embodiments[embodiment] = decode(cast(Mapping[object, object], values))
        return cls(decode(feature_mapping), embodiments=embodiments)

    @property
    def fingerprint(self) -> str:
        """返回全量内容稳定 SHA256 指纹。"""
        encoded = json.dumps(
            self.to_json_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class DatasetStatistics:
    """为旧 M2 缓存保留的薄数据集收据, 特征值仍是规范统计量。"""

    schema_version: str = "2.0"
    dataset_fingerprint: str = ""
    transform_fingerprint: str = ""
    count: int = 0
    state: FeatureStatistics | None = None
    action: FeatureStatistics | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))
    checksum: str = ""

    def __post_init__(self) -> None:
        """校验旧缓存收据并冻结 JSON 元数据。"""
        if self.schema_version != "2.0":
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if not self.dataset_fingerprint.strip():
            raise ValueError("dataset_fingerprint must not be empty")
        if not self.transform_fingerprint.strip():
            raise ValueError("transform_fingerprint must not be empty")
        if type(self.count) is not int or self.count < 0:
            raise ValueError("count must be a non-negative integer")
        if self.state is None and self.action is None:
            raise ValueError("state or action statistics must be present")
        try:
            plain = json.loads(json.dumps(dict(self.metadata), sort_keys=True, allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise TypeError("metadata must be JSON serializable") from exc
        object.__setattr__(self, "metadata", MappingProxyType(plain))

    @property
    def sample_count(self) -> int:
        """返回旧报告字段名。"""
        return self.count

    def to_json_dict(self, *, include_checksum: bool = True) -> dict[str, Any]:
        """转换为旧缓存兼容的 JSON 字典。"""
        payload: dict[str, Any] = {
            "action": self.action.to_json_dict() if self.action is not None else None,
            "count": self.count,
            "dataset_fingerprint": self.dataset_fingerprint,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
            "state": self.state.to_json_dict() if self.state is not None else None,
            "transform_fingerprint": self.transform_fingerprint,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        checksum = self.checksum or hashlib.sha256(encoded).hexdigest()
        if include_checksum:
            payload["checksum"] = checksum
        return payload

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, Any]) -> "DatasetStatistics":
        """恢复并验证旧缓存收据。"""
        checksum = str(payload.get("checksum", ""))
        clean = dict(payload)
        clean.pop("checksum", None)
        expected = hashlib.sha256(
            json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if not checksum or checksum != expected:
            raise ValueError("statistics checksum mismatch")
        state = payload.get("state")
        action = payload.get("action")
        return cls(
            schema_version=str(payload.get("schema_version", "")),
            dataset_fingerprint=str(payload.get("dataset_fingerprint", "")),
            transform_fingerprint=str(payload.get("transform_fingerprint", "")),
            count=int(payload.get("count", 0)),
            state=(
                FeatureStatistics.from_json_dict(cast(Mapping[str, object], state))
                if isinstance(state, Mapping)
                else None
            ),
            action=(
                FeatureStatistics.from_json_dict(cast(Mapping[str, object], action))
                if isinstance(action, Mapping)
                else None
            ),
            metadata=cast(Mapping[str, Any], payload.get("metadata", {})),
            checksum=checksum,
        )


__all__ = [
    "BoolArray",
    "ConstantFeaturePolicy",
    "DatasetStatistics",
    "FeatureNormalizationStatistics",
    "FeatureStatistics",
    "FloatArray",
    "NormalizationStatistics",
    "_align_numpy",
]
