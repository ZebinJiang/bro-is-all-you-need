# SPDX-License-Identifier: Apache-2.0
# Source: https://github.com/Physical-Intelligence/openpi/tree/15a9616a00943ada6c20a0f158e3adb39df2ccac
# License: Apache-2.0 source; model, tokenizer and checkpoint terms are separate.
# Reuse: Materially adapted flow-matching and Gemma expert execution semantics.
# AutoVLA changes: ActionHead contract, strict masks and fixed deterministic test hooks.
# ruff: noqa: RUF002
"""Pi0.5 Gemma 动作 expert、adaRMSNorm、flow loss 与 Euler 采样。"""

from __future__ import annotations

from typing import cast

import torch
from torch import nn
from torch.utils.checkpoint import checkpoint

from autovla.models.families.pi0_5._openpi_compat import (
    GemmaExpert,
    GemmaExpertModel,
    PrefixKVCache,
)
from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.interfaces.action_head import ActionHead
from autovla.models.outputs import (
    ActionHeadOutput,
    ActionPrediction,
    BackboneOutput,
    ModelInputBatch,
)


class Pi05ActionExpert(ActionHead):
    """以 Gemma expert 预测 ``[B,H,32]`` flow velocity。

    前缀特征只在每次模型调用开始时投影为逐层 K/V；十步 Euler 共享同一个
    ``PrefixKVCache``，suffix K/V 只存在于当前层调用中，不写回缓存。
    """

    def __init__(self, config: Pi05Config) -> None:
        """注册动作投影、时间 MLP、逐层 adaRMSNorm expert 和输出投影。"""

        super().__init__()
        self.config = config
        self.action_in_proj = nn.Linear(config.action_dimension, config.expert_hidden_size)
        self.time_mlp_in = nn.Linear(config.expert_hidden_size, config.expert_hidden_size)
        self.time_mlp_out = nn.Linear(config.expert_hidden_size, config.expert_hidden_size)
        self.gemma_expert = GemmaExpert(
            GemmaExpertModel(
                width=config.expert_hidden_size,
                intermediate_size=config.expert_intermediate_size,
                num_layers=config.expert_num_layers,
                num_heads=config.expert_num_heads,
                num_kv_heads=config.expert_num_key_value_heads,
                head_dim=config.expert_head_dim,
                epsilon=config.rms_norm_epsilon,
                rope_theta=config.rope_theta,
            )
        )
        self.action_out_proj = nn.Linear(config.expert_hidden_size, config.action_dimension)
        self.gradient_checkpointing = config.gradient_checkpointing
        self._apply_tuning_plan()

    def _apply_tuning_plan(self) -> None:
        """应用 expert 与输入/输出投影的显式可训练计划。"""

        for parameter in self.gemma_expert.parameters():
            parameter.requires_grad_(self.config.tune_action_expert)
        for module in (
            self.action_in_proj,
            self.time_mlp_in,
            self.time_mlp_out,
            self.action_out_proj,
        ):
            for parameter in module.parameters():
                parameter.requires_grad_(self.config.tune_input_output_projections)

    def gradient_checkpointing_enable(self) -> None:
        """启用 expert 层非重入 gradient checkpointing。"""

        self.gradient_checkpointing = True

    def gradient_checkpointing_disable(self) -> None:
        """关闭 expert 层 gradient checkpointing。"""

        self.gradient_checkpointing = False

    @staticmethod
    def adaptive_rms(
        hidden: torch.Tensor,
        scale: torch.Tensor,
        shift: torch.Tensor,
        gate: torch.Tensor,
        *,
        epsilon: float = 1e-6,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """保留公开测试入口：float32 RMS 后应用 scale/shift 并返回残差门。"""

        hidden_shape = tuple(hidden.shape)
        for name, value in (("scale", scale), ("shift", shift), ("gate", gate)):
            if tuple(torch.broadcast_shapes(hidden_shape, tuple(value.shape))) != hidden_shape:
                raise ValueError(f"AdaRMS {name} must broadcast exactly to hidden shape")
        rms = hidden.float().square().mean(dim=-1, keepdim=True).add(epsilon).rsqrt()
        normalized = (hidden.float() * rms).to(dtype=hidden.dtype)
        return normalized * (1 + scale) + shift, gate

    def _time_embedding(self, time: torch.Tensor) -> torch.Tensor:
        """把 ``[B]`` 连续时间编码到 expert 宽度。"""

        if time.ndim != 1:
            raise ValueError("Pi0.5 time must use [B]")
        half = self.config.expert_hidden_size // 2
        fraction = torch.linspace(
            0.0,
            1.0,
            half,
            device=time.device,
            dtype=torch.float64,
        )
        periods = 4e-3 * (4.0 / 4e-3) ** fraction
        angles = 2.0 * torch.pi * time.double()[:, None] / periods[None]
        embedding = torch.cat((angles.sin(), angles.cos()), dim=-1)
        embedding = embedding.to(dtype=self.action_in_proj.weight.dtype)
        embedding = torch.nn.functional.silu(self.time_mlp_in(embedding))
        return torch.nn.functional.silu(self.time_mlp_out(embedding))

    def build_prefix_cache(self, backbone_output: BackboneOutput) -> PrefixKVCache:
        """一次性为全部 expert 层生成前缀 K/V，推理步骤仅共享读取。"""

        mask = backbone_output.attention_mask
        positions = torch.clamp(mask.long().cumsum(dim=1) - 1, min=0)
        positions = torch.where(mask, positions, torch.zeros_like(positions))
        tensors = backbone_output.hidden_states
        expected = self.config.expert_num_layers * 2
        if len(tensors) != expected:
            raise ValueError("backbone must provide one PaliGemma K/V pair per expert layer")
        keys = tuple(tensors[0::2])
        values = tuple(tensors[1::2])
        return PrefixKVCache(keys, values, mask, positions)

    def _velocity(
        self,
        noisy_actions: torch.Tensor,
        time: torch.Tensor,
        prefix_cache: PrefixKVCache,
        suffix_mask: torch.Tensor,
    ) -> torch.Tensor:
        """执行一个共享前缀条件下的 suffix expert 前向。"""

        if noisy_actions.shape[-2:] != (
            self.config.action_horizon,
            self.config.action_dimension,
        ):
            raise ValueError("noisy actions must match configured [H,32]")
        if suffix_mask.dtype != torch.bool or suffix_mask.shape != noisy_actions.shape[:2]:
            raise TypeError("suffix mask must use strict bool[B,H]")
        hidden = self.action_in_proj(noisy_actions)
        condition = self._time_embedding(time).to(dtype=hidden.dtype)
        prefix_lengths = prefix_cache.mask.long().sum(dim=1, keepdim=True)
        suffix_positions = (
            prefix_lengths
            + torch.arange(noisy_actions.shape[1], device=noisy_actions.device, dtype=torch.long)[
                None
            ]
        )
        suffix_positions = torch.where(
            suffix_mask, suffix_positions, torch.zeros_like(suffix_positions)
        )
        key_mask = torch.cat((prefix_cache.mask, suffix_mask), dim=1)
        attention_mask = suffix_mask[:, :, None] & key_mask[:, None, :]
        for index, layer in enumerate(self.gemma_expert.model.layers):
            prefix_key = prefix_cache.keys[index]
            prefix_value = prefix_cache.values[index]
            if self.gradient_checkpointing and self.training:
                hidden = checkpoint(
                    layer,
                    hidden,
                    condition,
                    suffix_positions,
                    attention_mask,
                    (prefix_key, prefix_value),
                    use_reentrant=False,
                )
            else:
                hidden = layer(
                    hidden,
                    condition,
                    suffix_positions,
                    attention_mask,
                    (prefix_key, prefix_value),
                )
        hidden, _ = self.gemma_expert.model.norm(hidden, condition)
        return self.project_velocity(hidden)

    def sample_time(
        self,
        batch_size: int,
        *,
        device: torch.device,
        dtype: torch.dtype,
        generator: torch.Generator | None = None,
    ) -> torch.Tensor:
        """采样 ``Beta(1.5,1.0)*0.999+0.001``，并支持固定 generator。"""

        if self.config.beta_beta != 1.0:
            raise ValueError("generator-stable Pi0.5 sampler requires beta_beta=1.0")
        uniform = torch.rand(batch_size, device=device, dtype=torch.float32, generator=generator)
        beta = uniform.pow(1.0 / self.config.beta_alpha)
        time = beta * (1.0 - self.config.minimum_time) + self.config.minimum_time
        return time.to(dtype=dtype)

    @staticmethod
    def flow_training_sample(
        actions: torch.Tensor,
        noise: torch.Tensor,
        time: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """返回 ``x_t=t*noise+(1-t)*actions`` 和 ``noise-actions``。"""

        if actions.shape != noise.shape or actions.ndim != 3:
            raise ValueError("actions and noise must share [B,H,D]")
        if time.shape != (actions.shape[0],):
            raise ValueError("time must use [B]")
        expanded = time[:, None, None]
        return expanded * noise + (1.0 - expanded) * actions, noise - actions

    @staticmethod
    def _metadata_tensor(batch: ModelInputBatch, name: str) -> torch.Tensor | None:
        """读取可选固定测试 hook，拒绝非张量值。"""

        value = batch.metadata.get(name)
        if value is None:
            return None
        if not torch.is_tensor(value):
            raise TypeError(f"Pi0.5 metadata {name} must be a tensor")
        return cast(torch.Tensor, value)

    def compute_loss(
        self,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
    ) -> ActionHeadOutput:
        """计算严格 action mask 归约的 flow-matching 标量损失。"""

        if batch.actions is None or batch.action_mask is None:
            raise ValueError("Pi0.5 training requires actions and action_mask")
        actions = batch.actions
        fixed_noise = self._metadata_tensor(batch, "fixed_noise")
        noise = (
            torch.randn(
                actions.shape,
                device=actions.device,
                dtype=actions.dtype,
                generator=None,
            )
            if fixed_noise is None
            else fixed_noise.to(device=actions.device, dtype=actions.dtype)
        )
        fixed_time = self._metadata_tensor(batch, "fixed_time")
        time = (
            self.sample_time(actions.shape[0], device=actions.device, dtype=actions.dtype)
            if fixed_time is None
            else fixed_time.to(device=actions.device, dtype=actions.dtype)
        )
        if noise.shape != actions.shape or time.shape != (actions.shape[0],):
            raise ValueError("fixed noise/time hooks violate Pi0.5 tensor shapes")
        noisy_actions, target = self.flow_training_sample(actions, noise, time)
        suffix_mask = batch.action_mask.any(dim=-1)
        cache = self.build_prefix_cache(backbone_output)
        prediction = self._velocity(noisy_actions, time, cache, suffix_mask)
        squared = (prediction - target).square()
        elementwise = squared * batch.action_mask.to(dtype=squared.dtype)
        denominator = batch.action_mask.sum().clamp_min(1).to(dtype=squared.dtype)
        loss = elementwise.sum() / denominator
        if not torch.isfinite(loss):
            raise FloatingPointError("Pi0.5 flow-matching loss must be finite")
        return ActionHeadOutput(
            loss=loss,
            elementwise_loss=elementwise,
            action_mask=batch.action_mask,
            predicted_velocity=prediction,
            target_velocity=target,
            metrics={"mean_time": time.mean(), "valid_actions": denominator},
        )

    def predict_actions(
        self,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
        *,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """从固定或随机噪声执行恰好十步 ``t=1→0`` 显式 Euler。"""

        shape = (
            batch.batch_size,
            self.config.action_horizon,
            self.config.action_dimension,
        )
        fixed_noise = self._metadata_tensor(batch, "fixed_noise")
        value = (
            torch.randn(
                shape,
                device=backbone_output.features.device,
                dtype=backbone_output.features.dtype,
                generator=generator,
            )
            if fixed_noise is None
            else fixed_noise.to(
                device=backbone_output.features.device,
                dtype=backbone_output.features.dtype,
            )
        )
        if value.shape != shape:
            raise ValueError("fixed_noise must match [B,H,32]")
        suffix_mask = torch.ones(shape[:2], dtype=torch.bool, device=value.device)
        cache = self.build_prefix_cache(backbone_output)
        step_size = -1.0 / self.config.num_inference_steps
        for index in range(self.config.num_inference_steps):
            time = torch.full(
                (shape[0],),
                1.0 + index * step_size,
                device=value.device,
                dtype=value.dtype,
            )
            value = value + step_size * self._velocity(value, time, cache, suffix_mask)
        action_mask = torch.ones_like(value, dtype=torch.bool)
        return ActionPrediction(value, action_mask)

    def embed_actions(
        self, noisy_actions: torch.Tensor, time: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """公开动作/时间嵌入入口。"""

        return self.action_in_proj(noisy_actions), self._time_embedding(time)

    def project_velocity(self, hidden: torch.Tensor) -> torch.Tensor:
        """把 expert 隐状态投影回 ``[B,H,32]``。"""

        output = self.action_out_proj(hidden)
        if output.shape[-2:] != (
            self.config.action_horizon,
            self.config.action_dimension,
        ):
            raise ValueError("action expert output must match configured [H,32]")
        return output


__all__ = ["Pi05ActionExpert"]
