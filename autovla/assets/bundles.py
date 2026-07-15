"""由多个已验证资产收据组成的类型化模型资产包。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from autovla.assets.contracts import (
    AssetLicenseRecord,
    AssetProvenanceRecord,
    ModelAssetManifest,
    ModelAssetSpec,
    ResolvedModelAsset,
)
from autovla.assets.registry import (
    GR00T_N1D6_ASSET_SPEC,
    GR00T_N1D6_EAGLE_SUPPORT_SPEC,
)
from autovla.assets.store import ModelAssetStore

EAGLE_SUPPORT_SUBDIRECTORY = "gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2"


@dataclass(frozen=True, slots=True)
class VerifiedModelAssetBundle:
    """实现通用已验证资产包，身份不包含转换结果或运行 checkpoint。"""

    family_key: str
    revision: str
    root: Path
    assets_by_role: Mapping[str, ResolvedModelAsset]
    checkpoint_candidates: tuple[Path, ...] = ()
    tokenizer_or_processor_assets: tuple[Path, ...] = ()
    backbone_assets: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        """冻结角色映射并立即执行协议校验。"""

        object.__setattr__(self, "assets_by_role", MappingProxyType(dict(self.assets_by_role)))
        self.validate()

    @property
    def manifest(self) -> Mapping[str, ModelAssetManifest]:
        """按角色暴露已验证清单。"""

        return MappingProxyType(
            {role: asset.manifest for role, asset in self.assets_by_role.items()}
        )

    @property
    def provenance(self) -> tuple[AssetProvenanceRecord, ...]:
        """返回固定来源、revision 与收据身份。"""

        return tuple(
            AssetProvenanceRecord(
                asset.manifest.source_url,
                asset.manifest.revision,
                asset.identity,
            )
            for asset in self.assets_by_role.values()
        )

    @property
    def license_records(self) -> tuple[AssetLicenseRecord, ...]:
        """返回每个资产独立许可记录。"""

        return tuple(
            AssetLicenseRecord(
                asset.manifest.key,
                asset.manifest.license_name,
                asset.manifest.license_file_path,
                asset.manifest.redistribution,
            )
            for asset in self.assets_by_role.values()
        )

    @property
    def fingerprint(self) -> str:
        """仅由家族、revision 和角色收据身份生成摘要。"""

        payload = {
            "family_key": self.family_key,
            "revision": self.revision,
            "assets_by_role": {
                role: asset.identity for role, asset in self.assets_by_role.items()
            },
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate(self) -> None:
        """验证绝对根、角色唯一性、家族和 revision 一致。"""

        if not self.family_key.strip() or not self.revision.strip() or not self.root.is_absolute():
            raise ValueError("verified asset bundle requires family, revision and absolute root")
        if len(self.revision) != 40 or any(
            character not in "0123456789abcdef" for character in self.revision
        ):
            raise ValueError("verified asset bundle revision must be a pinned Git SHA")
        if not self.assets_by_role or any(not role.strip() for role in self.assets_by_role):
            raise ValueError("verified asset bundle requires non-empty asset roles")
        for asset in self.assets_by_role.values():
            if asset.manifest.family_key != self.family_key:
                raise ValueError("asset bundle family identity mismatch")
            if asset.manifest.revision != self.revision:
                raise ValueError("asset bundle revision identity mismatch")
        declared_paths = (
            self.checkpoint_candidates
            + self.tokenizer_or_processor_assets
            + self.backbone_assets
        )
        if any(not path.is_absolute() for path in declared_paths):
            raise ValueError("asset bundle paths must be absolute")
        asset_roots = tuple(asset.root for asset in self.assets_by_role.values())
        if self.root not in asset_roots:
            raise ValueError("asset bundle root must select one verified asset root")
        if any(
            not any(path.is_relative_to(asset_root) for asset_root in asset_roots)
            for path in declared_paths
        ):
            raise ValueError("asset bundle paths must remain inside verified asset roots")


@dataclass(frozen=True, slots=True)
class ModelAssetBundleRequirement:
    """声明一个角色必须由哪个固定资产规范满足。"""

    role: str
    spec: ModelAssetSpec

    def __post_init__(self) -> None:
        """拒绝空角色。"""

        if not self.role.strip():
            raise ValueError("asset bundle role must not be empty")

    def to_json_dict(self) -> dict[str, str]:
        """返回稳定资产需求。"""

        return {
            "role": self.role,
            "key": self.spec.key,
            "revision": self.spec.revision,
            "spec_identity": self.spec.identity,
        }


@dataclass(frozen=True, slots=True)
class Gr00tModelAssetBundle:
    """组合官方 GR00T checkpoint 与非可执行 Eagle 支持数据。"""

    base_checkpoint: ResolvedModelAsset
    eagle_support: ResolvedModelAsset

    def __post_init__(self) -> None:
        """要求两个收据分别匹配固定规范且许可/权重边界不混淆。"""

        _require_receipt(self.base_checkpoint, GR00T_N1D6_ASSET_SPEC)
        _require_receipt(self.eagle_support, GR00T_N1D6_EAGLE_SUPPORT_SPEC)
        if self.base_checkpoint.root == self.eagle_support.root:
            raise ValueError("checkpoint and Eagle support data must use separate asset roots")

    @classmethod
    def resolve(cls, store: ModelAssetStore) -> "Gr00tModelAssetBundle":
        """先完整验证两个本地资产,再签发类型化 bundle。"""

        return cls(
            base_checkpoint=store.verify(GR00T_N1D6_ASSET_SPEC),
            eagle_support=store.verify(GR00T_N1D6_EAGLE_SUPPORT_SPEC),
        )

    @property
    def family_key(self) -> str:
        """返回共享协议家族键。"""

        return "gr00t_n1d6"

    @property
    def revision(self) -> str:
        """返回主 checkpoint 固定 revision。"""

        return self.base_checkpoint.manifest.revision

    @property
    def root(self) -> Path:
        """返回主 checkpoint 的不可变根。"""

        return self.base_checkpoint.root

    @property
    def manifest(self) -> Mapping[str, ModelAssetManifest]:
        """按角色返回两个已验证清单。"""

        return MappingProxyType(
            {
                "base_checkpoint": self.base_checkpoint.manifest,
                "eagle_support": self.eagle_support.manifest,
            }
        )

    @property
    def assets_by_role(self) -> Mapping[str, ResolvedModelAsset]:
        """按稳定角色返回已验证收据。"""

        return MappingProxyType(
            {
                "base_checkpoint": self.base_checkpoint,
                "eagle_support": self.eagle_support,
            }
        )

    @property
    def checkpoint_candidates(self) -> tuple[Path, ...]:
        """返回主资产中声明的 safetensors 候选。"""

        return tuple(
            self.base_checkpoint.root / item.path
            for item in self.base_checkpoint.manifest.files
            if item.path.endswith(".safetensors")
        )

    @property
    def tokenizer_or_processor_assets(self) -> tuple[Path, ...]:
        """返回 Eagle processor 支持根。"""

        return (self.eagle_root,)

    @property
    def backbone_assets(self) -> tuple[Path, ...]:
        """返回 Eagle backbone 支持根。"""

        return (self.eagle_root,)

    @property
    def provenance(self) -> tuple[AssetProvenanceRecord, ...]:
        """返回两个不可变收据的来源身份。"""

        return tuple(
            AssetProvenanceRecord(
                asset.manifest.source_url,
                asset.manifest.revision,
                asset.identity,
            )
            for asset in (self.base_checkpoint, self.eagle_support)
        )

    @property
    def license_records(self) -> tuple[AssetLicenseRecord, ...]:
        """保持 checkpoint 与支持数据许可独立。"""

        return tuple(
            AssetLicenseRecord(
                asset.manifest.key,
                asset.manifest.license_name,
                asset.manifest.license_file_path,
                asset.manifest.redistribution,
            )
            for asset in (self.base_checkpoint, self.eagle_support)
        )

    def validate(self) -> None:
        """重新验证固定规范收据且不读取资产内容。"""

        _require_receipt(self.base_checkpoint, GR00T_N1D6_ASSET_SPEC)
        _require_receipt(self.eagle_support, GR00T_N1D6_EAGLE_SUPPORT_SPEC)

    @property
    def eagle_root(self):
        """返回声明的 Eagle 支持数据子目录。"""

        return self.eagle_support.root / EAGLE_SUPPORT_SUBDIRECTORY

    @property
    def fingerprint(self) -> str:
        """返回 bundle 中两个规范身份的稳定摘要。"""

        payload = {
            "family_key": "gr00t_n1d6",
            "base_checkpoint": self.base_checkpoint.identity,
            "eagle_support": self.eagle_support.identity,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


GR00T_N1D6_BUNDLE_REQUIREMENTS = (
    ModelAssetBundleRequirement("base_checkpoint", GR00T_N1D6_ASSET_SPEC),
    ModelAssetBundleRequirement("eagle_support", GR00T_N1D6_EAGLE_SUPPORT_SPEC),
)


def _require_receipt(receipt: object, spec: ModelAssetSpec) -> None:
    """仅检查已由 store 签发的不可变规范身份。"""

    if not isinstance(receipt, ResolvedModelAsset):
        raise TypeError("asset bundle members must be verified store receipts")
    if (
        receipt.manifest.key != spec.key
        or receipt.manifest.revision != spec.revision
        or receipt.identity != spec.identity
    ):
        raise ValueError(f"asset receipt does not satisfy {spec.key!r}")


__all__ = [
    "EAGLE_SUPPORT_SUBDIRECTORY",
    "GR00T_N1D6_BUNDLE_REQUIREMENTS",
    "Gr00tModelAssetBundle",
    "ModelAssetBundleRequirement",
    "VerifiedModelAssetBundle",
]
