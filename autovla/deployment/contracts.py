"""仅部署相邻、不拥有 transport 的本地契约。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.training.checkpointing.identity import stable_fingerprint


@dataclass(frozen=True, slots=True)
class DeploymentSpec:
    """声明 bundle 到本地 runtime 的兼容检查需求。"""

    target_runtime: str
    required_device: str = "cuda"
    required_precision: str = "bfloat16"
    hook_keys: tuple[str, ...] = ()
    local_only: bool = True

    def __post_init__(self) -> None:
        """拒绝服务器、机器人和远程运行时声明。"""
        if not self.target_runtime.strip():
            raise ValueError("target runtime must not be empty")
        forbidden = ("server", "robot", "endpoint", "remote", "ros")
        if any(token in self.target_runtime.lower() for token in forbidden):
            raise ValueError("M9 deployment target must remain local and transport-neutral")
        if self.required_device != "cuda" or self.required_precision not in {
            "bfloat16",
            "float32",
        }:
            raise ValueError("deployment spec requires supported local CUDA runtime")
        if type(self.local_only) is not bool or not self.local_only:
            raise ValueError("deployment spec must remain local-only")

    @property
    def fingerprint(self) -> str:
        """返回部署相邻规格身份。"""
        return stable_fingerprint(
            {
                "target_runtime": self.target_runtime,
                "required_device": self.required_device,
                "required_precision": self.required_precision,
                "hook_keys": self.hook_keys,
                "local_only": self.local_only,
            }
        )


@dataclass(frozen=True, slots=True)
class ExportManifest:
    """记录导出引用, 不复制 checkpoint 或资产。"""

    policy_bundle_fingerprint: str
    deployment_spec_fingerprint: str
    format_key: str
    artifact_reference: str

    def __post_init__(self) -> None:
        """校验引用身份并禁止 URL。"""
        for value in (
            self.policy_bundle_fingerprint,
            self.deployment_spec_fingerprint,
            self.format_key,
            self.artifact_reference,
        ):
            if not value.strip():
                raise ValueError("export manifest values must not be empty")
        if "://" in self.artifact_reference:
            raise ValueError("export artifact reference must be local")


@dataclass(frozen=True, slots=True)
class RuntimeCompatibilityReport:
    """保存纯检查结果, 不启动模型、服务或 endpoint。"""

    compatible: bool
    checked_bundle_fingerprint: str
    checked_spec_fingerprint: str
    issues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """校验布尔和报告一致性。"""
        if type(self.compatible) is not bool:
            raise TypeError("compatible must be bool")
        if not self.checked_bundle_fingerprint.strip() or not self.checked_spec_fingerprint.strip():
            raise ValueError("compatibility identities must not be empty")
        if self.compatible and self.issues:
            raise ValueError("compatible report cannot contain issues")
        if not self.compatible and not self.issues:
            raise ValueError("incompatible report must explain issues")


__all__ = ["DeploymentSpec", "ExportManifest", "RuntimeCompatibilityReport"]
