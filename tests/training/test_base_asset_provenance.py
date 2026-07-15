"""训练 checkpoint 的 immutable base asset provenance 测试。"""

from __future__ import annotations

import pytest

from autovla.training.checkpointing.manifest import BaseModelAssetProvenance


def test_base_asset_provenance_contains_identity_only() -> None:
    """provenance 不包含权重、副本路径或可变缓存位置。"""

    provenance = BaseModelAssetProvenance(
        key="gr00t_n1d6",
        revision="d0814e7ecb19202e7c8468b46098b0b7ef3a6d61",
        spec_identity_sha256="a" * 64,
    ).to_dict()
    assert set(provenance) == {"key", "revision", "spec_identity_sha256"}
    assert all("path" not in key and "weight" not in key for key in provenance)


def test_base_asset_provenance_rejects_moving_revision() -> None:
    """分支名或短 revision 不能作为 checkpoint 基础资产身份。"""

    with pytest.raises(ValueError, match="full lowercase Git SHA"):
        BaseModelAssetProvenance(
            key="gr00t_n1d6",
            revision="main",
            spec_identity_sha256="a" * 64,
        )
