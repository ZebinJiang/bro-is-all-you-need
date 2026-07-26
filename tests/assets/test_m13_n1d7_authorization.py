"""M13 N1D7 家族拥有的授权策略与身份传播回归。"""

from __future__ import annotations

import hashlib
import inspect
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from autovla.assets import (
    AssetAccessReceipt,
    AssetAccessState,
    AssetLifecycleEvidence,
    AssetTermsAcceptanceAuthority,
    AssetTermsReceipt,
    AssetTermsState,
    AuthorizedModelAsset,
    ModelAssetAcquisition,
    ModelAssetFile,
    ModelAssetManifest,
    ModelAssetSpec,
    ResolvedModelAsset,
    evaluate_asset_authorization,
)
from autovla.assets.errors import ModelAssetAuthorizationError
from autovla.models.assembly import ModelRuntimeAssetEvidence
from autovla.models.families.gr00t_n1d7.assets import (
    GR00T_N1D7_AUTHORIZATION_POLICY,
    Gr00tN1d7AssetBundle,
    Gr00tN1d7AuthorizationReceipt,
)
from autovla.models.families.gr00t_n1d7.config import (
    COSMOS_BACKBONE_ID,
    GR00T_N1D7_CHECKPOINT_ID,
    GR00T_N1D7_CHECKPOINT_REVISION,
)

_TIMESTAMP = "2026-07-25T00:00:00Z"
_COSMOS_REVISION = "a" * 40
_COSMOS_FILES = (
    "chat_template.json",
    "config.json",
    "merges.txt",
    "preprocessor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "video_preprocessor_config.json",
    "vocab.json",
)


def _file(path: str, role: str) -> ModelAssetFile:
    """构造无需真实 payload 的固定清单成员。"""

    content = f"contract:{path}".encode()
    return ModelAssetFile(path, len(content), hashlib.sha256(content).hexdigest(), role)


def _spec(role: str) -> ModelAssetSpec:
    """构造符合家族身份但不访问文件系统的精确规范。"""

    if role == "base_checkpoint":
        return ModelAssetSpec(
            key="gr00t_n1d7_checkpoint",
            family_key="gr00t_n1d7",
            provider="huggingface",
            source_url="https://huggingface.co/nvidia/GR00T-N1.7-3B",
            public_identifier=GR00T_N1D7_CHECKPOINT_ID,
            repository=GR00T_N1D7_CHECKPOINT_ID,
            revision=GR00T_N1D7_CHECKPOINT_REVISION,
            license_name="fixture checkpoint terms",
            license_file_path="LICENSE",
            use_limitation="authorization contract fixture only",
            redistribution="not distributed",
            checksum_policy="sha256-size-v1",
            files=(
                _file("LICENSE", "license"),
                _file("model-00001-of-00001.safetensors", "base_model_weights"),
                _file("processor_config.json", "processor_config"),
                _file("statistics.json", "normalization_statistics"),
            ),
        )
    if role == "cosmos_backbone":
        return ModelAssetSpec(
            key="cosmos_reason2_2b_gated",
            family_key="gr00t_n1d7",
            provider="huggingface",
            source_url="https://huggingface.co/nvidia/Cosmos-Reason2-2B",
            public_identifier=COSMOS_BACKBONE_ID,
            repository=COSMOS_BACKBONE_ID,
            revision=_COSMOS_REVISION,
            license_name="fixture Cosmos terms",
            license_file_path="LICENSE",
            use_limitation="authorization contract fixture only",
            redistribution="not distributed",
            checksum_policy="sha256-size-v1",
            files=(
                _file("LICENSE", "license"),
                *(_file(path, "processor_config") for path in _COSMOS_FILES),
            ),
        )
    raise ValueError(f"unknown fixture role: {role}")


