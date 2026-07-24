"""GR00T N1.7 checkpoint 与 gated Cosmos 双收据资产包。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from autovla.assets import (
    AssetLicenseRecord,
    AssetProvenanceRecord,
    ModelAssetManifest,
    ResolvedModelAsset,
)
from autovla.models.families.gr00t_n1d7.config import (
    COSMOS_BACKBONE_ID,
    GR00T_N1D7_CHECKPOINT_REVISION,
)

_IMMUTABLE_REVISION = re.compile(r"[0-9a-f]{40}")
_UNSAFE_MODEL_SUFFIXES = (".bin", ".pt", ".pth", ".pkl", ".pickle")
_COSMOS_CONSUMED_FILES = frozenset(
    {
        "chat_template.json",
        "config.json",
        "merges.txt",
        "preprocessor_config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "video_preprocessor_config.json",
        "vocab.json",
    }
)


class Gr00tN1d7AssetBundle:
    """只接受许可已解决且访问已接受的两个 verified store 收据。

    当前官方 checkpoint 的打包 LICENSE 与模型卡冲突。默认构造立即
    失败。Cosmos 还必须提供单独的 gated-access、revision 和许可收据。
    """

    def __init__(
        self,
        checkpoint: ResolvedModelAsset | None = None,
        cosmos: ResolvedModelAsset | None = None,
        *,
        checkpoint_license_resolved: bool = False,
        cosmos_access_accepted: bool = False,
    ) -> None:
        """按许可、访问、类型和 revision 顺序关闭资产门。"""

        if type(checkpoint_license_resolved) is not bool or not checkpoint_license_resolved:
            raise RuntimeError(
                "GR00T N1.7 checkpoint license conflict is unresolved; execution is forbidden"
            )
        if type(cosmos_access_accepted) is not bool or not cosmos_access_accepted:
            raise RuntimeError("gated Cosmos asset receipt and access acceptance are required")
        if not isinstance(checkpoint, ResolvedModelAsset) or not isinstance(
            cosmos, ResolvedModelAsset
        ):
            raise TypeError("N1.7 assets must be verified model-store receipts")
        if checkpoint.manifest.family_key != "gr00t_n1d7":
            raise ValueError("checkpoint receipt must belong to gr00t_n1d7")
        if checkpoint.manifest.revision != GR00T_N1D7_CHECKPOINT_REVISION:
            raise ValueError("checkpoint receipt revision is not pinned")
        if cosmos.manifest.public_identifier != COSMOS_BACKBONE_ID:
            raise ValueError("backbone receipt must identify gated Cosmos-Reason2-2B")
        self._checkpoint = checkpoint
        self._cosmos = cosmos
        self.validate()

    @property
    def family_key(self) -> str:
        """返回共享资产协议家族键。"""

        return "gr00t_n1d7"

    @property
    def revision(self) -> str:
        """返回主 checkpoint revision。"""

        return self._checkpoint.manifest.revision

    @property
    def root(self) -> Path:
        """返回主 checkpoint 本地根。"""

        return self._checkpoint.root

    @property
    def cosmos_revision(self) -> str:
        """返回 gated Cosmos verified receipt 的精确不可变 revision。"""

        return self._cosmos.manifest.revision

    @property
    def manifest(self) -> Mapping[str, ModelAssetManifest]:
        """按角色返回不可变清单。"""

        return MappingProxyType(
            {
                "base_checkpoint": self._checkpoint.manifest,
                "cosmos_backbone": self._cosmos.manifest,
            }
        )

    @property
    def assets_by_role(self) -> Mapping[str, ResolvedModelAsset]:
        """按角色返回 verified store 收据。"""

        return MappingProxyType(
            {"base_checkpoint": self._checkpoint, "cosmos_backbone": self._cosmos}
        )

    @property
    def checkpoint_candidates(self) -> tuple[Path, ...]:
        """返回主清单中声明的 safetensors shard。"""

        return tuple(
            self.root / item.path
            for item in self._checkpoint.manifest.files
            if item.path.endswith(".safetensors")
        )

    @property
    def tokenizer_or_processor_assets(self) -> tuple[Path, ...]:
        """返回主 processor 与 Cosmos tokenizer 根。"""

        return (self.root, self._cosmos.root)

    @property
    def backbone_assets(self) -> tuple[Path, ...]:
        """返回 gated Cosmos 本地根。"""

        return (self._cosmos.root,)

    @property
    def provenance(self) -> tuple[AssetProvenanceRecord, ...]:
        """返回两个固定来源身份。"""

        return tuple(
            AssetProvenanceRecord(
                asset.manifest.source_url,
                asset.manifest.revision,
                asset.identity,
            )
            for asset in (self._checkpoint, self._cosmos)
        )

    @property
    def license_records(self) -> tuple[AssetLicenseRecord, ...]:
        """保持 checkpoint 与 Cosmos 许可分离。"""

        return tuple(
            AssetLicenseRecord(
                asset.manifest.key,
                asset.manifest.license_name,
                asset.manifest.license_file_path,
                asset.manifest.redistribution,
            )
            for asset in (self._checkpoint, self._cosmos)
        )

    @property
    def fingerprint(self) -> str:
        """返回只绑定两个 verified receipt 的稳定摘要。"""

        payload = {
            "family_key": self.family_key,
            "checkpoint": self._checkpoint.identity,
            "cosmos": self._cosmos.identity,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate(self) -> None:
        """重新校验收据身份、根路径与 safetensors-only 边界。"""

        for asset in (self._checkpoint, self._cosmos):
            if not asset.root.is_absolute() or len(asset.identity) != 64:
                raise ValueError("asset receipts must have absolute roots and stable identities")
            if not _IMMUTABLE_REVISION.fullmatch(asset.manifest.revision):
                raise ValueError("N1.7 model assets require immutable 40-character revisions")
            if any(item.path.endswith(_UNSAFE_MODEL_SUFFIXES) for item in asset.manifest.files):
                raise ValueError("arbitrary pickle model formats are forbidden")
        if not self.checkpoint_candidates:
            raise ValueError("checkpoint receipt must inventory safetensors shards")
        # Cosmos 仅提供本地 config/processor/tokenizer; GR00T checkpoint 严格加载全部骨干权重。
        cosmos_paths = frozenset(item.path for item in self._cosmos.manifest.files)
        missing_cosmos = tuple(sorted(_COSMOS_CONSUMED_FILES - cosmos_paths))
        if missing_cosmos:
            raise ValueError(f"Cosmos receipt lacks consumed local assets: {missing_cosmos}")


__all__ = ["Gr00tN1d7AssetBundle"]
