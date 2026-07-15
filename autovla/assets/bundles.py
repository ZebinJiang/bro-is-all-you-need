"""由多个已验证资产收据组成的类型化模型资产包。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from autovla.assets.contracts import ModelAssetSpec, ResolvedModelAsset
from autovla.assets.registry import (
    GR00T_N1D6_ASSET_SPEC,
    GR00T_N1D6_EAGLE_SUPPORT_SPEC,
)
from autovla.assets.store import ModelAssetStore

EAGLE_SUPPORT_SUBDIRECTORY = "gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2"


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
]
