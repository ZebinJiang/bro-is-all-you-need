"""M13 N1D6 精确资产策略、证据解析与单进程验证复用。"""

from __future__ import annotations

import json
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, cast

from autovla.assets.contracts import ModelAssetSpec, ResolvedModelAsset
from autovla.assets.errors import (
    ModelAssetAuthorizationError,
    ModelAssetConfigurationError,
)
from autovla.assets.lifecycle import (
    AssetAccessState,
    AssetAuthorizationPolicy,
    AssetAuthorizationPolicyRegistry,
    AssetLifecycleEvidence,
    AssetTermsKind,
    AssetTermsRequirement,
    AssetTermsState,
    AuthorizedModelAsset,
)
from autovla.assets.registry import (
    DEFAULT_MODEL_ASSET_REGISTRY,
    GR00T_N1D6_ASSET_SPEC,
    GR00T_N1D6_EAGLE_SUPPORT_SPEC,
)
from autovla.assets.store import ModelAssetResolver, ModelAssetStore

if TYPE_CHECKING:
    from contextvars import Token

_BASE_TERMS_URL = (
    "https://huggingface.co/nvidia/GR00T-N1.6-3B/blob/"
    "d0814e7ecb19202e7c8468b46098b0b7ef3a6d61/LICENSE"
)
_EAGLE_TERMS_URL = (
    "https://github.com/NVIDIA/Isaac-GR00T/blob/" "5dc80c4afd726b34faad1d8f7e007a13b34e4c88/LICENSE"
)
_ACTIVE_AUTHORIZED_ASSETS: ContextVar[tuple[AuthorizedModelAsset, ...]] = ContextVar(
    "autovla_active_authorized_assets",
    default=(),
)


def _license_identity(spec: ModelAssetSpec) -> str:
    """读取规范中唯一 license 成员的固定摘要。"""

    matches = tuple(
        item.sha256
        for item in spec.files
        if item.path == spec.license_file_path and item.role == "license"
    )
    if len(matches) != 1:
        raise ModelAssetConfigurationError(
            f"asset policy {spec.key!r} lacks one canonical license member"
        )
    return matches[0]


GR00T_N1D6_BASE_AUTHORIZATION_POLICY = AssetAuthorizationPolicy(
    asset_key=GR00T_N1D6_ASSET_SPEC.key,
    spec_identity=GR00T_N1D6_ASSET_SPEC.identity,
    revision=GR00T_N1D6_ASSET_SPEC.revision,
    required_access_state=AssetAccessState.GRANTED,
    terms_requirements=(
        AssetTermsRequirement(
            terms_kind=AssetTermsKind.MODEL_CHECKPOINT,
            terms_identity=_license_identity(GR00T_N1D6_ASSET_SPEC),
            terms_source_url=_BASE_TERMS_URL,
            scope="gr00t_n1d6_runtime",
            required_state=AssetTermsState.ACCEPTED_BY_USER,
        ),
        AssetTermsRequirement(
            terms_kind=AssetTermsKind.DATASET_CONTENT,
            terms_identity=_license_identity(GR00T_N1D6_ASSET_SPEC),
            terms_source_url=_BASE_TERMS_URL,
            scope="gr00t_n1d6_statistics",
            required_state=AssetTermsState.ACCEPTED_BY_USER,
        ),
    ),
)

GR00T_N1D6_EAGLE_AUTHORIZATION_POLICY = AssetAuthorizationPolicy(
    asset_key=GR00T_N1D6_EAGLE_SUPPORT_SPEC.key,
    spec_identity=GR00T_N1D6_EAGLE_SUPPORT_SPEC.identity,
    revision=GR00T_N1D6_EAGLE_SUPPORT_SPEC.revision,
    required_access_state=AssetAccessState.PUBLIC,
    terms_requirements=(
        AssetTermsRequirement(
            terms_kind=AssetTermsKind.CODE_LICENSE,
            terms_identity=_license_identity(GR00T_N1D6_EAGLE_SUPPORT_SPEC),
            terms_source_url=_EAGLE_TERMS_URL,
            scope="gr00t_n1d6_eagle_source",
            required_state=AssetTermsState.ACCEPTED_BY_USER,
        ),
        AssetTermsRequirement(
            terms_kind=AssetTermsKind.TOKENIZER,
            terms_identity=_license_identity(GR00T_N1D6_EAGLE_SUPPORT_SPEC),
            terms_source_url=_EAGLE_TERMS_URL,
            scope="gr00t_n1d6_eagle_tokenizer",
            required_state=AssetTermsState.ACCEPTED_BY_USER,
        ),
    ),
)

