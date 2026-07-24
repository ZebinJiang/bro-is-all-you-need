"""三个活跃模型族的精确资产包注册事实。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from autovla.assets.errors import ModelAssetConfigurationError
from autovla.assets.registry import ModelFamilyAssetState


class AssetBundleComponentState(str, Enum):
    """描述资产包成员的已验证或失败关闭状态。"""

    VERIFIED_RECEIPT = "verified_receipt"
    PRESENT_BLOCKED_LICENSE = "present_blocked_license"
    MISSING_LICENSE_RECEIPT = "missing_license_receipt"
    MISSING_IMMUTABLE_IDENTITY = "missing_immutable_identity"
    UNSELECTED_DATA_BINDING = "unselected_data_binding"


@dataclass(frozen=True, slots=True)
class ModelAssetBundleComponent:
    """声明一个资产角色的公开身份及当前证据状态。"""

    role: str
    asset_key: str
    public_identifier: str
    revision: str | None
    state: AssetBundleComponentState
    license_status: str

    def __post_init__(self) -> None:
        """拒绝空身份、伪造 revision 和非闭集状态。"""

        if any(
            not value.strip()
            for value in (self.role, self.asset_key, self.public_identifier, self.license_status)
        ):
            raise ModelAssetConfigurationError("asset bundle component fields must not be empty")
        if self.revision is not None and (
            len(self.revision) != 40
            or any(character not in "0123456789abcdef" for character in self.revision)
        ):
            raise ModelAssetConfigurationError("asset bundle component revision must be Git SHA")
        if type(self.state) is not AssetBundleComponentState:
            raise ModelAssetConfigurationError("asset bundle component state is invalid")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定且不包含本地主机路径的组件事实。"""

        return {
            "asset_key": self.asset_key,
            "license_status": self.license_status,
            "public_identifier": self.public_identifier,
            "revision": self.revision,
            "role": self.role,
            "state": self.state.value,
        }


