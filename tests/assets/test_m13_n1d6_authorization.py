"""M13 N1D6 精确授权策略与单进程校验复用回归。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from autovla.assets import (
    GR00T_N1D6_ASSET_SPEC,
    GR00T_N1D6_BASE_AUTHORIZATION_POLICY,
    GR00T_N1D6_EAGLE_AUTHORIZATION_POLICY,
    GR00T_N1D6_EAGLE_SUPPORT_SPEC,
    AssetAuthorizationDecision,
    AuthorizedModelAsset,
    LocalModelAssetProvider,
    ModelAssetFile,
    ModelAssetSpec,
    ModelAssetStore,
    resolve_n1d6_authorized_assets,
    reuse_authorized_assets,
)
from autovla.assets.errors import ModelAssetAuthorizationError


def test_n1d6_policies_bind_exact_assets_and_require_external_terms_evidence(
    tmp_path: Path,
) -> None:
    """策略固定 key/revision/spec 且缺少证据路径时不推断用户接受。"""

    base = GR00T_N1D6_BASE_AUTHORIZATION_POLICY
    eagle = GR00T_N1D6_EAGLE_AUTHORIZATION_POLICY
    assert (base.asset_key, base.revision, base.spec_identity) == (
        GR00T_N1D6_ASSET_SPEC.key,
        GR00T_N1D6_ASSET_SPEC.revision,
        GR00T_N1D6_ASSET_SPEC.identity,
    )
    assert (eagle.asset_key, eagle.revision, eagle.spec_identity) == (
        GR00T_N1D6_EAGLE_SUPPORT_SPEC.key,
        GR00T_N1D6_EAGLE_SUPPORT_SPEC.revision,
        GR00T_N1D6_EAGLE_SUPPORT_SPEC.identity,
    )
    assert all(
        item.required_state.value == "accepted_by_user"
        for policy in (base, eagle)
        for item in policy.terms_requirements
    )
    with pytest.raises(
        ModelAssetAuthorizationError,
        match="ASSET_EVIDENCE_PATH_MISSING",
    ):
        resolve_n1d6_authorized_assets(asset_root=tmp_path, evidence_paths={})


def test_authorized_reuse_skips_second_hash_but_rechecks_manifest_and_sizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一组合上下文复用完整验证结果,不再次读取权重摘要。"""

    license_bytes = b"test terms\n"
    weight_bytes = b"contract fixture only\n"
    spec = ModelAssetSpec(
        key="m13_reuse_fixture",
        family_key="gr00t_n1d6",
        provider="local",
        source_url="https://example.invalid/m13-reuse",
        public_identifier="m13/reuse",
        repository="m13/reuse",
        revision="1" * 40,
        license_name="test",
        license_file_path="LICENSE",
        use_limitation="contract fixture only",
        redistribution="not distributed",
        checksum_policy="sha256-size-v1",
        files=(
            ModelAssetFile(
                "LICENSE",
                len(license_bytes),
                hashlib.sha256(license_bytes).hexdigest(),
                "license",
            ),
            ModelAssetFile(
                "weights/tiny.safetensors",
                len(weight_bytes),
                hashlib.sha256(weight_bytes).hexdigest(),
                "base_model_weights",
            ),
        ),
    )
    source = tmp_path / "source"
    (source / "weights").mkdir(parents=True)
    (source / "LICENSE").write_bytes(license_bytes)
    (source / "weights/tiny.safetensors").write_bytes(weight_bytes)
    store = ModelAssetStore(tmp_path / "store")
    resolved = store.fetch(spec, LocalModelAssetProvider(source))
    authorized = AuthorizedModelAsset(
        resolved=resolved,
        authorization=AssetAuthorizationDecision(
            authorized=True,
            first_blocker=None,
            policy_identity="2" * 64,
            access_receipt_identity="3" * 64,
            terms_receipt_identities=("4" * 64,),
            acquisition_receipt_identity=resolved.acquisition_receipt.fingerprint,
            verification_receipt_identity=resolved.verification_receipt.fingerprint,
        ),
    )
    calls = 0

    def _unexpected_hash(path: Path) -> str:
        """任何摘要读取都说明复用边界失效。"""

        nonlocal calls
        calls += 1
        raise AssertionError(f"unexpected second hash: {path}")

    monkeypatch.setattr("autovla.assets.store._sha256", _unexpected_hash)
    with reuse_authorized_assets((authorized,)):
        reused = ModelAssetStore(tmp_path / "store").verify(spec)
    assert reused is resolved
    assert calls == 0