GR00T_N1D6_AUTHORIZATION_POLICY_REGISTRY = AssetAuthorizationPolicyRegistry(
    (
        GR00T_N1D6_BASE_AUTHORIZATION_POLICY,
        GR00T_N1D6_EAGLE_AUTHORIZATION_POLICY,
    )
)


def load_asset_lifecycle_evidence(path: Path) -> AssetLifecycleEvidence:
    """读取一个显式 JSON 证据文件,不创建或补全任何收据。"""

    if path.is_symlink() or not path.is_file():
        raise ModelAssetConfigurationError(f"asset lifecycle evidence is not a real file: {path}")
    try:
        payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelAssetConfigurationError(
            f"asset lifecycle evidence is invalid JSON: {path}"
        ) from exc
    return AssetLifecycleEvidence.from_dict(payload)


def resolve_n1d6_authorized_assets(
    *,
    asset_root: Path,
    evidence_paths: Mapping[str, Path],
) -> tuple[AuthorizedModelAsset, ...]:
    """从两个显式证据文件解析并完整验证 N1D6 双资产。"""

    expected_specs = (
        GR00T_N1D6_ASSET_SPEC,
        GR00T_N1D6_EAGLE_SUPPORT_SPEC,
    )
    expected_keys = {spec.key for spec in expected_specs}
    supplied_keys = set(evidence_paths)
    missing = sorted(expected_keys - supplied_keys)
    unknown = sorted(supplied_keys - expected_keys)
    if missing:
        raise ModelAssetAuthorizationError(
            missing[0],
            "ASSET_EVIDENCE_PATH_MISSING",
        )
    if unknown:
        raise ModelAssetAuthorizationError(
            unknown[0],
            "ASSET_EVIDENCE_PATH_UNEXPECTED",
        )
    store = ModelAssetStore(asset_root)
    resolver = ModelAssetResolver(
        store,
        DEFAULT_MODEL_ASSET_REGISTRY,
        GR00T_N1D6_AUTHORIZATION_POLICY_REGISTRY,
    )
    authorized = tuple(
        resolver.resolve_authorized(
            spec.key,
            load_asset_lifecycle_evidence(evidence_paths[spec.key]),
        )
        for spec in expected_specs
    )
    return tuple(sorted(authorized, key=lambda item: item.resolved.manifest.key))


@contextmanager
def reuse_authorized_assets(
    assets: Sequence[AuthorizedModelAsset],
) -> Generator[None, None, None]:
    """仅在一次组合调用中公开已完整哈希且已授权的解析结果。"""

    normalized = tuple(assets)
    if not normalized or any(type(item) is not AuthorizedModelAsset for item in normalized):
        raise ModelAssetConfigurationError(
            "verified asset reuse requires lifecycle-authorized assets"
        )
    token: Token[tuple[AuthorizedModelAsset, ...]] = _ACTIVE_AUTHORIZED_ASSETS.set(normalized)
    try:
        yield
    finally:
        _ACTIVE_AUTHORIZED_ASSETS.reset(token)


def reusable_authorized_asset(
    store_root: Path,
    spec: ModelAssetSpec,
) -> ResolvedModelAsset | None:
    """返回当前组合上下文中同根、同规范的已授权解析结果。"""

    expected_root = (store_root / spec.key / spec.revision).resolve(strict=False)
    matches = tuple(
        item.resolved
        for item in _ACTIVE_AUTHORIZED_ASSETS.get()
        if item.resolved.root == expected_root
        and item.resolved.manifest.key == spec.key
        and item.resolved.manifest.revision == spec.revision
        and item.resolved.identity == spec.identity
    )
    if len(matches) > 1:
        raise ModelAssetConfigurationError(f"duplicate reusable authorized asset: {spec.key}")
    return matches[0] if matches else None


__all__ = [
    "GR00T_N1D6_AUTHORIZATION_POLICY_REGISTRY",
    "GR00T_N1D6_BASE_AUTHORIZATION_POLICY",
    "GR00T_N1D6_EAGLE_AUTHORIZATION_POLICY",
    "load_asset_lifecycle_evidence",
    "resolve_n1d6_authorized_assets",
    "reusable_authorized_asset",
    "reuse_authorized_assets",
]
