# SPDX-License-Identifier: Apache-2.0
# Source: https://github.com/Physical-Intelligence/openpi/tree/15a9616a00943ada6c20a0f158e3adb39df2ccac
# ruff: noqa: RUF002
"""Pi0.5 物理语义与 quantile 归一化的不可变收据和执行计划。"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Protocol, cast, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from autovla.models.families.pi0_5.source_map import OPENPI_REVISION

Float32Array = NDArray[np.float32]
BoolArray = NDArray[np.bool_]


def _require_sha256(value: str, name: str) -> None:
    """要求字段为完整小写 SHA256。"""

    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA256")


def _canonical_array(value: object, *, name: str, width: int) -> Float32Array:
    """复制有限 float32 一维统计量并冻结。"""

    array = np.asarray(value)
    if array.dtype != np.float32 or array.shape != (width,) or not np.isfinite(array).all():
        raise ValueError(f"{name} must be finite float32[{width}]")
    owned = np.array(array, dtype=np.float32, order="C", copy=True)
    if owned.dtype.byteorder == ">" or (owned.dtype.byteorder == "=" and sys.byteorder == "big"):
        owned = owned.astype(owned.dtype.newbyteorder("<"), copy=False)
    owned.setflags(write=False)
    return owned


def _array_sha256(value: Float32Array) -> str:
    """按 C 连续小端 float32 字节计算统计量身份。"""

    return hashlib.sha256(np.ascontiguousarray(value).tobytes(order="C")).hexdigest()


@dataclass(frozen=True, slots=True)
class Pi05FeatureReceipt:
    """记录一个物理特征的有序语义。"""

    name: str
    unit: str
    frame: str
    source: str

    def __post_init__(self) -> None:
        """拒绝未知或空白语义。"""

        values = (self.name, self.unit, self.frame, self.source)
        if any(
            type(value) is not str or not value.strip() or value != value.strip()
            for value in values
        ):
            raise ValueError("Pi0.5 feature semantics must be explicit canonical strings")


@dataclass(frozen=True, slots=True)
class Pi05NormalizationReceipt:
    """绑定 embodiment、特征顺序、单位、坐标系和统计来源。"""

    embodiment: str
    state_features: tuple[Pi05FeatureReceipt, ...]
    action_features: tuple[Pi05FeatureReceipt, ...]
    statistics_source: str
    statistics_fingerprint: str
    semantic_transform_id: str
    schema_version: str = "autovla.pi0_5.normalization_receipt.v1"
    source_revision: str = OPENPI_REVISION

    def __post_init__(self) -> None:
        """验证版本、固定来源和显式物理语义。"""

        if self.schema_version != "autovla.pi0_5.normalization_receipt.v1":
            raise ValueError("unsupported Pi0.5 normalization receipt schema")
        if self.source_revision != OPENPI_REVISION:
            raise ValueError("Pi0.5 normalization receipt source revision drifted")
        for name, value in (
            ("embodiment", self.embodiment),
            ("statistics_source", self.statistics_source),
            ("semantic_transform_id", self.semantic_transform_id),
        ):
            if type(value) is not str or not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be an explicit canonical string")
        _require_sha256(self.statistics_fingerprint, "statistics_fingerprint")
        for name, features in (
            ("state_features", self.state_features),
            ("action_features", self.action_features),
        ):
            if not features or len(features) > 32:
                raise ValueError(f"{name} must contain 1..32 ordered features")
            if any(type(item) is not Pi05FeatureReceipt for item in features):
                raise TypeError(f"{name} must contain Pi05FeatureReceipt values")
            names = tuple(item.name for item in features)
            if len(set(names)) != len(names):
                raise ValueError(f"{name} names must be unique")

    @property
    def fingerprint(self) -> str:
        """返回覆盖 embodiment 和全部有序语义字段的稳定身份。"""

        payload = asdict(self)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Pi05NormalizationReceipt:
        """从无载荷 JSON 映射构造严格收据。"""

        expected = {
            "action_features",
            "embodiment",
            "schema_version",
            "semantic_transform_id",
            "source_revision",
            "state_features",
            "statistics_fingerprint",
            "statistics_source",
        }
        if set(value) != expected:
            raise ValueError("Pi0.5 normalization receipt fields must be exact")

        def features(name: str) -> tuple[Pi05FeatureReceipt, ...]:
            """解析严格的有序物理特征列表。"""

            raw = value[name]
            if not isinstance(raw, list):
                raise TypeError(f"{name} must be a JSON list")
            result: list[Pi05FeatureReceipt] = []
            for item in cast(list[object], raw):
                if not isinstance(item, Mapping):
                    raise ValueError(f"{name} entries must contain exact semantic fields")
                raw_item = cast(Mapping[object, object], item)
                if set(raw_item) != {
                    "frame",
                    "name",
                    "source",
                    "unit",
                }:
                    raise ValueError(f"{name} entries must contain exact semantic fields")
                result.append(
                    Pi05FeatureReceipt(
                        name=cast(str, raw_item["name"]),
                        unit=cast(str, raw_item["unit"]),
                        frame=cast(str, raw_item["frame"]),
                        source=cast(str, raw_item["source"]),
                    )
                )
            return tuple(result)

        return cls(
            embodiment=cast(str, value["embodiment"]),
            state_features=features("state_features"),
            action_features=features("action_features"),
            statistics_source=cast(str, value["statistics_source"]),
            statistics_fingerprint=cast(str, value["statistics_fingerprint"]),
            semantic_transform_id=cast(str, value["semantic_transform_id"]),
            schema_version=cast(str, value["schema_version"]),
            source_revision=cast(str, value["source_revision"]),
        )


@runtime_checkable
class Pi05SemanticTransform(Protocol):
    """描述 embodiment 正向语义和精确动作逆变换。"""

    @property
    def identity(self) -> str:
        """返回与归一化收据绑定的稳定变换身份。"""

        ...

    def forward_state(self, value: Float32Array) -> Float32Array:
        """把物理状态转换为模型统计量使用的语义。"""

        ...

    def forward_actions(self, value: Float32Array) -> Float32Array:
        """把物理动作转换为模型统计量使用的语义。"""

        ...

    def inverse_actions(self, value: Float32Array) -> Float32Array:
        """严格反转 ``forward_actions``。"""

        ...


@dataclass(frozen=True, slots=True)
class Pi05IdentitySemanticTransform:
    """为来源语义已经与模型统计量一致的 embodiment 提供恒等变换。"""

    identity: str = "autovla.pi0_5.semantic.identity.v1"

    def forward_state(self, value: Float32Array) -> Float32Array:
        """返回拥有的状态副本。"""

        return np.array(value, dtype=np.float32, copy=True)

    def forward_actions(self, value: Float32Array) -> Float32Array:
        """返回拥有的动作副本。"""

        return np.array(value, dtype=np.float32, copy=True)

    def inverse_actions(self, value: Float32Array) -> Float32Array:
        """返回拥有的物理动作副本。"""

        return np.array(value, dtype=np.float32, copy=True)


@dataclass(frozen=True, slots=True)
class Pi05SemanticNormalizationPlan:
    """执行 ``语义正向→quantile`` 和 ``反 quantile→语义逆向``。"""

    receipt: Pi05NormalizationReceipt
    state_q01: Float32Array
    state_q99: Float32Array
    action_q01: Float32Array
    action_q99: Float32Array
    semantic_transform: Pi05SemanticTransform

    def __post_init__(self) -> None:
        """复制冻结统计量并绑定变换、来源和特征宽度。"""

        if type(self.receipt) is not Pi05NormalizationReceipt:
            raise TypeError("receipt must be Pi05NormalizationReceipt")
        raw_semantic_transform = cast(object, self.semantic_transform)
        if not isinstance(raw_semantic_transform, Pi05SemanticTransform):
            raise TypeError("semantic_transform must implement Pi05SemanticTransform")
        if self.semantic_transform.identity != self.receipt.semantic_transform_id:
            raise ValueError("semantic transform identity drifted from normalization receipt")
        state_width = len(self.receipt.state_features)
        action_width = len(self.receipt.action_features)
        for name, width in (
            ("state_q01", state_width),
            ("state_q99", state_width),
            ("action_q01", action_width),
            ("action_q99", action_width),
        ):
            object.__setattr__(
                self,
                name,
                _canonical_array(getattr(self, name), name=name, width=width),
            )
        if np.any(self.state_q99 <= self.state_q01):
            raise ValueError("active state q99 values must be greater than q01")
        if np.any(self.action_q99 <= self.action_q01):
            raise ValueError("active action q99 values must be greater than q01")

    @property
    def fingerprint(self) -> str:
        """返回覆盖收据、统计值和变换身份的稳定计划身份。"""

        payload = {
            "action_q01_sha256": _array_sha256(self.action_q01),
            "action_q99_sha256": _array_sha256(self.action_q99),
            "receipt_fingerprint": self.receipt.fingerprint,
            "schema_version": "autovla.pi0_5.semantic_normalization_plan.v1",
            "state_q01_sha256": _array_sha256(self.state_q01),
            "state_q99_sha256": _array_sha256(self.state_q99),
            "transform_identity": self.semantic_transform.identity,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def normalize_state(self, value: object) -> tuple[Float32Array, BoolArray]:
        """执行状态语义正向和 quantile，并右侧补零到 32 维。"""

        raw = self._physical_values(value, width=len(self.receipt.state_features), name="state")
        semantic = self._semantic_result(
            self.semantic_transform.forward_state(raw), raw.shape, name="state"
        )
        normalized = (semantic - self.state_q01) / (
            self.state_q99 - self.state_q01 + np.float32(1e-6)
        )
        normalized = normalized * np.float32(2.0) - np.float32(1.0)
        padded = np.zeros((*normalized.shape[:-1], 32), dtype=np.float32)
        mask = np.zeros_like(padded, dtype=np.bool_)
        padded[..., : normalized.shape[-1]] = normalized
        mask[..., : normalized.shape[-1]] = True
        return padded, mask

    def normalize_actions(self, value: object) -> tuple[Float32Array, BoolArray]:
        """执行动作语义正向和 quantile，并右侧补零到 32 维。"""

        raw = self._physical_values(
            value, width=len(self.receipt.action_features), name="actions", rank=3
        )
        semantic = self._semantic_result(
            self.semantic_transform.forward_actions(raw), raw.shape, name="actions"
        )
        normalized = (semantic - self.action_q01) / (
            self.action_q99 - self.action_q01 + np.float32(1e-6)
        )
        normalized = normalized * np.float32(2.0) - np.float32(1.0)
        padded = np.zeros((*normalized.shape[:-1], 32), dtype=np.float32)
        mask = np.zeros_like(padded, dtype=np.bool_)
        padded[..., : normalized.shape[-1]] = normalized
        mask[..., : normalized.shape[-1]] = True
        return padded, mask

    def denormalize_model_actions(self, value: object) -> Float32Array:
        """仅执行反 quantile，保留模型语义供后续显式 inverse 步骤。"""

        model = np.asarray(value)
        if (
            model.dtype != np.float32
            or model.ndim != 3
            or model.shape[-1] != 32
            or not np.isfinite(model).all()
        ):
            raise ValueError("model actions must be finite float32[B,H,32]")
        width = len(self.receipt.action_features)
        active = np.array(model[..., :width], dtype=np.float32, copy=True)
        return (
            (active + np.float32(1.0))
            * np.float32(0.5)
            * (self.action_q99 - self.action_q01 + np.float32(1e-6))
            + self.action_q01
        ).astype(np.float32, copy=False)

    def inverse_semantics(self, value: object) -> Float32Array:
        """执行 embodiment 动作逆变换并验证形状、dtype 和有限性。"""

        model_semantics = self._physical_values(
            value, width=len(self.receipt.action_features), name="model_semantics", rank=3
        )
        return self._semantic_result(
            self.semantic_transform.inverse_actions(model_semantics),
            model_semantics.shape,
            name="inverse actions",
        )

    def trim_actions(self, value: object, *, horizon: int) -> Float32Array:
        """把物理动作裁剪到显式 horizon，特征顺序由收据固定。"""

        actions = self._physical_values(
            value, width=len(self.receipt.action_features), name="physical actions", rank=3
        )
        if type(horizon) is not int or not 1 <= horizon <= actions.shape[1]:
            raise ValueError("physical action horizon must be an explicit positive prefix")
        return np.array(actions[:, :horizon], dtype=np.float32, copy=True)

    @staticmethod
    def _physical_values(
        value: object,
        *,
        width: int,
        name: str,
        rank: int = 2,
    ) -> Float32Array:
        """校验物理数组具有精确宽度、float32 和有限值。"""

        array = np.asarray(value)
        if (
            array.dtype != np.float32
            or array.ndim != rank
            or array.shape[-1] != width
            or not np.isfinite(array).all()
        ):
            raise ValueError(f"{name} must be finite float32 with trailing width {width}")
        return np.array(array, dtype=np.float32, copy=True)

    @staticmethod
    def _semantic_result(value: object, shape: tuple[int, ...], *, name: str) -> Float32Array:
        """拒绝语义变换改变形状、dtype 或有限性。"""

        array = np.asarray(value)
        if array.dtype != np.float32 or array.shape != shape or not np.isfinite(array).all():
            raise ValueError(f"{name} semantic transform must preserve shape and float32")
        return np.array(array, dtype=np.float32, copy=True)


__all__ = [
    "Pi05FeatureReceipt",
    "Pi05IdentitySemanticTransform",
    "Pi05NormalizationReceipt",
    "Pi05SemanticNormalizationPlan",
    "Pi05SemanticTransform",
]
