"""GR00T N1.7 checkpoint 与 gated Cosmos 双收据资产包。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from autovla.assets import (
    AssetAccessState,
    AssetAuthorizationPolicy,
    AssetLicenseRecord,
    AssetProvenanceRecord,
    AssetTermsKind,
    AssetTermsRequirement,
    AssetTermsState,
    AuthorizedModelAsset,
    ModelAssetManifest,
    ModelAssetSpec,
    ResolvedModelAsset,
)
from autovla.assets.errors import ModelAssetAuthorizationError
from autovla.models.families.gr00t_n1d7.config import (
    COSMOS_BACKBONE_ID,
    GR00T_N1D7_CHECKPOINT_ID,
    GR00T_N1D7_CHECKPOINT_REVISION,
)

_IMMUTABLE_REVISION = re.compile(r"[0-9a-f]{40}")
_UNSAFE_MODEL_SUFFIXES = (".bin", ".pt", ".pth", ".pkl", ".pickle")
_CHECKPOINT_KEY = "gr00t_n1d7_checkpoint"
_COSMOS_KEY = "cosmos_reason2_2b_gated"
_BASE_CHECKPOINT_ROLE = "base_checkpoint"
_COSMOS_BACKBONE_ROLE = "cosmos_backbone"
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


def _license_identity(spec: ModelAssetSpec) -> str:
    """返回规范中唯一许可成员的精确摘要。"""

    matches = tuple(
        item.sha256
        for item in spec.files
        if item.path == spec.license_file_path and item.role == "license"
    )
    if len(matches) != 1:
        raise ValueError(f"N1.7 asset {spec.key!r} must contain one license member")
    return matches[0]


def _terms_source_url(spec: ModelAssetSpec) -> str:
    """返回固定 revision 下的许可证据公开地址。"""

    return f"{spec.source_url.rstrip('/')}/blob/{spec.revision}/" f"{spec.license_file_path}"


@dataclass(frozen=True, slots=True)
class Gr00tN1d7AssetAuthorizationPolicy:
    """定义 N1.7 双资产角色的失败关闭授权规则。"""

    schema_version: str = "autovla.gr00t_n1d7_asset_authorization_policy.v1"

    def __post_init__(self) -> None:
        """拒绝调用方替换家族拥有的策略版本。"""

        if self.schema_version != "autovla.gr00t_n1d7_asset_authorization_policy.v1":
            raise ValueError("unsupported N1.7 authorization policy schema")

    @property
    def fingerprint(self) -> str:
        """返回不依赖本地路径和外部接受动作的家族策略身份。"""

        payload = {
            "schema_version": self.schema_version,
            "roles": {
                _BASE_CHECKPOINT_ROLE: {
                    "asset_key": _CHECKPOINT_KEY,
                    "public_identifier": GR00T_N1D7_CHECKPOINT_ID,
                    "revision": GR00T_N1D7_CHECKPOINT_REVISION,
                    "access": AssetAccessState.PUBLIC.value,
                    "terms_kind": AssetTermsKind.MODEL_CHECKPOINT.value,
                    "scope": "gr00t_n1d7_checkpoint_runtime",
                },
                _COSMOS_BACKBONE_ROLE: {
                    "asset_key": _COSMOS_KEY,
                    "public_identifier": COSMOS_BACKBONE_ID,
                    "revision": "receipt_bound_immutable_revision",
                    "access": AssetAccessState.GRANTED.value,
                    "terms_kind": AssetTermsKind.MODEL_CHECKPOINT.value,
                    "scope": "gr00t_n1d7_cosmos_runtime",
                },
            },
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def policy_for(
        self,
        role: str,
        spec: ModelAssetSpec,
        /,
    ) -> AssetAuthorizationPolicy:
        """为精确资产规范生成共享生命周期授权策略。"""

        if type(spec) is not ModelAssetSpec:
            raise TypeError("N1.7 authorization policy requires ModelAssetSpec")
        if spec.family_key != "gr00t_n1d7":
            raise ValueError("N1.7 authorization policy requires family-owned assets")
        if role == _BASE_CHECKPOINT_ROLE:
            expected_key = _CHECKPOINT_KEY
            expected_identifier = GR00T_N1D7_CHECKPOINT_ID
            expected_revision = GR00T_N1D7_CHECKPOINT_REVISION
            access_state = AssetAccessState.PUBLIC
            scope = "gr00t_n1d7_checkpoint_runtime"
        elif role == _COSMOS_BACKBONE_ROLE:
            expected_key = _COSMOS_KEY
            expected_identifier = COSMOS_BACKBONE_ID
            expected_revision = spec.revision
            access_state = AssetAccessState.GRANTED
            scope = "gr00t_n1d7_cosmos_runtime"
        else:
            raise ValueError(f"unknown N1.7 authorization role: {role!r}")
        if (
            spec.key != expected_key
            or spec.public_identifier != expected_identifier
            or spec.revision != expected_revision
            or not _IMMUTABLE_REVISION.fullmatch(spec.revision)
        ):
            raise ValueError(f"N1.7 authorization spec does not match role {role!r}")
        return AssetAuthorizationPolicy(
            asset_key=spec.key,
            spec_identity=spec.identity,
            revision=spec.revision,
            required_access_state=access_state,
            terms_requirements=(
                AssetTermsRequirement(
                    terms_kind=AssetTermsKind.MODEL_CHECKPOINT,
                    terms_identity=_license_identity(spec),
                    terms_source_url=_terms_source_url(spec),
                    scope=scope,
                    required_state=AssetTermsState.ACCEPTED_BY_USER,
                ),
            ),
        )


GR00T_N1D7_AUTHORIZATION_POLICY = Gr00tN1d7AssetAuthorizationPolicy()


@dataclass(frozen=True, slots=True)
class Gr00tN1d7AuthorizationReceipt:
    """绑定 checkpoint、Cosmos 与家族策略的类型化授权收据。"""

    checkpoint: AuthorizedModelAsset
    cosmos: AuthorizedModelAsset

    def __post_init__(self) -> None:
        """只接受共享生命周期层已签发并匹配家族策略的授权资产。"""

        self.validate()

    @property
    def policy_identity(self) -> str:
        """返回签发本收据所依据的家族策略身份。"""

        return GR00T_N1D7_AUTHORIZATION_POLICY.fingerprint

    @property
    def authorization_identities(self) -> tuple[str, ...]:
        """按角色顺序返回两个完整生命周期授权身份。"""

        return (self.checkpoint.fingerprint, self.cosmos.fingerprint)

    @property
    def fingerprint(self) -> str:
        """返回绑定策略、角色和两个授权资产的稳定身份。"""

        self.validate()
        payload = {
            "schema_version": "autovla.gr00t_n1d7_authorization_receipt.v1",
            "policy_identity": self.policy_identity,
            "authorized_assets": {
                _BASE_CHECKPOINT_ROLE: self.checkpoint.fingerprint,
                _COSMOS_BACKBONE_ROLE: self.cosmos.fingerprint,
            },
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate(self) -> None:
        """重新校验类型、角色和每个共享策略决定身份。"""

        for role, raw_asset in (
            (_BASE_CHECKPOINT_ROLE, cast(object, self.checkpoint)),
            (_COSMOS_BACKBONE_ROLE, cast(object, self.cosmos)),
        ):
            if type(raw_asset) is not AuthorizedModelAsset:
                raise TypeError("N1.7 requires lifecycle-authorized model asset receipts")
            asset = raw_asset
            expected_policy = GR00T_N1D7_AUTHORIZATION_POLICY.policy_for(
                role,
                asset.resolved.manifest.to_spec(),
            )
            if asset.authorization.policy_identity != expected_policy.fingerprint:
                raise ModelAssetAuthorizationError(
                    asset.resolved.manifest.key,
                    "N1D7_AUTHORIZATION_POLICY_IDENTITY_MISMATCH",
                )


@dataclass(frozen=True, slots=True, init=False)
class Gr00tN1d7AssetBundle:
    """只接受绑定家族策略的双资产生命周期授权收据。

    当前官方 checkpoint 的打包 LICENSE 与模型卡冲突。默认构造立即
    失败。调用方布尔断言不能解决冲突或代表用户接受 Cosmos 条款。
    """

    _authorization: Gr00tN1d7AuthorizationReceipt

    def __init__(
        self,
        authorization: Gr00tN1d7AuthorizationReceipt | None = None,
        **legacy_assertions: object,
    ) -> None:
        """要求类型化授权收据,旧布尔调用形状只保留失败关闭语义。"""

        if legacy_assertions:
            known = {"checkpoint_license_resolved", "cosmos_access_accepted"}
            unknown = set(legacy_assertions) - known
            if unknown:
                raise TypeError(
                    "direct N1.7 asset or authorization assertions are forbidden: "
                    f"{sorted(unknown)}"
                )
            if any(type(value) is not bool for value in legacy_assertions.values()):
                raise TypeError("legacy N1.7 authorization assertions must be bool")
            if (
                legacy_assertions.get("checkpoint_license_resolved") is True
                and legacy_assertions.get("cosmos_access_accepted", False) is False
            ):
                raise RuntimeError(
                    "gated Cosmos typed authorization receipt is required; "
                    "caller-controlled access acceptance is forbidden"
                )
            raise RuntimeError(
                "GR00T N1.7 checkpoint license conflict requires a typed lifecycle "
                "authorization receipt; caller-controlled assertions are forbidden"
            )
        if authorization is None:
            raise RuntimeError(
                "GR00T N1.7 checkpoint license conflict is unresolved; "
                "typed lifecycle authorization receipt is required"
            )
        if type(authorization) is not Gr00tN1d7AuthorizationReceipt:
            raise TypeError("N1.7 asset bundle requires Gr00tN1d7AuthorizationReceipt")
        authorization.validate()
        object.__setattr__(self, "_authorization", authorization)
        self.validate()

    @property
    def authorization_identity(self) -> str:
        """返回进入装配指纹的双资产授权收据身份。"""

        return self._authorization.fingerprint

    @property
    def authorization_policy_identity(self) -> str:
        """返回家族拥有的失败关闭策略身份。"""

        return self._authorization.policy_identity

    @property
    def authorization_evidence_ids(self) -> tuple[str, ...]:
        """返回通用运行证据使用的排序授权资产身份。"""

        return tuple(sorted(self._authorization.authorization_identities))

    @property
    def family_key(self) -> str:
        """返回共享资产协议家族键。"""

        return "gr00t_n1d7"

    @property
    def revision(self) -> str:
        """返回主 checkpoint revision。"""

        return self._authorization.checkpoint.resolved.manifest.revision

    @property
    def root(self) -> Path:
        """返回主 checkpoint 本地根。"""

        return self._authorization.checkpoint.resolved.root

    @property
    def cosmos_revision(self) -> str:
        """返回 gated Cosmos 授权收据的精确不可变 revision。"""

        return self._authorization.cosmos.resolved.manifest.revision

    @property
    def manifest(self) -> Mapping[str, ModelAssetManifest]:
        """按角色返回不可变清单。"""

        return MappingProxyType(
            {
                _BASE_CHECKPOINT_ROLE: self._authorization.checkpoint.resolved.manifest,
                _COSMOS_BACKBONE_ROLE: self._authorization.cosmos.resolved.manifest,
            }
        )

    @property
    def assets_by_role(self) -> Mapping[str, ResolvedModelAsset]:
        """按角色返回 verified store 收据。"""

        return MappingProxyType(
            {
                _BASE_CHECKPOINT_ROLE: self._authorization.checkpoint.resolved,
                _COSMOS_BACKBONE_ROLE: self._authorization.cosmos.resolved,
            }
        )

    @property
    def authorization_receipts_by_role(self) -> Mapping[str, AuthorizedModelAsset]:
        """按角色返回完整生命周期授权收据。"""

        return MappingProxyType(
            {
                _BASE_CHECKPOINT_ROLE: self._authorization.checkpoint,
                _COSMOS_BACKBONE_ROLE: self._authorization.cosmos,
            }
        )

    @property
    def checkpoint_candidates(self) -> tuple[Path, ...]:
        """返回主清单中声明的 safetensors shard。"""

        return tuple(
            self.root / item.path
            for item in self._authorization.checkpoint.resolved.manifest.files
            if item.path.endswith(".safetensors")
        )

    @property
    def tokenizer_or_processor_assets(self) -> tuple[Path, ...]:
        """返回主 processor 与 Cosmos tokenizer 根。"""

        return (self.root, self._authorization.cosmos.resolved.root)

    @property
    def backbone_assets(self) -> tuple[Path, ...]:
        """返回 gated Cosmos 本地根。"""

        return (self._authorization.cosmos.resolved.root,)

    @property
    def provenance(self) -> tuple[AssetProvenanceRecord, ...]:
        """返回两个固定来源身份。"""

        return tuple(
            AssetProvenanceRecord(
                asset.resolved.manifest.source_url,
                asset.resolved.manifest.revision,
                asset.fingerprint,
            )
            for asset in (
                self._authorization.checkpoint,
                self._authorization.cosmos,
            )
        )

    @property
    def license_records(self) -> tuple[AssetLicenseRecord, ...]:
        """保持 checkpoint 与 Cosmos 许可分离。"""

        return tuple(
            AssetLicenseRecord(
                asset.resolved.manifest.key,
                asset.resolved.manifest.license_name,
                asset.resolved.manifest.license_file_path,
                asset.resolved.manifest.redistribution,
            )
            for asset in (
                self._authorization.checkpoint,
                self._authorization.cosmos,
            )
        )

    @property
    def fingerprint(self) -> str:
        """返回绑定资产、授权策略和授权收据的稳定摘要。"""

        payload = {
            "family_key": self.family_key,
            "authorization_policy": self.authorization_policy_identity,
            "authorization_receipt": self.authorization_identity,
            "checkpoint": self._authorization.checkpoint.resolved.identity,
            "cosmos": self._authorization.cosmos.resolved.identity,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @property
    def manifest_fingerprint(self) -> str:
        """返回与通用运行资产证据一致的清单摘要。"""

        payload = {role: manifest.to_dict() for role, manifest in sorted(self.manifest.items())}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate(self) -> None:
        """重新校验授权、收据身份、根路径与 safetensors-only 边界。"""

        self._authorization.validate()
        checkpoint = self._authorization.checkpoint.resolved
        cosmos = self._authorization.cosmos.resolved
        for asset in (checkpoint, cosmos):
            if not asset.root.is_absolute() or len(asset.identity) != 64:
                raise ValueError("asset receipts must have absolute roots and stable identities")
            if not _IMMUTABLE_REVISION.fullmatch(asset.manifest.revision):
                raise ValueError("N1.7 model assets require immutable 40-character revisions")
            if any(item.path.endswith(_UNSAFE_MODEL_SUFFIXES) for item in asset.manifest.files):
                raise ValueError("arbitrary pickle model formats are forbidden")
        if not self.checkpoint_candidates:
            raise ValueError("checkpoint receipt must inventory safetensors shards")
        # Cosmos 仅提供本地 config/processor/tokenizer; GR00T checkpoint 严格加载全部骨干权重。
        cosmos_paths = frozenset(item.path for item in cosmos.manifest.files)
        missing_cosmos = tuple(sorted(_COSMOS_CONSUMED_FILES - cosmos_paths))
        if missing_cosmos:
            raise ValueError(f"Cosmos receipt lacks consumed local assets: {missing_cosmos}")


__all__ = [
    "GR00T_N1D7_AUTHORIZATION_POLICY",
    "Gr00tN1d7AssetAuthorizationPolicy",
    "Gr00tN1d7AssetBundle",
    "Gr00tN1d7AuthorizationReceipt",
]
