"""OpenPI 来源的 Pi 架构静态配置,不依赖 JAX/Flax/OpenPI。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Pi0Config:
    """描述 Pi0 的默认张量和 token 契约。"""

    action_dimension: int = 32
    action_horizon: int = 50
    max_language_tokens: int = 48
    image_size: int = 224
    state_conditioning: str = "continuous_state_suffix_token"
    normalization: str = "mean_std"
    local_files_only: bool = True

    def __post_init__(self) -> None:
        """拒绝偏离固定默认架构或远程资产。"""

        if (self.action_dimension, self.action_horizon, self.image_size) != (32, 50, 224):
            raise ValueError("Pi0 defaults must remain 32/50/224")
        if not self.local_files_only:
            raise ValueError("Pi0 assets must remain local_files_only")


@dataclass(frozen=True, slots=True)
class Pi0FastConfig(Pi0Config):
    """描述 FAST 自回归动作 token 架构。"""

    state_conditioning: str = "continuous_state_in_fast_token_prefix"
    normalization: str = "quantile"


@dataclass(frozen=True, slots=True)
class Pi0_5Config(Pi0Config):
    """描述 Pi0.5 的离散状态和 AdaRMSNorm 架构。"""

    max_language_tokens: int = 200
    state_conditioning: str = "discrete_state_in_language_tokens"
    normalization: str = "quantile"


__all__ = ["Pi0Config", "Pi0FastConfig", "Pi0_5Config"]
