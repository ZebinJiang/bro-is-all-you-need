"""不复制权重的本地 policy bundle 契约。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from autovla.training.checkpointing.identity import stable_fingerprint


@dataclass(frozen=True, slots=True)
class PolicyBundleManifest:
    """引用模型、资产、共享处理与动作解码身份。"""

    family_key: str
    family_config_fingerprint: str
    asset_manifest_fingerprint: str
    checkpoint_manifest_fingerprint: str
    processor_fingerprint: str
    transform_fingerprint: str
    capability_fingerprint: str
    action_decode_fingerprint: str
    device: str
    precision: str
    provenance: Mapping[str, str]
    deployment_hooks: tuple[str, ...] = ()
    schema_version: str = "autovla.policy_bundle_manifest.v1"

    def __post_init__(self) -> None:
        """校验本地 GPU bundle 身份。"""
        if self.schema_version != "autovla.policy_bundle_manifest.v1":
            raise ValueError("unsupported policy bundle manifest schema")
        identities = (
            self.family_key,
            self.family_config_fingerprint,
            self.asset_manifest_fingerprint,
            self.checkpoint_manifest_fingerprint,
            self.processor_fingerprint,
            self.transform_fingerprint,
            self.capability_fingerprint,
            self.action_decode_fingerprint,
        )
        if any(not value.strip() for value in identities):
            raise ValueError("policy bundle identities must not be empty")
        if self.device != "cuda" or self.precision not in {"bfloat16", "float32"}:
            raise ValueError("policy bundle requires local CUDA and supported precision")
        if any(not key.strip() or not value.strip() for key, value in self.provenance.items()):
            raise ValueError("policy bundle provenance must not be empty")
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))

    @property
    def fingerprint(self) -> str:
        """返回不含权重字节的稳定 bundle 身份。"""
        return stable_fingerprint(
            {
                "schema_version": self.schema_version,
                "family_key": self.family_key,
                "family_config_fingerprint": self.family_config_fingerprint,
                "asset_manifest_fingerprint": self.asset_manifest_fingerprint,
                "checkpoint_manifest_fingerprint": self.checkpoint_manifest_fingerprint,
                "processor_fingerprint": self.processor_fingerprint,
                "transform_fingerprint": self.transform_fingerprint,
                "capability_fingerprint": self.capability_fingerprint,
                "action_decode_fingerprint": self.action_decode_fingerprint,
                "device": self.device,
                "precision": self.precision,
                "provenance": self.provenance,
                "deployment_hooks": self.deployment_hooks,
            }
        )


@dataclass(frozen=True, slots=True)
class PolicyBundle:
    """把 manifest 与受治理本地引用绑定, 不复制任何资产。"""

    manifest: PolicyBundleManifest
    checkpoint_manifest_path: Path
    asset_root: Path

    def __post_init__(self) -> None:
        """要求引用绝对本地路径且彼此独立。"""
        checkpoint = self.checkpoint_manifest_path.expanduser()
        asset = self.asset_root.expanduser()
        if not checkpoint.is_absolute() or not asset.is_absolute():
            raise ValueError("policy bundle references must be absolute local paths")
        if checkpoint == asset or asset in checkpoint.parents:
            raise ValueError("checkpoint manifest must not be stored inside model assets")
        object.__setattr__(self, "checkpoint_manifest_path", checkpoint)
        object.__setattr__(self, "asset_root", asset)

    @property
    def fingerprint(self) -> str:
        """返回 manifest 身份; 物理路径不改变 bundle 内容身份。"""
        return self.manifest.fingerprint


__all__ = ["PolicyBundle", "PolicyBundleManifest"]
