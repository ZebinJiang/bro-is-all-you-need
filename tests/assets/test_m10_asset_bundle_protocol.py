"""M10 通用已验证资产包协议测试。"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from autovla.assets import (
    AssetLicenseRecord,
    AssetProvenanceRecord,
    ModelAssetBundle,
    ModelAssetConfigurationError,
)


class _BundleShape:
    """提供协议规定的全部不可变身份字段。"""

    family_key = "pi0_5"
    revision = "a" * 40
    root = Path("/verified/pi0_5")
    manifest: ClassVar[dict[str, object]] = {}
    assets_by_role: ClassVar[dict[str, object]] = {}
    checkpoint_candidates = (Path("/verified/pi0_5/model.safetensors"),)
    tokenizer_or_processor_assets: tuple[Path, ...] = ()
    backbone_assets: tuple[Path, ...] = ()
    provenance: tuple[AssetProvenanceRecord, ...] = ()
    license_records: tuple[AssetLicenseRecord, ...] = ()
    fingerprint = "b" * 64

    def validate(self) -> None:
        """测试协议签发者的封闭校验入口。"""

        if not self.root.is_absolute():
            raise ValueError("asset root must be absolute")


def test_asset_bundle_protocol_is_structural_and_keeps_provenance_typed() -> None:
    """协议接受家族实现，并保持来源与许可记录为独立类型。"""

    bundle = _BundleShape()
    assert isinstance(bundle, ModelAssetBundle)
    bundle.validate()
    provenance = AssetProvenanceRecord(
        "https://example.com/public-model",
        "c" * 40,
        "d" * 64,
    )
    license_record = AssetLicenseRecord(
        "pi0_5_checkpoint",
        "separate-weight-terms",
        "LICENSE",
        "restricted",
    )
    assert provenance.revision == "c" * 40
    assert license_record.license_file_path == "LICENSE"


def test_asset_provenance_rejects_mutable_or_credentialed_identity() -> None:
    """来源必须固定 revision、公开 URL 且不携带凭据。"""

    with pytest.raises(ModelAssetConfigurationError, match="public HTTPS"):
        AssetProvenanceRecord("https://user:secret@example.com/model", "c" * 40, "d" * 64)
    with pytest.raises(ModelAssetConfigurationError, match="pinned identities"):
        AssetProvenanceRecord("https://example.com/model", "main", "d" * 64)
