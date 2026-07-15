"""GR00T N1.7 flow-matching 动作头的架构描述。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.models.assembly import ModelAssemblyRequest
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config


@dataclass(frozen=True, slots=True)
class Gr00tN1d7ActionHead:
    """描述 embodiment-conditioned AlternateVLDiT 与四步 Euler 解码。

    状态输入为 ``[B,132]``。训练动作和 mask 为 ``[B,40,132]``。
    本类不采样噪声、不分配参数。不声称 checkpoint shape 已验证。
    """

    config: Gr00tN1d7Config
    distribution: str = "flow_matching"
    time_distribution: str = "beta"
    integration_method: str = "euler"
    masked_loss: str = "elementwise_mse_normalized_by_valid_actions"

    def __post_init__(self) -> None:
        """验证 artifact 实现的动作维度、层数和积分步数。"""

        if not isinstance(self.config, Gr00tN1d7Config):
            raise TypeError("action head requires Gr00tN1d7Config")
        if (
            self.config.max_state_dim,
            self.config.max_action_dim,
            self.config.action_horizon,
            self.config.diffusion_layers,
            self.config.vl_self_attention_layers,
            self.config.num_inference_steps,
        ) != (132, 132, 40, 32, 4, 4):
            raise ValueError("action head must use the realized 132/132/40/32/4/4 contract")

    @classmethod
    def from_request(cls, request: ModelAssemblyRequest) -> Gr00tN1d7ActionHead:
        """实现共享组件工厂输入面且不构造 Torch 模块。"""

        if request.family_key != "gr00t_n1d7" or not isinstance(request.config, Gr00tN1d7Config):
            raise TypeError("request must carry a GR00T N1.7 config")
        return cls(request.config)

    @property
    def tune_freeze_defaults(self) -> dict[str, bool]:
        """返回动作头和 embodiment projector 的显式调优默认值。"""

        return {
            "action_head_trainable": self.config.tune_action_head,
            "embodiment_projectors_trainable": self.config.tune_projectors,
        }


def _build_action_head(request: ModelAssemblyRequest) -> Gr00tN1d7ActionHead:
    """返回绑定共享请求的动作头描述。"""

    return Gr00tN1d7ActionHead.from_request(request)


__all__ = ["Gr00tN1d7ActionHead"]
