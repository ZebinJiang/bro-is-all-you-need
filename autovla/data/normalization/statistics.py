"""AutoVLA 类型化归一化统计量。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


def _empty_embodiments() -> Mapping[str, Mapping[str, "FeatureNormalizationStatistics"]]:
    """返回类型明确的空 embodiment 统计映射。"""
    return {}


def _vector(value: object | None, *, name: str) -> FloatArray | None:
    """拥有并冻结可选有限一维浮点数组。"""
    if value is None:
        return None
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 1 or not bool(np.isfinite(array).all()):
        raise ValueError(f"{name} must be a finite 1-D array")
    owned = np.array(array, copy=True)
    owned.setflags(write=False)
    return owned


@dataclass(frozen=True, slots=True)
class FeatureNormalizationStatistics:
    """描述单个特征的 identity/mean-std/min-max/quantile 参数。"""

    method: str = "identity"
    center: FloatArray | None = None
    scale: FloatArray | None = None
    minimum: FloatArray | None = None
    maximum: FloatArray | None = None
    lower_quantile: FloatArray | None = None
    upper_quantile: FloatArray | None = None
    valid_mask: BoolArray | None = None

    def __post_init__(self) -> None:
        """校验方法要求、维度一致性和严格布尔掩码。"""
        if self.method not in {"identity", "mean_std", "min_max", "quantile"}:
            raise ValueError(f"unsupported normalization method: {self.method}")
        names = ("center", "scale", "minimum", "maximum", "lower_quantile", "upper_quantile")
        arrays: dict[str, FloatArray | None] = {
            name: _vector(getattr(self, name), name=name) for name in names
        }
        present = [array for array in arrays.values() if array is not None]
        if present and any(array.shape != present[0].shape for array in present):
            raise ValueError("normalization statistic arrays must share one shape")
        mask = None
        if self.valid_mask is not None:
            raw_mask = np.asarray(self.valid_mask)
            if raw_mask.dtype != np.dtype(np.bool_) or raw_mask.ndim != 1:
                raise TypeError("valid_mask must be a strict 1-D bool array")
            if present and raw_mask.shape != present[0].shape:
                raise ValueError("valid_mask shape must match statistics")
            mask = np.array(raw_mask, dtype=np.bool_, copy=True)
            mask.setflags(write=False)
        required = {
            "mean_std": ("center", "scale"),
            "min_max": ("minimum", "maximum"),
            "quantile": ("lower_quantile", "upper_quantile"),
        }.get(self.method, ())
        if any(arrays[name] is None for name in required):
            raise ValueError(f"normalization method {self.method!r} lacks required arrays")
        denominator: FloatArray | None = None
        if self.method == "mean_std":
            denominator = arrays["scale"]
        elif self.method == "min_max":
            minimum = arrays["minimum"]
            maximum = arrays["maximum"]
            assert minimum is not None and maximum is not None
            denominator = maximum - minimum
        elif self.method == "quantile":
            lower = arrays["lower_quantile"]
            upper = arrays["upper_quantile"]
            assert lower is not None and upper is not None
            denominator = upper - lower
        if denominator is not None:
            active = np.ones(denominator.shape, dtype=np.bool_) if mask is None else mask
            if bool(np.any(denominator[active] <= 0.0)):
                raise ValueError("normalization scales must be positive on valid dimensions")
        for name, array in arrays.items():
            object.__setattr__(self, name, array)
        object.__setattr__(self, "valid_mask", mask)

    @property
    def dimension(self) -> int | None:
        """返回统计维度;identity 无参数时返回 ``None``。"""
        for value in (self.center, self.minimum, self.lower_quantile, self.valid_mask):
            if value is not None:
                return int(value.shape[0])
        return None


@dataclass(frozen=True, slots=True)
class NormalizationStatistics:
    """按特征和可选 embodiment 保存可序列化统计量。"""

    features: Mapping[str, FeatureNormalizationStatistics]
    embodiments: Mapping[str, Mapping[str, FeatureNormalizationStatistics]] = field(
        default_factory=_empty_embodiments
    )
    schema_version: str = "autovla.normalization_statistics.v1"

    def __post_init__(self) -> None:
        """冻结特征和 embodiment 映射。"""
        if not self.features:
            raise ValueError("normalization features must not be empty")
        features = MappingProxyType(dict(self.features))
        embodiments = MappingProxyType(
            {name: MappingProxyType(dict(values)) for name, values in self.embodiments.items()}
        )
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "embodiments", embodiments)

    def for_feature(
        self, name: str, *, embodiment: str | None = None
    ) -> FeatureNormalizationStatistics:
        """优先返回 embodiment 专用统计量,再回退到全局特征。"""
        if embodiment is not None and embodiment in self.embodiments:
            values = self.embodiments[embodiment]
            if name in values:
                return values[name]
        try:
            return self.features[name]
        except KeyError as exc:
            raise KeyError(f"normalization statistics missing feature {name!r}") from exc

    def to_dict(self) -> dict[str, object]:
        """返回可进入 manifest 的 JSON 安全结构。"""

        def encode(feature: FeatureNormalizationStatistics) -> dict[str, object]:
            return {
                "method": feature.method,
                **{
                    name: (
                        None if getattr(feature, name) is None else getattr(feature, name).tolist()
                    )
                    for name in (
                        "center",
                        "scale",
                        "minimum",
                        "maximum",
                        "lower_quantile",
                        "upper_quantile",
                        "valid_mask",
                    )
                },
            }

        return {
            "schema_version": self.schema_version,
            "features": {name: encode(value) for name, value in sorted(self.features.items())},
            "embodiments": {
                embodiment: {name: encode(value) for name, value in sorted(features.items())}
                for embodiment, features in sorted(self.embodiments.items())
            },
        }

    @property
    def fingerprint(self) -> str:
        """返回统计量内容的稳定 SHA256 指纹。"""
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


__all__ = ["FeatureNormalizationStatistics", "NormalizationStatistics"]
