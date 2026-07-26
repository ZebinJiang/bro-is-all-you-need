# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Selectively adapted from NVIDIA/Isaac-GR00T.
# Source revision: 9c7e746b2cd37a810070a98ef41d290a07e806c2
# Source path: gr00t/model/gr00t_n1d7/gr00t_n1d7.py
# Source blob: 346b597a4b9a115a9a5b1053621f47f07833da09
# Local changes: AutoVLA typed outputs, shared flow schedule, deterministic hooks,
# Chinese documentation, and runtime-gated namespace-constrained configuration.

"""GR00T N1.7 官方 namespace 兼容的 flow-matching 动作头。"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import torch
from torch import nn

from autovla.models._torch_typing import initialize_torch_module
from autovla.models.assembly import ModelAssemblyRequest
from autovla.models.components.flow_matching import (
    FlowMatchingSchedule,
    euler_integrate,
    interpolate_flow,
    masked_mean_squared_error,
    sample_beta_time,
)
from autovla.models.families.gr00t_n1d7._nvidia.dit import (
    AlternateVLDiT,
    SelfAttentionTransformer,
)
from autovla.models.families.gr00t_n1d7._nvidia.embodiment import (
    CategorySpecificMLP,
    MultiEmbodimentActionEncoder,
)
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config
from autovla.models.interfaces.action_head import ActionHead
from autovla.models.outputs import (
    ActionHeadOutput,
    ActionPrediction,
    BackboneOutput,
    ModelInputBatch,
)

NoiseHook = Callable[[torch.Tensor], torch.Tensor]
TimeHook = Callable[[int, torch.device, torch.dtype, FlowMatchingSchedule], torch.Tensor]


class Gr00tN1d7ActionHead(ActionHead):
    """保留官方 AlternateVLDiT tensor flow 与 checkpoint namespace。"""

    distribution = "flow_matching"
    time_distribution = "beta"
    integration_method = "euler"
    masked_loss = "elementwise_mse_normalized_by_valid_actions"

    def __init__(
        self,
        config: Gr00tN1d7Config,
        *,
        noise_hook: NoiseHook | None = None,
        time_hook: TimeHook | None = None,
    ) -> None:
        """构造唯一参数图; 测试 hook 不进入 state dict。"""

        initialize_torch_module(super())
        if not isinstance(cast(object, config), Gr00tN1d7Config):
            raise TypeError("action head requires Gr00tN1d7Config")
        self.config = config
        self.model = AlternateVLDiT(
            num_attention_heads=config.action_attention_heads,
            attention_head_dim=config.action_attention_head_dim,
            output_dim=config.diffusion_output_dim,
            num_layers=config.diffusion_layers,
            dropout=config.attention_dropout,
            attention_bias=config.attention_bias,
            norm_type="ada_norm",
            norm_elementwise_affine=False,
            norm_eps=config.norm_epsilon,
            final_dropout=config.final_dropout,
            positional_embeddings=config.diffusion_positional_embeddings,
            max_positional_embeddings=config.diffusion_max_positional_embeddings,
            interleave_self_attention=True,
            cross_attention_dim=config.backbone_hidden_size,
            attend_text_every_n_blocks=config.attend_text_every_n_blocks,
        )
        self.state_encoder = CategorySpecificMLP(
            config.max_num_embodiments,
            config.max_state_dim * config.state_history_length,
            config.action_hidden_size,
            config.action_model_width,
        )
        self.action_encoder = MultiEmbodimentActionEncoder(
            config.max_action_dim,
            config.action_model_width,
            config.max_num_embodiments,
        )
        self.action_decoder = CategorySpecificMLP(
            config.max_num_embodiments,
            config.action_hidden_size,
            config.action_hidden_size,
            config.max_action_dim,
        )
        self.vlln = nn.LayerNorm(config.backbone_hidden_size)
        self.vl_self_attention = SelfAttentionTransformer(
            num_attention_heads=config.vl_attention_heads,
            attention_head_dim=config.vl_attention_head_dim,
            num_layers=config.vl_self_attention_layers,
            dropout=config.vl_attention_dropout,
            attention_bias=config.vl_attention_bias,
            norm_elementwise_affine=True,
            norm_eps=config.norm_epsilon,
            final_dropout=config.vl_final_dropout,
            positional_embeddings=config.vl_positional_embeddings,
            max_positional_embeddings=config.vl_max_positional_embeddings,
        )
        self.position_embedding = nn.Embedding(
            config.max_sequence_length,
            config.action_model_width,
        )
        nn.init.normal_(self.position_embedding.weight, mean=0.0, std=0.02)
        self.schedule = FlowMatchingSchedule(
            beta_alpha=config.flow_beta_alpha,
            beta_beta=config.flow_beta_beta,
            time_scale=config.flow_time_scale,
            timestep_buckets=config.timestep_buckets,
            inference_steps=config.num_inference_steps,
        )
        self._noise_hook = noise_hook
        self._time_hook = time_hook
        self._apply_tune_policy()

    @classmethod
    def from_request(cls, request: ModelAssemblyRequest) -> "Gr00tN1d7ActionHead":
        """从唯一共享请求构造动作头。"""

        if request.family_key != "gr00t_n1d7" or not isinstance(request.config, Gr00tN1d7Config):
            raise TypeError("request must carry a GR00T N1.7 config")
        return cls(request.config)

    @property
    def tune_freeze_defaults(self) -> dict[str, bool]:
        """返回官方 projector、DiT 和 VL normalization 的调优策略。"""

        return {
            "action_head_trainable": self.config.tune_action_head,
            "embodiment_projectors_trainable": self.config.tune_projectors,
            "diffusion_model_trainable": self.config.tune_diffusion_model,
            "vlln_trainable": self.config.tune_vlln,
        }

    def _apply_tune_policy(self) -> None:
        """先冻结全部, 再按 artifact 开关解冻官方 namespace。"""

        self.requires_grad_(False)
        if not self.config.tune_action_head:
            return
        if self.config.tune_projectors:
            self.state_encoder.requires_grad_(True)
            self.action_encoder.requires_grad_(True)
            self.action_decoder.requires_grad_(True)
            self.position_embedding.requires_grad_(True)
        if self.config.tune_diffusion_model:
            self.model.requires_grad_(True)
        if self.config.tune_vlln:
            self.vlln.requires_grad_(True)
            self.vl_self_attention.requires_grad_(True)

    def train(self, mode: bool = True) -> "Gr00tN1d7ActionHead":
        """切换模式并让冻结分支保持 eval。"""

        super().train(mode)
        if mode:
            if not self.config.tune_projectors:
                self.state_encoder.eval()
                self.action_encoder.eval()
                self.action_decoder.eval()
                self.position_embedding.eval()
            if not self.config.tune_diffusion_model:
                self.model.eval()
            if not self.config.tune_vlln:
                self.vlln.eval()
                self.vl_self_attention.eval()
        return self

    def _state_features(self, batch: ModelInputBatch, *, apply_dropout: bool) -> torch.Tensor:
        """把 ``[B,T,132]`` 展平为官方单 state token 并按样本归零。"""

        if batch.state.shape[1:] != (
            self.config.state_history_length,
            self.config.max_state_dim,
        ):
            raise ValueError("state history must match the official N1.7 state encoder input")
        state = batch.state.reshape(batch.batch_size, 1, -1)
        state_features = self.state_encoder(state, batch.embodiment_ids)
        if apply_dropout and self.training and self.config.state_dropout_probability > 0:
            dropped = torch.rand(state_features.shape[0], device=state_features.device)
            dropped = dropped.lt(self.config.state_dropout_probability).reshape(-1, 1, 1)
            state_features = torch.where(dropped, torch.zeros_like(state_features), state_features)
        return state_features

    def _vl_features(self, output: BackboneOutput) -> torch.Tensor:
        """按官方顺序执行 VLLN 和四层 SelfAttentionTransformer。"""

        if output.features.shape[-1] != self.config.backbone_hidden_size:
            raise ValueError("backbone features must preserve the 2048-wide Cosmos contract")
        return self.vl_self_attention(self.vlln(output.features))

    def _predict_velocity(
        self,
        actions: torch.Tensor,
        timesteps: torch.Tensor,
        *,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
        state_features: torch.Tensor,
        vl_features: torch.Tensor,
    ) -> torch.Tensor:
        """执行官方 action encoder -> AlternateVLDiT -> action decoder 流。"""

        action_features = self.action_encoder(actions, timesteps, batch.embodiment_ids)
        position_ids = torch.arange(action_features.shape[1], device=actions.device)
        action_features = action_features + self.position_embedding(position_ids).unsqueeze(0)
        state_action = torch.cat((state_features, action_features), dim=1)
        model_output = self.model(
            state_action,
            vl_features,
            timesteps,
            image_mask=backbone_output.image_mask,
            backbone_attention_mask=backbone_output.attention_mask,
        )
        decoded = self.action_decoder(model_output, batch.embodiment_ids)
        return decoded[:, -actions.shape[1] :]

    def compute_loss(
        self,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
    ) -> ActionHeadOutput:
        """按官方 flow target 和有效动作元素归一化 MSE。"""

        if batch.actions is None or batch.action_mask is None:
            raise ValueError("flow-matching training requires actions and action_mask")
        actions = batch.actions
        noise = self._noise_hook(actions) if self._noise_hook else torch.randn_like(actions)
        if noise.shape != actions.shape:
            raise ValueError("fixed noise hook must preserve [B,40,132]")
        if self._time_hook is None:
            continuous_time = sample_beta_time(
                actions.shape[0],
                device=actions.device,
                dtype=actions.dtype,
                schedule=self.schedule,
            )
        else:
            continuous_time = self._time_hook(
                actions.shape[0],
                actions.device,
                actions.dtype,
                self.schedule,
            )
        trajectory, target = interpolate_flow(noise, actions, continuous_time)
        timesteps = (continuous_time * self.schedule.timestep_buckets).long()
        predicted = self._predict_velocity(
            trajectory,
            timesteps,
            backbone_output=backbone_output,
            batch=batch,
            state_features=self._state_features(batch, apply_dropout=True),
            vl_features=self._vl_features(backbone_output),
        )
        loss, elementwise = masked_mean_squared_error(predicted, target, batch.action_mask)
        return ActionHeadOutput(
            loss,
            elementwise,
            batch.action_mask,
            predicted,
            target,
            {
                "valid_action_count": batch.action_mask.sum(),
                "mean_flow_time": continuous_time.mean(),
            },
        )

    def predict_actions(
        self,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
        *,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """从 Gaussian noise 执行官方四步 Euler 预测。"""

        with torch.no_grad():
            initial = torch.randn(
                (batch.batch_size, self.config.action_horizon, self.config.max_action_dim),
                device=backbone_output.features.device,
                dtype=backbone_output.features.dtype,
                generator=generator,
            )
            if self._noise_hook is not None:
                initial = self._noise_hook(initial)
            state = self._state_features(batch, apply_dropout=False)
            vl_features = self._vl_features(backbone_output)

            def velocity(actions: torch.Tensor, timesteps: torch.Tensor) -> torch.Tensor:
                """复用同一官方参数图返回当前速度。"""

                return self._predict_velocity(
                    actions,
                    timesteps,
                    backbone_output=backbone_output,
                    batch=batch,
                    state_features=state,
                    vl_features=vl_features,
                )

            actions = euler_integrate(initial, velocity, schedule=self.schedule)
            mask = (
                batch.action_mask
                if batch.action_mask is not None
                else torch.ones_like(actions, dtype=torch.bool)
            )
            return ActionPrediction(actions, mask)


def _build_action_head(request: ModelAssemblyRequest) -> Gr00tN1d7ActionHead:
    """沿唯一 N1.7 工厂与请求初始化上下文构造动作头。"""

    from autovla.models.families.gr00t_n1d7.factory import Gr00tN1d7ModelFactory

    return Gr00tN1d7ModelFactory().build_action_head(request)


__all__ = ["Gr00tN1d7ActionHead", "_build_action_head"]
