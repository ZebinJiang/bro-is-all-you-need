"""M2 数据集统计量 schema。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, cast

import numpy as np
from numpy.typing import NDArray

from autovla.dataloader.contracts import (
    JsonObject,
    canonical_json_object,
    json_object_to_plain,
    strict_bool_array,
)

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
NormalizationMethod = Literal["mean_std", "min_max", "quantile"]
ZeroVariancePolicy = Literal["raise", "identity"]


def _normalization_method(value: Any) -> NormalizationMethod:
    """校验并返回统计量归一化方法。"""
    if value not in {"mean_std", "min_max", "quantile"}:
        raise ValueError(f"unsupported normalization method: {value}")
    return cast(NormalizationMethod, value)


def _zero_variance_policy(value: Any) -> ZeroVariancePolicy:
    """校验并返回零方差处理策略。"""
    if value not in {"raise", "identity"}:
        raise ValueError(f"unsupported zero_variance_policy: {value}")
    return cast(ZeroVariancePolicy, value)


def _float_array(value: Any, *, name: str) -> FloatArray:
    """把输入转换为有限 float 数组。"""
    array = np.array(value, dtype=np.float64, copy=True)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a 1-D array")
    if not bool(np.all(np.isfinite(array))):
        raise ValueError(f"{name} must contain finite values")
    array.setflags(write=False)
    return array


def _bool_array(value: Any | None, *, length: int) -> BoolArray | None:
    """把可选 mask 转换为 bool 数组。"""
    if value is None:
        return None
    array = strict_bool_array(value, name="valid_mask")
    if array.ndim != 1 or array.shape[0] != length:
        raise ValueError("valid_mask dimension must match statistics dimension")
    array.setflags(write=False)
    return array


def _feature_names(value: tuple[object, ...], *, length: int) -> tuple[str, ...]:
    """校验 feature name 非空、唯一且维度匹配。"""
    if not value:
        return ()
    if len(value) != length:
        raise ValueError("names length must match statistics dimension")
    seen: set[str] = set()
    output: list[str] = []
    for index, name in enumerate(value):
        if not isinstance(name, str):
            raise ValueError(f"names[{index}] must be a string")
        if not name.strip():
            raise ValueError(f"names[{index}] must not be empty")
        if name in seen:
            raise ValueError("names must not contain duplicates")
        seen.add(name)
        output.append(name)
    return tuple(output)


def _metadata_object(value: Mapping[str, Any]) -> JsonObject:
    """验证并拥有 metadata 的严格 JSON 表示。"""
    try:
        return canonical_json_object(cast(Mapping[str, object], value))
    except TypeError as exc:
        raise TypeError("metadata must be JSON serializable") from exc
    except ValueError as exc:
        raise ValueError("metadata must be JSON serializable") from exc


def _empty_metadata() -> dict[str, Any]:
    """返回带有明确类型的空 metadata。"""
    return {}


def _checksum_payload(payload: Mapping[str, Any]) -> str:
    """计算排除 checksum 字段后的稳定 SHA256。"""
    clean = dict(payload)
    clean.pop("checksum", None)
    encoded = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class FeatureStatistics:
    """描述单个特征族的归一化统计量。"""

    method: NormalizationMethod = "mean_std"
    mean: NDArray[Any] | None = None
    std: NDArray[Any] | None = None
    minimum: NDArray[Any] | None = None
    maximum: NDArray[Any] | None = None
    valid_mask: object | None = None
    names: tuple[object, ...] = ()
    zero_variance_policy: ZeroVariancePolicy = "raise"

    def __post_init__(self) -> None:
        """校验统计字段维度和策略。"""
        if self.method not in {"mean_std", "min_max", "quantile"}:
            raise ValueError(f"unsupported normalization method: {self.method}")
        if self.method == "quantile":
            raise ValueError("quantile statistics are reserved for a future schema extension")

        if self.method == "mean_std":
            if self.mean is None or self.std is None:
                raise ValueError("mean_std statistics require mean and std")
            left = _float_array(self.mean, name="mean")
            right = _float_array(self.std, name="std")
            if left.shape != right.shape:
                raise ValueError("mean and std shape must match")
            if bool(np.any(right < 0.0)):
                raise ValueError("std must be non-negative")
            if self.zero_variance_policy == "raise" and bool(np.any(right == 0.0)):
                raise ValueError("std contains zero variance dimensions")
        else:
            if self.minimum is None or self.maximum is None:
                raise ValueError("min_max statistics require minimum and maximum")
            left = _float_array(self.minimum, name="minimum")
            right = _float_array(self.maximum, name="maximum")
            if left.shape != right.shape:
                raise ValueError("minimum and maximum shape must match")
            if bool(np.any(right < left)):
                raise ValueError("maximum must be greater than or equal to minimum")
            if self.zero_variance_policy == "raise" and bool(np.any((right - left) == 0.0)):
                raise ValueError("min_max contains zero range dimensions")

        mask = _bool_array(self.valid_mask, length=left.shape[0])
        names = _feature_names(self.names, length=left.shape[0])

        object.__setattr__(self, "mean", left if self.method == "mean_std" else None)
        object.__setattr__(self, "std", right if self.method == "mean_std" else None)
        object.__setattr__(self, "minimum", left if self.method == "min_max" else None)
        object.__setattr__(self, "maximum", right if self.method == "min_max" else None)
        object.__setattr__(self, "valid_mask", mask)
        object.__setattr__(self, "names", names)

    @property
    def dimension(self) -> int:
        """返回统计维度。"""
        if self.method == "mean_std":
            assert self.mean is not None
            return int(self.mean.shape[0])
        assert self.minimum is not None
        return int(self.minimum.shape[0])

    def to_json_dict(self) -> dict[str, Any]:
        """转换为 JSON 安全字典。"""
        payload: dict[str, Any] = {
            "method": self.method,
            "names": list(self.names),
            "zero_variance_policy": self.zero_variance_policy,
            "valid_mask": (
                cast(BoolArray, self.valid_mask).tolist() if self.valid_mask is not None else None
            ),
        }
        if self.method == "mean_std":
            assert self.mean is not None and self.std is not None
            payload["mean"] = self.mean.tolist()
            payload["std"] = self.std.tolist()
        else:
            assert self.minimum is not None and self.maximum is not None
            payload["minimum"] = self.minimum.tolist()
            payload["maximum"] = self.maximum.tolist()
        return payload

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, Any]) -> "FeatureStatistics":
        """从 JSON 字典恢复统计量。"""
        method = _normalization_method(payload.get("method", "mean_std"))
        zero_variance_policy = _zero_variance_policy(payload.get("zero_variance_policy", "raise"))
        if method == "mean_std":
            return cls(
                method="mean_std",
                mean=np.asarray(payload["mean"], dtype=np.float64),
                std=np.asarray(payload["std"], dtype=np.float64),
                valid_mask=payload.get("valid_mask"),
                names=tuple(cast(tuple[object, ...], tuple(payload.get("names", ())))),
                zero_variance_policy=zero_variance_policy,
            )
        if method == "quantile":
            raise ValueError("quantile statistics are reserved for a future schema extension")
        return cls(
            method="min_max",
            minimum=np.asarray(payload["minimum"], dtype=np.float64),
            maximum=np.asarray(payload["maximum"], dtype=np.float64),
            valid_mask=payload.get("valid_mask"),
            names=tuple(cast(tuple[object, ...], tuple(payload.get("names", ())))),
            zero_variance_policy=zero_variance_policy,
        )


@dataclass(frozen=True, slots=True)
class DatasetStatistics:
    """描述数据集和转换配置绑定的统计量缓存。"""

    schema_version: str = "2.0"
    dataset_fingerprint: str = ""
    transform_fingerprint: str = ""
    count: int = 0
    state: FeatureStatistics | None = None
    action: FeatureStatistics | None = None
    metadata: Mapping[str, Any] = field(default_factory=_empty_metadata)
    checksum: str = ""

    def __post_init__(self) -> None:
        """校验统计量缓存的基本结构。"""
        if self.schema_version != "2.0":
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if not self.dataset_fingerprint.strip():
            raise ValueError("dataset_fingerprint must not be empty")
        if not self.transform_fingerprint.strip():
            raise ValueError("transform_fingerprint must not be empty")
        if self.count < 0:
            raise ValueError("count must be non-negative")
        if self.state is None and self.action is None:
            raise ValueError("state or action statistics must be present")
        object.__setattr__(self, "metadata", _metadata_object(self.metadata))

    @property
    def sample_count(self) -> int:
        """兼容旧报告字段名。"""
        return self.count

    def to_json_dict(self, *, include_checksum: bool = True) -> dict[str, Any]:
        """转换为 JSON 安全字典。"""
        payload: dict[str, Any] = {
            "action": self.action.to_json_dict() if self.action is not None else None,
            "count": self.count,
            "dataset_fingerprint": self.dataset_fingerprint,
            "metadata": json_object_to_plain(cast(JsonObject, self.metadata)),
            "schema_version": self.schema_version,
            "state": self.state.to_json_dict() if self.state is not None else None,
            "transform_fingerprint": self.transform_fingerprint,
        }
        checksum = self.checksum or _checksum_payload(payload)
        if include_checksum:
            payload["checksum"] = checksum
        return payload

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, Any]) -> "DatasetStatistics":
        """从 JSON 字典恢复并校验 checksum。"""
        checksum = str(payload.get("checksum", ""))
        if not checksum:
            raise ValueError("checksum is required")
        expected = _checksum_payload(payload)
        if checksum != expected:
            raise ValueError("statistics checksum mismatch")

        state_payload = payload.get("state")
        action_payload = payload.get("action")
        metadata_payload = payload.get("metadata", {})
        if not isinstance(metadata_payload, Mapping):
            raise TypeError("metadata must be a mapping")
        metadata_mapping = cast(Mapping[str, Any], metadata_payload)
        return cls(
            schema_version=str(payload.get("schema_version", "")),
            dataset_fingerprint=str(payload.get("dataset_fingerprint", "")),
            transform_fingerprint=str(payload.get("transform_fingerprint", "")),
            count=int(payload.get("count", 0)),
            state=(
                FeatureStatistics.from_json_dict(cast(Mapping[str, Any], state_payload))
                if isinstance(state_payload, Mapping)
                else None
            ),
            action=(
                FeatureStatistics.from_json_dict(cast(Mapping[str, Any], action_payload))
                if isinstance(action_payload, Mapping)
                else None
            ),
            metadata=metadata_mapping,
            checksum=checksum,
        )