def _authorized(
    tmp_path: Path,
    role: str,
    *,
    external_identity: str,
) -> AuthorizedModelAsset:
    """由共享生命周期评估器签发测试授权资产。"""

    spec = _spec(role)
    manifest = ModelAssetManifest.from_spec(
        spec,
        acquired_at_utc=_TIMESTAMP,
        acquisition=ModelAssetAcquisition(
            provider_version="fixture-provider-1",
            downloader_version="fixture-downloader-1",
        ),
    )
    resolved = ResolvedModelAsset.from_verified_store(tmp_path / role, manifest)
    policy = GR00T_N1D7_AUTHORIZATION_POLICY.policy_for(role, spec)
    access = AssetAccessReceipt(
        asset_key=spec.key,
        spec_identity=spec.identity,
        revision=spec.revision,
        state=policy.required_access_state,
        observed_at_utc=_TIMESTAMP,
        evidence_identity=(
            "b" * 64 if policy.required_access_state is AssetAccessState.GRANTED else None
        ),
        evidence_source_url=(
            "https://example.invalid/external-access-receipt"
            if policy.required_access_state is AssetAccessState.GRANTED
            else None
        ),
    )
    requirement = policy.terms_requirements[0]
    terms = AssetTermsReceipt(
        asset_key=spec.key,
        spec_identity=spec.identity,
        revision=spec.revision,
        terms_kind=requirement.terms_kind,
        terms_identity=requirement.terms_identity,
        terms_source_url=requirement.terms_source_url,
        state=AssetTermsState.ACCEPTED_BY_USER,
        scope=requirement.scope,
        external_receipt_identity=external_identity,
        acceptance_authority=AssetTermsAcceptanceAuthority.USER,
        accepted_at_utc=_TIMESTAMP,
    )
    evidence = AssetLifecycleEvidence(
        access_receipts=(access,),
        terms_receipts=(terms,),
        acquisition_receipt=manifest.acquisition_receipt,
        verification_receipt=manifest.verification_receipt,
    )
    decision = evaluate_asset_authorization(spec, policy, evidence)
    assert decision.authorized
    return AuthorizedModelAsset(resolved=resolved, authorization=decision)


def _receipt(
    tmp_path: Path,
    *,
    checkpoint_external_identity: str = "c" * 64,
) -> Gr00tN1d7AuthorizationReceipt:
    """构造身份完整的双资产测试授权收据。"""

    return Gr00tN1d7AuthorizationReceipt(
        checkpoint=_authorized(
            tmp_path,
            "base_checkpoint",
            external_identity=checkpoint_external_identity,
        ),
        cosmos=_authorized(
            tmp_path,
            "cosmos_backbone",
            external_identity="d" * 64,
        ),
    )


def test_boolean_assertions_and_plain_verified_assets_cannot_open_bundle(
    tmp_path: Path,
) -> None:
    """布尔断言和普通 verified 资产都不能替代授权身份。"""

    parameters = inspect.signature(Gr00tN1d7AssetBundle).parameters
    assert "checkpoint_license_resolved" not in parameters
    assert "cosmos_access_accepted" not in parameters
    with pytest.raises(RuntimeError, match="caller-controlled assertions"):
        Gr00tN1d7AssetBundle(
            checkpoint_license_resolved=True,
            cosmos_access_accepted=True,
        )
    checkpoint = _authorized(
        tmp_path,
        "base_checkpoint",
        external_identity="c" * 64,
    ).resolved
    with pytest.raises(TypeError, match="Gr00tN1d7AuthorizationReceipt"):
        Gr00tN1d7AssetBundle(authorization=cast(Gr00tN1d7AuthorizationReceipt, checkpoint))


def test_authorized_bundle_binds_policy_and_external_receipt_identities(
    tmp_path: Path,
) -> None:
    """bundle、运行资产证据与外部收据身份保持同一闭环。"""

    first_receipt = _receipt(tmp_path)
    first = Gr00tN1d7AssetBundle(first_receipt)
    evidence = ModelRuntimeAssetEvidence(
        asset_bundle_fingerprint=first.fingerprint,
        manifest_fingerprint=first.manifest_fingerprint,
        evidence_ids=first.authorization_evidence_ids,
    )
    assert first.authorization_policy_identity == GR00T_N1D7_AUTHORIZATION_POLICY.fingerprint
    assert first.authorization_identity == first_receipt.fingerprint
    assert evidence.evidence_ids == tuple(
        sorted(receipt.fingerprint for receipt in first.authorization_receipts_by_role.values())
    )
    second = Gr00tN1d7AssetBundle(_receipt(tmp_path, checkpoint_external_identity="e" * 64))
    assert second.authorization_identity != first.authorization_identity
    assert second.fingerprint != first.fingerprint


def test_wrong_policy_identity_or_role_binding_is_rejected(tmp_path: Path) -> None:
    """授权决定必须来自当前家族策略且不能交换资产角色。"""

    receipt = _receipt(tmp_path)
    forged_checkpoint = AuthorizedModelAsset(
        resolved=receipt.checkpoint.resolved,
        authorization=replace(
            receipt.checkpoint.authorization,
            policy_identity="f" * 64,
        ),
    )
    with pytest.raises(
        ModelAssetAuthorizationError,
        match="N1D7_AUTHORIZATION_POLICY_IDENTITY_MISMATCH",
    ):
        Gr00tN1d7AuthorizationReceipt(
            checkpoint=forged_checkpoint,
            cosmos=receipt.cosmos,
        )
    with pytest.raises(ValueError, match="does not match role"):
        Gr00tN1d7AuthorizationReceipt(
            checkpoint=receipt.cosmos,
            cosmos=receipt.checkpoint,
        )