@dataclass(frozen=True, slots=True)
class ModelFamilyAssetBundleRegistration:
    """绑定家族资产包工厂、成员闭集和控制 blocker。"""

    family_key: str
    factory_path: str
    lifecycle_state: ModelFamilyAssetState
    components: tuple[ModelAssetBundleComponent, ...]
    blockers: tuple[str, ...]
    runtime_authorized: bool = False

    def __post_init__(self) -> None:
        """确保失败关闭注册不能冒充运行授权。"""

        module, separator, symbol = self.factory_path.partition(":")
        if not self.family_key.strip() or not separator or not module or not symbol:
            raise ModelAssetConfigurationError("asset bundle registration identity is invalid")
        if not self.components or len({item.role for item in self.components}) != len(
            self.components
        ):
            raise ModelAssetConfigurationError("asset bundle component roles must be unique")
        if type(self.lifecycle_state) is not ModelFamilyAssetState:
            raise ModelAssetConfigurationError("asset bundle lifecycle state is invalid")
        if type(self.runtime_authorized) is not bool or self.runtime_authorized:
            raise ModelAssetConfigurationError(
                "M11 asset bundle registration cannot authorize runtime"
            )
        if not self.blockers or any(not blocker.strip() for blocker in self.blockers):
            raise ModelAssetConfigurationError("asset bundle registration requires blockers")

    @property
    def fingerprint(self) -> str:
        """根据公开注册事实生成稳定 SHA256。"""

        payload = self.to_json_dict(include_fingerprint=False)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_json_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        """序列化精确成员、许可门和工厂路径。"""

        payload: dict[str, object] = {
            "blockers": list(self.blockers),
            "components": [item.to_json_dict() for item in self.components],
            "factory_path": self.factory_path,
            "family_key": self.family_key,
            "lifecycle_state": self.lifecycle_state.value,
            "runtime_authorized": self.runtime_authorized,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


class ModelFamilyAssetBundleRegistry:
    """保存三个活跃家族的轻量资产包注册。"""

    def __init__(self, registrations: tuple[ModelFamilyAssetBundleRegistration, ...]) -> None:
        """冻结按家族键索引的闭集。"""

        mapping = {item.family_key: item for item in registrations}
        if len(mapping) != len(registrations):
            raise ModelAssetConfigurationError("duplicate family asset bundle registration")
        expected = {"gr00t_n1d6", "gr00t_n1d7", "pi0_5"}
        if set(mapping) != expected:
            raise ModelAssetConfigurationError("family asset bundle registry must match M11")
        self._registrations: Mapping[str, ModelFamilyAssetBundleRegistration] = MappingProxyType(
            mapping
        )

    def require(self, family_key: str) -> ModelFamilyAssetBundleRegistration:
        """返回家族注册,未知或延后家族失败关闭。"""

        try:
            return self._registrations[family_key]
        except KeyError as exc:
            raise ModelAssetConfigurationError(
                f"unknown active family asset bundle: {family_key!r}"
            ) from exc

    def list(self) -> tuple[ModelFamilyAssetBundleRegistration, ...]:
        """按家族键稳定列出三个注册。"""

        return tuple(self._registrations[key] for key in sorted(self._registrations))


DEFAULT_MODEL_FAMILY_ASSET_BUNDLE_REGISTRY = ModelFamilyAssetBundleRegistry(
    (
        ModelFamilyAssetBundleRegistration(
            family_key="gr00t_n1d6",
            factory_path=("autovla.models.families.gr00t_n1d6.assets:Gr00tN1d6AssetBundle"),
            lifecycle_state=ModelFamilyAssetState.BLOCKED_C3_DATA,
            components=(
                ModelAssetBundleComponent(
                    "base_checkpoint",
                    "gr00t_n1d6",
                    "nvidia/GR00T-N1.6-3B",
                    "d0814e7ecb19202e7c8468b46098b0b7ef3a6d61",
                    AssetBundleComponentState.VERIFIED_RECEIPT,
                    "NVIDIA non-commercial research or evaluation terms verified locally",
                ),
                ModelAssetBundleComponent(
                    "eagle_support",
                    "gr00t_n1d6_eagle_support",
                    "NVIDIA/Isaac-GR00T/Eagle-Block2A-2B-v2-support-data",
                    "5dc80c4afd726b34faad1d8f7e007a13b34e4c88",
                    AssetBundleComponentState.VERIFIED_RECEIPT,
                    "NVIDIA n1.6.1 source support terms verified locally",
                ),
            ),
            blockers=("BLOCKED_C3_DATA",),
        ),
        ModelFamilyAssetBundleRegistration(
            family_key="gr00t_n1d7",
            factory_path=("autovla.models.families.gr00t_n1d7.assets:Gr00tN1d7AssetBundle"),
            lifecycle_state=ModelFamilyAssetState.BLOCKED_LICENSE,
            components=(
                ModelAssetBundleComponent(
                    "base_checkpoint",
                    "gr00t_n1d7_checkpoint",
                    "nvidia/GR00T-N1.7-3B",
                    "2fc962b973bccdd5d8ce4f67cc63b264d6886495",
                    AssetBundleComponentState.PRESENT_BLOCKED_LICENSE,
                    "packaged NVIDIA License conflicts with model-card terms",
                ),
                ModelAssetBundleComponent(
                    "cosmos_backbone",
                    "cosmos_reason2_2b_gated",
                    "nvidia/Cosmos-Reason2-2B",
                    "9ce19a195e423419c349abfc86fd07178b230561",
                    AssetBundleComponentState.MISSING_LICENSE_RECEIPT,
                    "local gated-acceptance receipt is missing",
                ),
                ModelAssetBundleComponent(
                    "checkpoint_license_receipt",
                    "gr00t_n1d7_license_resolution",
                    "local legal resolution receipt",
                    None,
                    AssetBundleComponentState.MISSING_LICENSE_RECEIPT,
                    "BLOCKED_LICENSE",
                ),
            ),
            blockers=(
                "GR00T_N1D7_CHECKPOINT_LICENSE_CONFLICT_UNRESOLVED",
                "COSMOS_REASON2_GATED_ACCEPTANCE_RECEIPT_MISSING",
            ),
        ),
        ModelFamilyAssetBundleRegistration(
            family_key="pi0_5",
            factory_path="autovla.models.families.pi0_5.assets:Pi05AssetBundle",
            lifecycle_state=ModelFamilyAssetState.BLOCKED_LICENSE,
            components=(
                ModelAssetBundleComponent(
                    "checkpoint",
                    "pi0_5_checkpoint",
                    "gs://openpi-assets/checkpoints/pi05_base",
                    None,
                    AssetBundleComponentState.MISSING_IMMUTABLE_IDENTITY,
                    "Gemma/checkpoint terms acceptance and immutable generation are missing",
                ),
                ModelAssetBundleComponent(
                    "gemma_tokenizer",
                    "pi0_5_gemma_tokenizer",
                    "gs://big_vision/paligemma_tokenizer.model",
                    None,
                    AssetBundleComponentState.MISSING_IMMUTABLE_IDENTITY,
                    "tokenizer digest and separate terms receipt are missing",
                ),
                ModelAssetBundleComponent(
                    "normalization_statistics",
                    "pi0_5_normalization",
                    "checkpoint assets/<dataset-or-robot-asset-id>",
                    None,
                    AssetBundleComponentState.UNSELECTED_DATA_BINDING,
                    "normalization identity cannot be selected before exact data binding",
                ),
            ),
            blockers=(
                "PI05_GEMMA_TERMS_ACCEPTANCE_MISSING",
                "PI05_CHECKPOINT_TOKENIZER_IMMUTABLE_IDENTITIES_MISSING",
                "PI05_NORMALIZATION_ASSET_ID_UNSELECTED",
            ),
        ),
    )
)


__all__ = [
    "DEFAULT_MODEL_FAMILY_ASSET_BUNDLE_REGISTRY",
    "AssetBundleComponentState",
    "ModelAssetBundleComponent",
    "ModelFamilyAssetBundleRegistration",
    "ModelFamilyAssetBundleRegistry",
]
