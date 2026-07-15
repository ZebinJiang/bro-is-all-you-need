"""GR00T N1.6.1 embodiment 条件投影。"""

from __future__ import annotations

import torch
from torch import nn

from autovla.models._torch_typing import initialize_torch_module
from autovla.models.families.gr00t_n1d6._nvidia.embodiment import (
    CategorySpecificMLP,
    MultiEmbodimentActionEncoder,
)
from autovla.models.families.gr00t_n1d6.config import Gr00tN1d6Config


class EmbodimentConditioner(nn.Module):
    """集中拥有状态编码、动作时间编码和动作解码参数库。"""

    def __init__(self, config: Gr00tN1d6Config) -> None:
        """按照 32 个 projector 槽构造 checkpoint 可映射模块。"""
        initialize_torch_module(super())
        self.num_embodiments = config.max_num_embodiments
        self.state_encoder = CategorySpecificMLP(
            self.num_embodiments,
            config.max_state_dim,
            config.action_hidden_size,
            config.input_embedding_dim,
        )
        self.action_encoder = MultiEmbodimentActionEncoder(
            config.max_action_dim,
            config.input_embedding_dim,
            self.num_embodiments,
        )
        self.action_decoder = CategorySpecificMLP(
            self.num_embodiments,
            config.action_hidden_size,
            config.action_hidden_size,
            config.max_action_dim,
        )

    def validate_ids(self, embodiment_ids: torch.Tensor) -> None:
        """要求 ID 为 ``torch.long`` 且严格落在 ``[0,32)``。"""
        if embodiment_ids.ndim != 1 or embodiment_ids.dtype != torch.long:
            raise TypeError("embodiment_ids must be a torch.long [B] tensor")
        if bool(torch.any(embodiment_ids < 0)) or bool(
            torch.any(embodiment_ids >= self.num_embodiments)
        ):
            raise ValueError("embodiment ID exceeds configured projector bank")

    def encode_state(
        self,
        state: torch.Tensor,
        embodiment_ids: torch.Tensor,
    ) -> torch.Tensor:
        """把 padded 状态 ``[B,T,128]`` 编码为 ``[B,T,1536]``。"""
        self.validate_ids(embodiment_ids)
        return self.state_encoder(state, embodiment_ids)

    def encode_actions(
        self,
        actions: torch.Tensor,
        timesteps: torch.Tensor,
        embodiment_ids: torch.Tensor,
    ) -> torch.Tensor:
        """把动作和离散时间编码为 ``[B,50,1536]``。"""
        self.validate_ids(embodiment_ids)
        return self.action_encoder(actions, timesteps, embodiment_ids)

    def decode(
        self,
        features: torch.Tensor,
        embodiment_ids: torch.Tensor,
    ) -> torch.Tensor:
        """把 DiT 特征解码为 padded 动作速度。"""
        self.validate_ids(embodiment_ids)
        return self.action_decoder(features, embodiment_ids)


__all__ = ["EmbodimentConditioner"]
