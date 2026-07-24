"""对真实数据元数据表面执行有界、不可升级的兼容性检查。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from autovla.data.binding.contracts import (
    DatasetCompatibilityLevel,
    ModelInputSchema,
    canonical_data,
    sha256_fingerprint,
)

BACKEND_DECISION = "NO_BACKEND_WINNER"


def _text(value: object, name: str) -> str:
    """校验并返回非空文本。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _positive_int(value: object, name: str) -> int:
    """校验排除 bool 的正整数。"""
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class BoundedDatasetSurface:
    """保存一次只读元数据观察,不把形状观察提升为物理语义。"""

    dataset_id: str
    version: str
    source_format: str
    source_revision: str
    provenance: str
    state_dimension: int
    action_dimension: int
    camera_names: tuple[str, ...]
    sample_rate_hz: float
    history: int | None = None
    horizon: int | None = None
    units_known: bool = False
    frames_known: bool = False
    ordering_known: bool = False
    normalization_known: bool = False
    embodiment_known: bool = False

    def __post_init__(self) -> None:
        """严格校验已观察字段并拒绝伪造的宽松布尔值。"""
        for name in ("dataset_id", "version", "source_format", "source_revision", "provenance"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self, "state_dimension", _positive_int(self.state_dimension, "state_dimension")
        )
        object.__setattr__(
            self, "action_dimension", _positive_int(self.action_dimension, "action_dimension")
        )
        cameras = tuple(_text(item, "camera_names") for item in self.camera_names)
        if not cameras or len(set(cameras)) != len(cameras):
            raise ValueError("camera_names must be non-empty and unique")
        object.__setattr__(self, "camera_names", cameras)
        if isinstance(self.sample_rate_hz, bool) or self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        for name in ("history", "horizon"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _positive_int(value, name))
        for name in (
            "units_known",
            "frames_known",
            "ordering_known",
            "normalization_known",
            "embodiment_known",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")

    @property
    def fingerprint(self) -> str:
        """返回观察表面的确定性身份。"""
        return sha256_fingerprint(self)


@dataclass(frozen=True, slots=True)
class BoundedRealSampleReport:
    """报告元数据层的缺口,永不宣称真实样本已兼容某模型族。"""

    dataset_surface_fingerprint: str
    family_id: str
    level: DatasetCompatibilityLevel
    reason_codes: tuple[str, ...]
    observed_state_dimension: int
    observed_action_dimension: int
    observed_camera_names: tuple[str, ...]
    source_revision: str
    provenance: str
    real_sample_read: bool = False
    family_compatibility_claimed: bool = False
    backend_decision: str = BACKEND_DECISION

    def __post_init__(self) -> None:
        """锁定 incompatible 和非声明状态。"""
        if self.level is not DatasetCompatibilityLevel.INCOMPATIBLE:
            raise ValueError("bounded metadata report must remain incompatible")
        if self.real_sample_read or self.family_compatibility_claimed:
            raise ValueError("bounded metadata report cannot claim real-sample compatibility")
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("bounded report must preserve NO_BACKEND_WINNER")
        if not self.reason_codes:
            raise ValueError("bounded report must explain incompatibility")

    @property
    def fingerprint(self) -> str:
        """返回完整报告的确定性身份。"""
        return sha256_fingerprint(self)

    def to_dict(self) -> dict[str, object]:
        """返回可序列化且不包含模型运行声明的报告。"""
        value = canonical_data(self)
        if not isinstance(value, dict):
            raise AssertionError("bounded report must serialize to a mapping")
        return cast(dict[str, object], value)


def inspect_bounded_dataset_surface(
    surface: BoundedDatasetSurface,
    model_schema: ModelInputSchema,
) -> BoundedRealSampleReport:
    """比较已观察形状并把所有未知物理语义显式报告为不兼容。"""
    if not isinstance(cast(object, surface), BoundedDatasetSurface):
        raise TypeError("surface must be BoundedDatasetSurface")
    if not isinstance(cast(object, model_schema), ModelInputSchema):
        raise TypeError("model_schema must be ModelInputSchema")
    reasons = ["NO_DATASET_MODEL_BINDING"]
    known_axes = (
        (surface.units_known, "UNKNOWN_UNITS"),
        (surface.frames_known, "UNKNOWN_COORDINATE_OR_REFERENCE_FRAMES"),
        (surface.ordering_known, "UNKNOWN_FEATURE_ORDERING"),
        (surface.normalization_known, "UNKNOWN_NORMALIZATION"),
        (surface.embodiment_known, "UNKNOWN_EMBODIMENT"),
    )
    reasons.extend(code for known, code in known_axes if not known)
    if surface.history is None:
        reasons.append("UNKNOWN_HISTORY")
    elif surface.history != model_schema.history:
        reasons.append("HISTORY_MISMATCH")
    if surface.horizon is None:
        reasons.append("UNKNOWN_HORIZON")
    elif surface.horizon != model_schema.horizon:
        reasons.append("HORIZON_MISMATCH")
    expected_state = sum(item.dimension for item in model_schema.state_features)
    expected_action = sum(item.dimension for item in model_schema.action_features)
    if surface.state_dimension != expected_state:
        reasons.append("STATE_DIMENSION_MISMATCH")
    if surface.action_dimension != expected_action:
        reasons.append("ACTION_DIMENSION_MISMATCH")
    if surface.camera_names != model_schema.camera_names:
        reasons.append("CAMERA_ORDER_OR_IDENTITY_MISMATCH")
    return BoundedRealSampleReport(
        dataset_surface_fingerprint=surface.fingerprint,
        family_id=model_schema.family_id,
        level=DatasetCompatibilityLevel.INCOMPATIBLE,
        reason_codes=tuple(dict.fromkeys(reasons)),
        observed_state_dimension=surface.state_dimension,
        observed_action_dimension=surface.action_dimension,
        observed_camera_names=surface.camera_names,
        source_revision=surface.source_revision,
        provenance=surface.provenance,
    )


__all__ = [
    "BACKEND_DECISION",
    "BoundedDatasetSurface",
    "BoundedRealSampleReport",
    "inspect_bounded_dataset_surface",
]
