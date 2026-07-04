"""Action-head schema substrate, 仅表达 metadata 契约。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionHeadKind(str, Enum):
    """AutoVLA action head 家族枚举。"""

    FLOW_MATCHING_CONTINUOUS = "flow_matching_continuous_action"
    DIFFUSION_CONTINUOUS = "diffusion_continuous_action"
    AUTOREGRESSIVE_DISCRETE_TOKEN = "autoregressive_discrete_action_token"


@dataclass(frozen=True, slots=True)
class ActionOutputSpec:
    """Action output 基础契约。"""

    action_kind: ActionHeadKind
    runtime_status: str = "runtime_not_loaded"

    def to_table_row(self) -> dict[str, object]:
        """返回 action schema 表格行。"""
        return {
            "action_kind": self.action_kind.value,
            "runtime_status": self.runtime_status,
        }


@dataclass(frozen=True, slots=True)
class ContinuousActionChunkSpec(ActionOutputSpec):
    """连续 action chunk 输出契约。"""

    action_horizon: int = 1
    action_dim: int = 1

    def __init__(
        self,
        *,
        action_horizon: int,
        action_dim: int,
        action_kind: ActionHeadKind = ActionHeadKind.FLOW_MATCHING_CONTINUOUS,
        runtime_status: str = "runtime_not_loaded",
    ) -> None:
        """初始化连续 action chunk spec。"""
        if type(action_horizon) is not int or action_horizon <= 0:
            raise ValueError("action_horizon must be positive")
        if type(action_dim) is not int or action_dim <= 0:
            raise ValueError("action_dim must be positive")
        object.__setattr__(self, "action_kind", action_kind)
        object.__setattr__(self, "runtime_status", runtime_status)
        object.__setattr__(self, "action_horizon", action_horizon)
        object.__setattr__(self, "action_dim", action_dim)

    def to_table_row(self) -> dict[str, object]:
        """返回连续 action chunk 表格行。"""
        row = ActionOutputSpec.to_table_row(self)
        row.update({"action_dim": self.action_dim, "action_horizon": self.action_horizon})
        return row


@dataclass(frozen=True, slots=True)
class DiscreteActionTokenSpec(ActionOutputSpec):
    """离散 action token 输出契约。"""

    vocab_size: int = 1
    token_horizon: int = 1

    def __init__(
        self,
        *,
        vocab_size: int,
        token_horizon: int,
        runtime_status: str = "runtime_not_loaded",
    ) -> None:
        """初始化离散 action token spec。"""
        if type(vocab_size) is not int or vocab_size <= 0:
            raise ValueError("vocab_size must be positive")
        if type(token_horizon) is not int or token_horizon <= 0:
            raise ValueError("token_horizon must be positive")
        object.__setattr__(self, "action_kind", ActionHeadKind.AUTOREGRESSIVE_DISCRETE_TOKEN)
        object.__setattr__(self, "runtime_status", runtime_status)
        object.__setattr__(self, "vocab_size", vocab_size)
        object.__setattr__(self, "token_horizon", token_horizon)

    def to_table_row(self) -> dict[str, object]:
        """返回离散 action token 表格行。"""
        row = ActionOutputSpec.to_table_row(self)
        row.update({"token_horizon": self.token_horizon, "vocab_size": self.vocab_size})
        return row


@dataclass(frozen=True, slots=True)
class NormalizationPolicySpec:
    """Normalization policy metadata。"""

    policy: str
    statistics_required: bool = False

    def __post_init__(self) -> None:
        """校验 policy 非空。"""
        if not self.policy.strip():
            raise ValueError("policy must not be empty")


@dataclass(frozen=True, slots=True)
class FlowMatchingActionHeadSpec:
    """Flow-matching action head metadata。"""

    name: str
    output: ContinuousActionChunkSpec
    normalization: NormalizationPolicySpec

    def to_table_row(self) -> dict[str, object]:
        """返回 flow action head 表格行。"""
        row = self.output.to_table_row()
        row.update({"name": self.name, "normalization_policy": self.normalization.policy})
        return row


@dataclass(frozen=True, slots=True)
class DiffusionActionHeadSpec(FlowMatchingActionHeadSpec):
    """Diffusion action head metadata。"""


@dataclass(frozen=True, slots=True)
class AutoregressiveActionTokenHeadSpec:
    """Autoregressive token action head metadata。"""

    name: str
    output: DiscreteActionTokenSpec
    normalization: NormalizationPolicySpec

    def to_table_row(self) -> dict[str, object]:
        """返回 autoregressive token action head 表格行。"""
        row = self.output.to_table_row()
        row.update({"name": self.name, "normalization_policy": self.normalization.policy})
        return row
