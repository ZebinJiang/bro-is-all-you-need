"""Pi0.5 已验证资产包及独立许可收据边界。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from autovla.assets import (
    AssetLicenseRecord,
    AssetProvenanceRecord,
    ModelAssetManifest,
    ResolvedModelAsset,
    VerifiedModelAssetBundle,
)


@dataclass(frozen=True, slots=True)
class Pi05AssetBundle:
    """把 checkpoint、Gemma/tokenizer 与统计收据保持为独立角色。"""

    verified: VerifiedModelAssetBundle

    def __post_init__(self) -> None:
        """要求全部运行角色先由共享资产 store 验证。"""

        if self.verified.family_key != "pi0_5":
            raise ValueError("Pi0.5 asset bundle requires family_key=pi0_5")
        required = {"checkpoint", "gemma_tokenizer", "normalization_statistics"}
        missing = required - set(self.verified.assets_by_role)
        if missing:
            raise ValueError(f"Pi0.5 asset bundle missing verified roles: {sorted(missing)}")
        self.validate()

    @classmethod
    def from_verified(cls, value: VerifiedModelAssetBundle) -> "Pi05AssetBundle":
        """从共享 store 已签发的包构造家族包,不读取资产字节。"""

        return cls(value)

    @property
    def family_key(self) -> str:
        """返回规范家族键。"""

        return self.verified.family_key

    @property
    def revision(self) -> str:
        """返回主资产固定 revision。"""

        return self.verified.revision

    @property
    def root(self) -> Path:
        """返回主资产绝对根。"""

        return self.verified.root

    @property
    def assets_by_role(self) -> Mapping[str, ResolvedModelAsset]:
        """返回共享包的只读角色映射。"""

        return self.verified.assets_by_role

    @property
    def manifest(self) -> Mapping[str, ModelAssetManifest]:
        """返回每个角色独立清单。"""

        return self.verified.manifest

    @property
    def checkpoint_candidates(self) -> tuple[Path, ...]:
        """只暴露 ``.safetensors`` 运行 checkpoint。"""

        candidates = self.verified.checkpoint_candidates
        if not candidates or any(path.suffix != ".safetensors" for path in candidates):
            raise ValueError("Pi0.5 runtime checkpoint candidates must be safetensors-only")
        return candidates

    @property
    def tokenizer_or_processor_assets(self) -> tuple[Path, ...]:
        """返回显式 tokenizer 与统计资产路径。"""

        return self.verified.tokenizer_or_processor_assets

    @property
    def backbone_assets(self) -> tuple[Path, ...]:
        """返回 Gemma/PaliGemma 资产路径。"""

        return self.verified.backbone_assets

    @property
    def provenance(self) -> tuple[AssetProvenanceRecord, ...]:
        """保持每个角色的来源身份。"""

        return self.verified.provenance

    @property
    def license_records(self) -> tuple[AssetLicenseRecord, ...]:
        """保持 Apache 源码与 Gemma/checkpoint 条款分离。"""

        return self.verified.license_records

    @property
    def fingerprint(self) -> str:
        """返回共享已验证资产身份。"""

        return self.verified.fingerprint

    def validate(self) -> None:
        """重新执行共享验证并拒绝远程代码收据。"""

        self.verified.validate()
        if any(item.remote_code_required for item in self.manifest.values()):
            raise ValueError("Pi0.5 assets must not require remote code")
