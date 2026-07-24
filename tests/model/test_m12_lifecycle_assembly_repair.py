"""M12 lifecycle 授权 assembly 与 promotable readiness 聚焦测试。"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import cast

import pytest

from autovla.assets import (
    AssetAccessReceipt,
    AssetAccessState,
    AssetAuthorizationPolicy,
    AssetLifecycleEvidence,
    AssetTermsAcceptanceAuthority,
    AssetTermsKind,
    AssetTermsReceipt,
    AssetTermsRequirement,
    AssetTermsState,
    AuthorizedModelAsset,
    ModelAssetAcquisition,
    ModelAssetFile,
    ModelAssetManifest,
    ModelAssetSpec,
    ResolvedModelAsset,
    evaluate_asset_authorization,
)
from autovla.models.activation import (
    RuntimeActivationReceipt,
    require_activation,
    runtime_topology_fingerprint,
)
from autovla.models.assembly import ModelAssemblyRequest
from autovla.models.assembly.contracts import (
    RuntimeAssemblyInput,
    assemble_runtime_bundle,
)
from autovla.models.readiness import (
    DeepSpeedStage,
    DistributedStrategyKind,
    ModelFamilyReadinessSnapshot,
    PrecisionMode,
    RuntimeEvidenceKind,
    RuntimeEvidenceReceipt,
    RuntimeOperation,
    RuntimeTopology,
    RuntimeValidationKey,
)
from autovla.models.readiness_io import (
    PromotableReadinessDocument,
    ReadinessPersistenceError,
    decode_promotable_readiness_document,
    encode_promotable_readiness_document,
)
from autovla.runtime_profiles.contracts import (
    CudaCompatibilityIntent,
    ResolvedPackage,
    ResolvedRuntimeLock,
    RuntimeEnvironmentReceipt,
    RuntimeExecutionReceipt,
    RuntimeProfileSpec,
)

_TIMESTAMP = "2026-07-24T00:00:00Z"
_TERMS = hashlib.sha256(b"terms").hexdigest()
_ACCEPTANCE = hashlib.sha256(b"user receipt").hexdigest()


def _runtime_chain() -> tuple[
    RuntimeProfileSpec,
    ResolvedRuntimeLock,
    RuntimeEnvironmentReceipt,
]:
    """构造不依赖 Torch 的 conversion runtime 身份链。"""

    profile = RuntimeProfileSpec(
        profile_id="tiny_runtime",
        family_key="tiny_family",
        kind="conversion",
        descriptor_path=Path("configs/env/profiles/tiny.yaml"),
        uv_project=Path("envs/tiny"),
        requested_python_version="3.12",
        lock_status="resolved",
        lock_sha256="1" * 64,
        lock_accepted=True,
        exact_packages=(("numpy", "1.0.0"),),
        observed_lock_packages=(("numpy", "1.0.0"),),
        prohibited_packages=(),
        blockers=(),
        asset_license_gate_status="separate_receipt_required",
        requires_cuda=False,
        resolver_version="0.11.7",
        upstream_revision="2" * 40,
    )
    lock = ResolvedRuntimeLock(
        schema_version="autovla.resolved_runtime_lock.v2",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        python_version=profile.requested_python_version,
        python_implementation=profile.python_implementation,
        platform_intent=profile.platform_intent,
        resolver_name=profile.resolver_name,
        resolver_version=cast(str, profile.resolver_version),
        upstream_revision=cast(str, profile.upstream_revision),
        lock_sha256=cast(str, profile.lock_sha256),
        packages=(ResolvedPackage("numpy", "1.0.0", ()),),
        cuda_compatibility=CudaCompatibilityIntent(
            schema_version="autovla.cuda_compatibility_intent.v1",
            required=False,
            torch_compiled_cuda_version=None,
            cuda_runtime_version=None,
            cuda_driver_version=None,
            cudnn_version=None,
            nccl_version=None,
            compute_capabilities=(),
        ),
    )
    environment = RuntimeEnvironmentReceipt(
        schema_version="autovla.runtime_environment_receipt.v1",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        lock_fingerprint=lock.fingerprint,
        source_sha="3" * 40,
        environment_path=f".autovla_envs/{profile.profile_id}",
        installed_packages=(("numpy", "1.0.0"),),
        python_implementation="CPython",
        python_version="3.12.13",
        platform="linux-x86_64",
        torch_version=None,
        torch_compiled_cuda_version=None,
        cuda_runtime_version=None,
        cuda_driver_version=None,
        cudnn_version=None,
        nccl_version=None,
        gpu_name=None,
        gpu_compute_capability=None,
        deepspeed_compatible=None,
        offline_flags=(
            ("HF_HUB_OFFLINE", "1"),
            ("PIP_NO_INDEX", "1"),
            ("UV_OFFLINE", "1"),
        ),
        verification_status="pass",
        diagnostics=(),
    )
    return profile, lock, environment


def _authorized_asset(root: Path, *, key: str) -> AuthorizedModelAsset:
    """构造完整 access/terms/acquisition/verification 授权链。"""

    payload = b"fixture"
    license_payload = b"test terms\n"
    spec = ModelAssetSpec(
        key=key,
        family_key="tiny_family",
        provider="local",
        source_url=f"https://example.invalid/{key}",
        public_identifier=f"fixtures/{key}",
        repository=f"fixtures/{key}",
        revision="4" * 40,
        license_name="Test Terms",
        license_file_path="LICENSE",
        use_limitation="tests",
        redistribution="none",
        checksum_policy="sha256-size-v1",
        files=(
            ModelAssetFile(
                "LICENSE",
                len(license_payload),
                hashlib.sha256(license_payload).hexdigest(),
                "license",
            ),
            ModelAssetFile(
                "weights/tiny.safetensors",
                len(payload),
                hashlib.sha256(payload).hexdigest(),
                "base_model_weights",
            ),
        ),
    )
    manifest = ModelAssetManifest.from_spec(
        spec,
        acquired_at_utc=_TIMESTAMP,
        acquisition=ModelAssetAcquisition("provider-1", "downloader-1"),
    )
    resolved = ResolvedModelAsset.from_verified_store(root.resolve(), manifest)
    access = AssetAccessReceipt(
        spec.key,
        spec.identity,
        spec.revision,
        AssetAccessState.PUBLIC,
        _TIMESTAMP,
    )
    terms = AssetTermsReceipt(
        asset_key=spec.key,
        spec_identity=spec.identity,
        revision=spec.revision,
        terms_kind=AssetTermsKind.MODEL_CHECKPOINT,
        terms_identity=_TERMS,
        terms_source_url="https://example.invalid/terms",
        state=AssetTermsState.ACCEPTED_BY_USER,
        scope="tests",
        external_receipt_identity=_ACCEPTANCE,
        acceptance_authority=AssetTermsAcceptanceAuthority.USER,
        accepted_at_utc=_TIMESTAMP,
    )
    policy = AssetAuthorizationPolicy(
        asset_key=spec.key,
        spec_identity=spec.identity,
        revision=spec.revision,
        required_access_state=AssetAccessState.PUBLIC,
        terms_requirements=(
            AssetTermsRequirement(
                AssetTermsKind.MODEL_CHECKPOINT,
                _TERMS,
                "https://example.invalid/terms",
                "tests",
                AssetTermsState.ACCEPTED_BY_USER,
            ),
        ),
    )
    evidence = AssetLifecycleEvidence(
        (access,),
        (terms,),
        manifest.acquisition_receipt,
        manifest.verification_receipt,
    )
    return AuthorizedModelAsset(
        resolved,
        evaluate_asset_authorization(spec, policy, evidence),
    )


class _Bundle:
    """提供 RuntimeAssemblyInput 校验所需的最小资产包投影。"""

    family_key = "tiny_family"

    def __init__(self, asset: AuthorizedModelAsset) -> None:
        """绑定一个已验证资产。"""

        self.assets_by_role = MappingProxyType({"checkpoint": asset.resolved})
        self.manifest = MappingProxyType({"checkpoint": asset.resolved.manifest})
        self.fingerprint = "5" * 64


def _request(bundle: _Bundle) -> ModelAssemblyRequest:
    """构造只供副作用前校验读取的 exact request 类型。"""

    request = object.__new__(ModelAssemblyRequest)
    object.__setattr__(request, "family_key", "tiny_family")
    object.__setattr__(request, "asset_bundle", bundle)
    return request


def test_authorized_asset_is_consumed_before_family_factory_side_effect(
    tmp_path: Path,
) -> None:
    """请求出现未授权资产时,统一 caller 不得进入 family factory。"""

    authorized = _authorized_asset(tmp_path / "authorized", key="authorized")
    stale = _authorized_asset(tmp_path / "stale", key="stale")
    profile, lock, environment = _runtime_chain()
    runtime = RuntimeAssemblyInput(profile, lock, environment, (authorized,))
    good_request = _request(_Bundle(authorized))
    evidence = runtime.validate_request(good_request)
    assert evidence.evidence_ids == (authorized.fingerprint,)

    calls = 0

    class _Factory:
        """记录统一 caller 是否越过授权门。"""

        def __call__(self, request: ModelAssemblyRequest) -> object:
            """任何调用都表示授权顺序回归。"""

            nonlocal calls
            calls += 1
            return request

    with pytest.raises(ValueError, match="unauthorized or stale"):
        assemble_runtime_bundle(_request(_Bundle(stale)), _Factory(), runtime)
    assert calls == 0


def _promotion() -> tuple[
    ModelFamilyReadinessSnapshot,
    RuntimeValidationKey,
    RuntimeActivationReceipt,
]:
    """构造一条可重验的 prediction promotion chain。"""

    topology = RuntimeTopology(1, 1, 1, "h800")
    key = RuntimeValidationKey(
        family_key="tiny_family",
        definition_fingerprint="6" * 64,
        operation=RuntimeOperation.PREDICTION,
        runtime_profile_fingerprint="7" * 64,
        runtime_lock_fingerprint="8" * 64,
        environment_fingerprint="9" * 64,
        asset_fingerprint="a" * 64,
        checkpoint_fingerprint="b" * 64,
        data_binding_fingerprint="c" * 64,
        data_backend="canonical_batch",
        source_sha="d" * 40,
        command_fingerprint="e" * 64,
        evidence_artifact_fingerprint="f" * 64,
        strategy=DistributedStrategyKind.SINGLE_GPU,
        deepspeed_stage=DeepSpeedStage.NONE,
        topology=topology,
        precision=PrecisionMode.BF16,
    )
    receipt = RuntimeEvidenceReceipt(
        "tiny-prediction",
        key,
        RuntimeEvidenceKind.RUNTIME,
        "f" * 64,
        True,
    )
    execution = RuntimeExecutionReceipt(
        schema_version="autovla.runtime_execution_receipt.v2",
        profile_id="tiny_runtime",
        profile_fingerprint=cast(str, key.runtime_profile_fingerprint),
        lock_fingerprint=cast(str, key.runtime_lock_fingerprint),
        environment_fingerprint=cast(str, key.environment_fingerprint),
        source_sha=cast(str, key.source_sha),
        asset_fingerprint=cast(str, key.asset_fingerprint),
        command_name="predict",
        command_fingerprint=cast(str, key.command_fingerprint),
        topology_fingerprint=runtime_topology_fingerprint(key),
        evidence_path="runs/tmp/m12/prediction.json",
        evidence_sha256=cast(str, key.evidence_artifact_fingerprint),
        operation=key.operation.value,
        status="pass",
        diagnostics=(),
    )
    promotion = RuntimeActivationReceipt(
        receipt,
        execution,
        key.checkpoint_fingerprint,
        key.data_binding_fingerprint,
        runtime_topology_fingerprint(key),
    )
    snapshot = ModelFamilyReadinessSnapshot.derive(
        key.family_key,
        key.definition_fingerprint,
        (receipt,),
    )
    return snapshot, key, promotion


def test_promotable_json_revalidates_execution_and_full_identity_chain() -> None:
    """普通 readiness 无法自授权,canonical promotion document 可严格往返。"""

    snapshot, key, promotion = _promotion()
    plain = PromotableReadinessDocument({key.family_key: snapshot}, {})
    with pytest.raises(ReadinessPersistenceError, match="lacks a canonical"):
        plain.require(key.family_key, key)
    with pytest.raises(TypeError, match="required positional argument"):
        require_activation(snapshot, key)  # type: ignore[call-arg]

    encoded = encode_promotable_readiness_document(
        {key.family_key: snapshot},
        (promotion,),
    )
    decoded = decode_promotable_readiness_document(
        encoded,
        {key.family_key: key.definition_fingerprint},
    )
    assert decoded.require(key.family_key, key) == promotion.readiness_receipt.receipt_id

    stale_execution = replace(
        promotion.execution_receipt,
        command_fingerprint="0" * 64,
    )
    with pytest.raises(ValueError, match="command identity drifted"):
        RuntimeActivationReceipt(
            promotion.readiness_receipt,
            stale_execution,
            key.checkpoint_fingerprint,
            key.data_binding_fingerprint,
            promotion.topology_fingerprint,
        )


def test_all_official_families_delegate_to_the_same_runtime_caller() -> None:
    """N1D6、N1D7、Pi0.5 不得各自新建第二套 runtime assembly。"""

    root = Path(__file__).resolve().parents[2]
    for relative in (
        "autovla/models/families/gr00t_n1d6/factory.py",
        "autovla/models/families/gr00t_n1d7/factory.py",
        "autovla/models/families/pi0_5/factory.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert "def build_runtime_bundle(" in source
        assert "return assemble_runtime_bundle(request, self, runtime)" in source
