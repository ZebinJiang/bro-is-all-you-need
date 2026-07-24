"""合成契约批的不可变、不可升级 provenance。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from autovla.data.binding.contracts import (
    DatasetCompatibilityLevel,
    canonical_data,
    sha256_fingerprint,
)


def _sha256(value: object, name: str) -> str:
    """在 provenance 边界校验小写 SHA-256。"""
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _strict_bool(value: object, name: str) -> bool:
    """拒绝整数等可强制转换值。"""
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")
    return value


@dataclass(frozen=True, slots=True)
class ContractBatchProvenance:
    """证明批次仅是确定性契约 fixture,绝不证明真实数据或模型质量。"""

    binding_fingerprint: str
    dataset_fingerprint: str
    factory_fingerprint: str
    source_revision: str
    provenance_schema: str = "autovla.contract_batch_provenance.v2"
    compatibility_level: DatasetCompatibilityLevel = DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY
    synthetic: bool = True
    real_data_evidence: bool = False
    robot_evidence: bool = False
    model_quality_evidence: bool = False
    purpose: str = "shape_and_contract_mechanics_only"

    def __post_init__(self) -> None:
        """锁定 fixture-only 等级并拒绝任何真实证据声明。"""
        for name in ("binding_fingerprint", "dataset_fingerprint", "factory_fingerprint"):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))
        for name in ("source_revision", "provenance_schema"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if self.compatibility_level is not DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY:
            raise ValueError("contract batch provenance must remain contract_fixture_only")
        for name in (
            "synthetic",
            "real_data_evidence",
            "robot_evidence",
            "model_quality_evidence",
        ):
            object.__setattr__(self, name, _strict_bool(getattr(self, name), name))
        if not self.synthetic:
            raise ValueError("contract batch provenance must be synthetic")
        if self.real_data_evidence or self.robot_evidence or self.model_quality_evidence:
            raise ValueError(
                "contract fixture must not claim real-data, robot, or quality evidence"
            )
        if not isinstance(cast(object, self.purpose), str) or not self.purpose.strip():
            raise ValueError("purpose must be non-empty text")

    @property
    def fingerprint(self) -> str:
        """返回 provenance 的确定性 SHA-256。"""
        return sha256_fingerprint(self)

    def to_dict(self) -> dict[str, object]:
        """返回可嵌入 TrainingBatch.metadata 的规范普通字典。"""
        value = canonical_data(self)
        if not isinstance(value, dict):
            raise AssertionError("canonical provenance must be a dictionary")
        return cast(dict[str, object], value)


__all__ = ["ContractBatchProvenance"]
