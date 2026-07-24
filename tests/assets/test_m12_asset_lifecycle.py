"""M12 模型资产访问、条款、获取、验证与解析授权测试。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

import autovla.cli.assets as asset_cli
from autovla.assets import (
    AssetAccessReceipt,
    AssetAccessState,
    AssetAcquisitionReceipt,
    AssetAuthorizationPolicy,
    AssetAuthorizationPolicyRegistry,
    AssetLifecycleEvidence,
    AssetTermsAcceptanceAuthority,
    AssetTermsKind,
    AssetTermsReceipt,
    AssetTermsRequirement,
    AssetTermsState,
    AssetVerificationReceipt,
    AssetVerificationResult,
    LocalModelAssetProvider,
    MissingModelAssetError,
    ModelAssetAcquisition,
    ModelAssetAuthorizationError,
    ModelAssetConfigurationError,
    ModelAssetFile,
    ModelAssetIntegrityError,
    ModelAssetManifest,
    ModelAssetRegistry,
    ModelAssetResolver,
    ModelAssetSpec,
    ModelAssetStore,
    evaluate_asset_authorization,
)

_TIMESTAMP = "2026-07-24T00:00:00Z"
_TERMS_IDENTITY = hashlib.sha256(b"model checkpoint terms").hexdigest()
_EXTERNAL_RECEIPT_IDENTITY = hashlib.sha256(b"user-owned acceptance receipt").hexdigest()


def _spec(*, weight_path: str = "weights/tiny.safetensors") -> ModelAssetSpec:
    """构造只含微型文本身份的离线规范,不加载模型 payload。"""

    license_bytes = b"test terms\n"
    weight_bytes = b"not a model; contract fixture only\n"
    return ModelAssetSpec(
        key="tiny",
        family_key="tiny_family",
        provider="local",
        source_url="https://example.invalid/assets/tiny",
        public_identifier="fixtures/tiny",
        repository="fixtures/tiny",
        revision="1" * 40,
        license_name="Test Terms",
        license_file_path="LICENSE",
        use_limitation="contract tests only",
        redistribution="not applicable",
        checksum_policy="sha256-size-v1",
        files=(
            ModelAssetFile(
                "LICENSE",
                len(license_bytes),
                hashlib.sha256(license_bytes).hexdigest(),
                "license",
            ),
            ModelAssetFile(
                weight_path,
                len(weight_bytes),
                hashlib.sha256(weight_bytes).hexdigest(),
                "base_model_weights",
            ),
        ),
    )


def _manifest(spec: ModelAssetSpec) -> ModelAssetManifest:
    """从兼容清单创建独立 M12 获取与验证收据。"""

    return ModelAssetManifest.from_spec(
        spec,
        acquired_at_utc=_TIMESTAMP,
        acquisition=ModelAssetAcquisition(
            provider_version="test-provider-1",
            downloader_version="test-downloader-1",
        ),
    )


def _policy(spec: ModelAssetSpec) -> AssetAuthorizationPolicy:
    """要求公开访问和一份用户明确接受的 checkpoint 条款收据。"""

    return AssetAuthorizationPolicy(
        asset_key=spec.key,
        spec_identity=spec.identity,
        revision=spec.revision,
        required_access_state=AssetAccessState.PUBLIC,
        terms_requirements=(
            AssetTermsRequirement(
                terms_kind=AssetTermsKind.MODEL_CHECKPOINT,
                terms_identity=_TERMS_IDENTITY,
                terms_source_url="https://example.invalid/terms/model",
                scope="contract_tests",
                required_state=AssetTermsState.ACCEPTED_BY_USER,
            ),
        ),
    )


def _access(spec: ModelAssetSpec) -> AssetAccessReceipt:
    """构造无需代码代用户接受任何条款的公开访问收据。"""

    return AssetAccessReceipt(
        asset_key=spec.key,
        spec_identity=spec.identity,
        revision=spec.revision,
        state=AssetAccessState.PUBLIC,
        observed_at_utc=_TIMESTAMP,
    )


def _terms(
    spec: ModelAssetSpec,
    *,
    kind: AssetTermsKind = AssetTermsKind.MODEL_CHECKPOINT,
    state: AssetTermsState = AssetTermsState.ACCEPTED_BY_USER,
) -> AssetTermsReceipt:
    """构造显式引用用户外部收据的条款证据。"""

    accepted = state is AssetTermsState.ACCEPTED_BY_USER
    return AssetTermsReceipt(
        asset_key=spec.key,
        spec_identity=spec.identity,
        revision=spec.revision,
        terms_kind=kind,
        terms_identity=_TERMS_IDENTITY,
        terms_source_url="https://example.invalid/terms/model",
        state=state,
        scope="contract_tests",
        external_receipt_identity=(_EXTERNAL_RECEIPT_IDENTITY if accepted else None),
        acceptance_authority=(AssetTermsAcceptanceAuthority.USER if accepted else None),
        accepted_at_utc=_TIMESTAMP if accepted else None,
    )


def _evidence(spec: ModelAssetSpec) -> AssetLifecycleEvidence:
    """构造全部身份相互绑定的授权证据。"""

    manifest = _manifest(spec)
    return AssetLifecycleEvidence(
        access_receipts=(_access(spec),),
        terms_receipts=(_terms(spec),),
        acquisition_receipt=manifest.acquisition_receipt,
        verification_receipt=manifest.verification_receipt,
    )


def test_receipts_round_trip_strictly_and_fingerprint_deterministically() -> None:
    """四类收据严格往返,序列化顺序不影响稳定身份。"""

    spec = _spec()
    evidence = _evidence(spec)
    pairs = (
        (AssetAccessReceipt, evidence.access_receipts[0]),
        (AssetTermsReceipt, evidence.terms_receipts[0]),
        (AssetAcquisitionReceipt, evidence.acquisition_receipt),
        (AssetVerificationReceipt, evidence.verification_receipt),
    )
    for receipt_type, receipt in pairs:
        payload = receipt.to_dict()
        parsed = receipt_type.from_dict(dict(reversed(tuple(payload.items()))))
        assert parsed == receipt
        assert parsed.fingerprint == receipt.fingerprint
        payload["unknown"] = True
        with pytest.raises(ModelAssetConfigurationError, match="fields are not exact"):
            receipt_type.from_dict(payload)


def test_accepted_terms_require_explicit_external_user_receipt() -> None:
    """代码不能仅凭 accepted 状态替用户接受条款。"""

    spec = _spec()
    with pytest.raises(ModelAssetConfigurationError, match="external receipt"):
        AssetTermsReceipt(
            asset_key=spec.key,
            spec_identity=spec.identity,
            revision=spec.revision,
            terms_kind=AssetTermsKind.MODEL_CHECKPOINT,
            terms_identity=_TERMS_IDENTITY,
            terms_source_url="https://example.invalid/terms/model",
            state=AssetTermsState.ACCEPTED_BY_USER,
            scope="contract_tests",
            acceptance_authority=AssetTermsAcceptanceAuthority.USER,
            accepted_at_utc=_TIMESTAMP,
        )
    with pytest.raises(ModelAssetConfigurationError, match="acceptance evidence"):
        replace(_terms(spec), state=AssetTermsState.REQUIRED)


def test_terms_categories_are_not_substitutable_or_implicitly_merged() -> None:
    """checkpoint 条款不能代替 tokenizer、数据或转换条款。"""

    spec = _spec()
    checkpoint = _policy(spec).terms_requirements[0]
    tokenizer = AssetTermsRequirement(
        terms_kind=AssetTermsKind.TOKENIZER,
        terms_identity="2" * 64,
        terms_source_url="https://example.invalid/terms/tokenizer",
        scope="contract_tests",
        required_state=AssetTermsState.ACCEPTED_BY_USER,
    )
    policy = replace(_policy(spec), terms_requirements=(checkpoint, tokenizer))
    decision = evaluate_asset_authorization(spec, policy, _evidence(spec))
    assert decision.authorized is False
    assert decision.first_blocker == "ASSET_TERMS_RECEIPT_MISSING"


def test_authorization_rejects_contradictory_superseded_and_stale_receipts() -> None:
    """重复、被取代或 revision/spec 不匹配的收据全部失败关闭。"""

    spec = _spec()
    policy = _policy(spec)
    evidence = _evidence(spec)
    contradictory = replace(
        evidence,
        access_receipts=(evidence.access_receipts[0], evidence.access_receipts[0]),
    )
    assert (
        evaluate_asset_authorization(spec, policy, contradictory).first_blocker
        == "ASSET_ACCESS_RECEIPTS_CONTRADICTORY"
    )
    superseded = replace(
        evidence,
        terms_receipts=(replace(evidence.terms_receipts[0], superseded_by="3" * 64),),
    )
    assert (
        evaluate_asset_authorization(spec, policy, superseded).first_blocker
        == "ASSET_TERMS_RECEIPT_SUPERSEDED"
    )
    stale = replace(
        evidence,
        access_receipts=(replace(evidence.access_receipts[0], revision="4" * 40),),
    )
    assert (
        evaluate_asset_authorization(spec, policy, stale).first_blocker
        == "ASSET_ACCESS_RECEIPT_SPEC_MISMATCH"
    )


def test_partial_acquisition_and_verification_cannot_authorize() -> None:
    """缺少成员的获取或验证收据不能提升本地解析。"""

    spec = _spec()
    policy = _policy(spec)
    evidence = _evidence(spec)
    partial_acquisition = replace(
        evidence.acquisition_receipt,
        inventory=(spec.files[0],),
    )
    partial = replace(evidence, acquisition_receipt=partial_acquisition)
    assert (
        evaluate_asset_authorization(spec, policy, partial).first_blocker
        == "ASSET_ACQUISITION_RECEIPT_PARTIAL_OR_MISMATCHED"
    )

    rejected_verification = AssetVerificationReceipt(
        asset_key=spec.key,
        spec_identity=spec.identity,
        revision=spec.revision,
        acquisition_receipt_identity=evidence.acquisition_receipt.fingerprint,
        expected_inventory=spec.files,
        observed_inventory=(spec.files[0],),
        checksum_policy=spec.checksum_policy,
        size_verified=False,
        hashes_verified=False,
        safetensors_only=True,
        remote_code_allowed=False,
        result=AssetVerificationResult.REJECTED,
        verified_at_utc=_TIMESTAMP,
    )
    rejected = replace(evidence, verification_receipt=rejected_verification)
    assert (
        evaluate_asset_authorization(spec, policy, rejected).first_blocker
        == "ASSET_VERIFICATION_RECEIPT_PARTIAL_OR_REJECTED"
    )


def test_manifest_level_safetensors_policy_rejects_pickle_capable_weights() -> None:
    """权重角色必须为 safetensors,普通配置/许可文本不受后缀误判。"""

    safe = _manifest(_spec()).verification_receipt
    unsafe = _manifest(_spec(weight_path="weights/tiny.bin")).verification_receipt
    assert safe.result is AssetVerificationResult.VERIFIED
    assert safe.safetensors_only is True
    assert unsafe.result is AssetVerificationResult.REJECTED
    assert unsafe.safetensors_only is False


def test_store_rejects_unsafe_weight_manifest_before_atomic_publication(
    tmp_path: Path,
) -> None:
    """pickle 能力权重后缀在完成清单发布前被拒绝。"""

    spec = _spec(weight_path="weights/tiny.bin")
    source = tmp_path / "source"
    (source / "weights").mkdir(parents=True)
    (source / "LICENSE").write_bytes(b"test terms\n")
    (source / "weights/tiny.bin").write_bytes(b"not a model; contract fixture only\n")
    store = ModelAssetStore(tmp_path / "store")
    with pytest.raises(ModelAssetIntegrityError, match="safetensors-only"):
        store.fetch(spec, LocalModelAssetProvider(source))
    assert not store.asset_path(spec).exists()


def test_fetch_reuses_valid_bundle_without_overwrite(tmp_path: Path) -> None:
    """第二次显式 fetch 复用完整验证结果且不再次调用 provider。"""

    spec = _spec()
    source = tmp_path / "source"
    (source / "weights").mkdir(parents=True)
    (source / "LICENSE").write_bytes(b"test terms\n")
    (source / "weights/tiny.safetensors").write_bytes(b"not a model; contract fixture only\n")
    store = ModelAssetStore(tmp_path / "store")
    first = store.fetch(spec, LocalModelAssetProvider(source))

    class _MustNotFetch:
        """确认有效最终目录不会被覆盖或重新获取。"""

        name = "local"

        def fetch(
            self,
            selected: ModelAssetSpec,
            destination: Path,
        ) -> ModelAssetAcquisition:
            """任何调用都表示 no-overwrite 契约被破坏。"""

            raise AssertionError(f"unexpected fetch for {selected.key} at {destination}")

    second = store.fetch(spec, _MustNotFetch())
    assert second.manifest == first.manifest
    assert second.root == first.root


def test_resolver_binds_authorization_to_actual_local_completion_manifest(
    tmp_path: Path,
) -> None:
    """规范相同但获取实现身份陈旧时也必须失败关闭。"""

    spec = _spec()
    source = tmp_path / "source"
    (source / "weights").mkdir(parents=True)
    (source / "LICENSE").write_bytes(b"test terms\n")
    (source / "weights/tiny.safetensors").write_bytes(b"not a model; contract fixture only\n")
    store = ModelAssetStore(tmp_path / "store")
    local = store.fetch(spec, LocalModelAssetProvider(source))
    resolver = ModelAssetResolver(
        store,
        ModelAssetRegistry((spec,)),
        AssetAuthorizationPolicyRegistry((_policy(spec),)),
    )
    with pytest.raises(
        ModelAssetAuthorizationError,
        match="LOCAL_ACQUISITION_RECEIPT_IDENTITY_MISMATCH",
    ):
        resolver.resolve(spec.key, _evidence(spec))

    exact_evidence = AssetLifecycleEvidence(
        access_receipts=(_access(spec),),
        terms_receipts=(_terms(spec),),
        acquisition_receipt=local.acquisition_receipt,
        verification_receipt=local.verification_receipt,
    )
    assert resolver.resolve(spec.key, exact_evidence).root == local.root


def test_resolver_requires_authorization_before_local_payload_verification(
    tmp_path: Path,
) -> None:
    """缺少策略或证据时在 store 哈希/读取成员前失败。"""

    spec = _spec()
    store = ModelAssetStore(tmp_path / "store")
    registry = ModelAssetRegistry((spec,))
    resolver = ModelAssetResolver(store, registry)
    with pytest.raises(
        ModelAssetAuthorizationError,
        match="ASSET_AUTHORIZATION_POLICY_MISSING",
    ):
        resolver.resolve(spec.key)

    authorized_resolver = ModelAssetResolver(
        store,
        registry,
        AssetAuthorizationPolicyRegistry((_policy(spec),)),
    )
    with pytest.raises(
        ModelAssetAuthorizationError,
        match="ASSET_LIFECYCLE_EVIDENCE_MISSING",
    ):
        authorized_resolver.resolve(spec.key)
    with pytest.raises(MissingModelAssetError):
        authorized_resolver.resolve(spec.key, _evidence(spec))


def test_cli_terms_is_static_fail_closed_and_does_not_leak_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """terms 只输出静态状态,不读取 payload、访问网络或公开本地路径。"""

    spec = _spec()
    monkeypatch.setattr(
        asset_cli,
        "DEFAULT_MODEL_ASSET_REGISTRY",
        ModelAssetRegistry((spec,)),
    )
    root = tmp_path / "private" / "base_model"
    assert asset_cli.main(["--root", str(root), "--json", "terms", spec.key]) == 0
    payload = json.loads(capsys.readouterr().out)["result"]
    assert payload["access_state"] == "gated_unconfirmed"
    assert payload["terms_state"] == "required"
    assert payload["first_blocker"] == "ASSET_ACCESS_RECEIPT_MISSING"
    assert payload["runtime_authorized"] is False
    assert str(root) not in json.dumps(payload)


def test_cli_terms_reads_only_strict_user_owned_receipt_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """标准 receipt 根可展示状态,但仍不越过显式授权策略。"""

    spec = _spec()
    monkeypatch.setattr(
        asset_cli,
        "DEFAULT_MODEL_ASSET_REGISTRY",
        ModelAssetRegistry((spec,)),
    )
    root = tmp_path / "base_model"
    receipt_root = root / ".receipts" / spec.key / spec.revision
    terms_root = receipt_root / "terms"
    terms_root.mkdir(parents=True)
    (receipt_root / "access.json").write_text(
        json.dumps(_access(spec).to_dict()),
        encoding="utf-8",
    )
    (terms_root / "model_checkpoint.json").write_text(
        json.dumps(_terms(spec).to_dict()),
        encoding="utf-8",
    )

    assert asset_cli.main(["--root", str(root), "--json", "terms", spec.key]) == 0
    payload = json.loads(capsys.readouterr().out)["result"]
    assert payload["access_state"] == "public"
    assert payload["terms_state"] == "accepted_by_user"
    assert payload["first_blocker"] == "ASSET_AUTHORIZATION_POLICY_MISSING"
    assert payload["access_receipt_identity"] == _access(spec).fingerprint
    assert payload["terms_receipt_identities"] == [_terms(spec).fingerprint]
    assert payload["runtime_authorized"] is False

    (receipt_root / "unexpected.json").write_text("{}", encoding="utf-8")
    assert asset_cli.main(["--root", str(root), "--json", "terms", spec.key]) == 2
    error = json.loads(capsys.readouterr().out)
    assert "unexpected member" in error["error"]


def test_complete_exact_evidence_authorizes_without_merging_term_identities() -> None:
    """全部精确收据同时满足时才返回授权决定。"""

    spec = _spec()
    decision = evaluate_asset_authorization(spec, _policy(spec), _evidence(spec))
    assert decision.authorized is True
    assert decision.first_blocker is None
    assert len(decision.terms_receipt_identities) == 1
