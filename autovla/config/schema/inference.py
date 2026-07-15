"""本地推理配置。"""

from dataclasses import dataclass

from autovla.config.schema.base import require_bool, require_choice, require_non_empty_str


@dataclass(frozen=True, slots=True)
class InferenceConfig:
    """声明本地 policy bundle 检查或推理会话, 不拥有端点。"""

    enabled: bool = False
    device: str = "cuda"
    precision: str = "bfloat16"
    policy_bundle_manifest: str | None = None
    local_only: bool = True

    def __post_init__(self) -> None:
        """拒绝 CPU、网络和隐式 bundle。"""
        require_bool(self.enabled, "inference.enabled")
        require_choice(self.device, "inference.device", ("cuda",))
        require_choice(self.precision, "inference.precision", ("bfloat16", "float32"))
        require_bool(self.local_only, "inference.local_only")
        if not self.local_only:
            raise ValueError("inference must remain local-only")
        if self.policy_bundle_manifest is not None:
            require_non_empty_str(
                self.policy_bundle_manifest,
                "inference.policy_bundle_manifest",
            )
        if self.enabled and self.policy_bundle_manifest is None:
            raise ValueError("enabled inference requires a local policy bundle manifest")


__all__ = ["InferenceConfig"]
