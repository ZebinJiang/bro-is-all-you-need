"""训练组合根使用的运行画像门禁与规范身份。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

from autovla.core.runtime import EnvProfile, RuntimePlan
from autovla.runtime_profiles.contracts import (
    FamilyRuntimeProfile,
    RuntimeCompatibilityReport,
)
from autovla.runtime_profiles.errors import RuntimeEnvironmentError

if TYPE_CHECKING:
    from autovla.models.assembly import ModelRuntimeBundle
    from autovla.runtime_profiles.manager import RuntimeEnvironmentManager

ProcessorT = TypeVar("ProcessorT")
BackboneT = TypeVar("BackboneT")
ActionHeadT = TypeVar("ActionHeadT")
ModelT = TypeVar("ModelT")
CheckpointAdapterT = TypeVar("CheckpointAdapterT")
PolicyBundleT = TypeVar("PolicyBundleT")


def _type_identity(value: object) -> str:
    """返回对象类型的稳定 Python 身份。"""

    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


@dataclass(frozen=True, slots=True)
class VerifiedTrainingRuntime:
    """保存一个已实现且兼容的 CUDA 训练画像证据。"""

    profile: FamilyRuntimeProfile
    report: RuntimeCompatibilityReport

    def __post_init__(self) -> None:
        """拒绝转换画像、未实现环境、身份漂移和许可门未关闭。"""

        if not self.profile.is_training_runtime:
            raise RuntimeEnvironmentError("TRAINING_PROFILE_REQUIRED", self.profile.profile_id)
        if not self.profile.requires_cuda:
            raise RuntimeEnvironmentError("CPU_MODEL_RUNTIME_FORBIDDEN", self.profile.profile_id)
        if self.profile.blockers:
            raise RuntimeEnvironmentError("PROFILE_BLOCKED", "; ".join(self.profile.blockers))
        if self.profile.asset_license_gate_status.startswith("blocked"):
            raise RuntimeEnvironmentError(
                "ASSET_LICENSE_GATE_BLOCKED",
                self.profile.asset_license_gate_status,
            )
        if self.report.profile_id != self.profile.profile_id:
            raise RuntimeEnvironmentError(
                "PROFILE_REPORT_IDENTITY_MISMATCH", self.report.profile_id
            )
        if self.report.source_sha != self.report.fingerprint.source_sha:
            raise RuntimeEnvironmentError(
                "PROFILE_SOURCE_IDENTITY_MISMATCH", self.report.source_sha
            )
        if self.report.asset_and_license_gate_status != self.profile.asset_license_gate_status:
            raise RuntimeEnvironmentError(
                "PROFILE_GATE_IDENTITY_MISMATCH",
                self.report.asset_and_license_gate_status,
            )
        if self.report.fingerprint.realized_runtime_fingerprint is None:
            raise RuntimeEnvironmentError("ENVIRONMENT_NOT_REALIZED", self.profile.profile_id)
        if not self.report.is_compatible:
            codes = ",".join(item.code for item in self.report.errors) or "unknown"
            raise RuntimeEnvironmentError("ENVIRONMENT_INCOMPATIBLE", codes)

    @property
    def bundle_profile_identity(self) -> str:
        """返回模型运行包必须携带的 profile 与 lock 联合身份。"""

        lock_sha = self.profile.lock_sha256
        if lock_sha is None:
            raise RuntimeEnvironmentError("PROFILE_LOCK_MISSING", self.profile.profile_id)
        return f"{self.profile.profile_id}@lock-sha256:{lock_sha}"


@dataclass(frozen=True, slots=True)
class TrainingRuntimeIdentity:
    """绑定处理器、模型、checkpoint、调优和运行画像身份。"""

    family_key: str
    family_definition_fingerprint: str
    processor: str
    model: str
    checkpoint_adapter: str
    checkpoint_fingerprint: str
    tuning_strategy: str
    runtime_profile: str
    portable_runtime_fingerprint: str
    realized_runtime_fingerprint: str
    asset_bundle_fingerprint: str
    asset_manifest_fingerprint: str

    @classmethod
    def from_bundle(
        cls,
        bundle: ModelRuntimeBundle[
            ProcessorT,
            BackboneT,
            ActionHeadT,
            ModelT,
            CheckpointAdapterT,
            PolicyBundleT,
        ],
        runtime: VerifiedTrainingRuntime,
    ) -> TrainingRuntimeIdentity:
        """从唯一模型运行包和已验证画像建立 checkpoint 身份。"""

        from autovla.models.assembly import ModelRuntimeBundle

        if not isinstance(cast(object, bundle), ModelRuntimeBundle):
            raise TypeError("training composition requires ModelRuntimeBundle")
        if bundle.family_definition.family_key != runtime.profile.family_key:
            raise ValueError("runtime profile family differs from model runtime bundle")
        if bundle.runtime_profile_identity != runtime.bundle_profile_identity:
            raise ValueError("model runtime bundle profile identity drifted")
        realized = runtime.report.fingerprint.realized_runtime_fingerprint
        if realized is None:
            raise RuntimeEnvironmentError("ENVIRONMENT_NOT_REALIZED", runtime.profile.profile_id)
        return cls(
            family_key=bundle.family_definition.family_key,
            family_definition_fingerprint=bundle.family_definition.fingerprint,
            processor=_type_identity(bundle.processor),
            model=_type_identity(bundle.model),
            checkpoint_adapter=_type_identity(bundle.checkpoint_adapter),
            checkpoint_fingerprint=bundle.checkpoint_evidence.checkpoint_fingerprint,
            tuning_strategy=bundle.tuning_freeze_plan.strategy,
            runtime_profile=bundle.runtime_profile_identity,
            portable_runtime_fingerprint=(runtime.report.fingerprint.portable_lock_fingerprint),
            realized_runtime_fingerprint=realized,
            asset_bundle_fingerprint=bundle.asset_evidence.asset_bundle_fingerprint,
            asset_manifest_fingerprint=bundle.asset_evidence.manifest_fingerprint,
        )

    def to_dict(self) -> dict[str, str]:
        """返回 checkpoint provenance 使用的稳定身份映射。"""

        return {
            "family_key": self.family_key,
            "family_definition_fingerprint": self.family_definition_fingerprint,
            "processor": self.processor,
            "model": self.model,
            "checkpoint_adapter": self.checkpoint_adapter,
            "checkpoint_fingerprint": self.checkpoint_fingerprint,
            "tuning_strategy": self.tuning_strategy,
            "runtime_profile": self.runtime_profile,
            "portable_runtime_fingerprint": self.portable_runtime_fingerprint,
            "realized_runtime_fingerprint": self.realized_runtime_fingerprint,
            "asset_bundle_fingerprint": self.asset_bundle_fingerprint,
            "asset_manifest_fingerprint": self.asset_manifest_fingerprint,
        }


def resolve_verified_training_runtime(
    repository_root: Path,
    family_key: str,
    *,
    manager: RuntimeEnvironmentManager | None = None,
) -> VerifiedTrainingRuntime:
    """在模型、数据和 distributed 副作用前解析并验证唯一训练画像。"""

    from autovla.runtime_profiles.manager import RuntimeEnvironmentManager
    from autovla.runtime_profiles.registry import load_runtime_profiles

    root = repository_root.resolve()
    profiles = tuple(
        profile
        for profile in load_runtime_profiles(root).values()
        if profile.family_key == family_key and profile.is_training_runtime
    )
    if len(profiles) != 1:
        raise RuntimeEnvironmentError(
            "TRAINING_PROFILE_CARDINALITY_INVALID",
            f"{family_key} has {len(profiles)} training profiles",
        )
    profile = profiles[0]
    runtime_manager = manager or RuntimeEnvironmentManager(root)
    report = runtime_manager.verify(profile.profile_id)
    return VerifiedTrainingRuntime(profile=profile, report=report)


__all__ = [
    "EnvProfile",
    "RuntimePlan",
    "TrainingRuntimeIdentity",
    "VerifiedTrainingRuntime",
    "resolve_verified_training_runtime",
]
