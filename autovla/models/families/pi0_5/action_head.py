# ruff: noqa: RUF002
"""Pi0.5 Gemma 动作 expert、adaRMSNorm、flow loss 与 Euler 采样。"""

from __future__ import annotations

import math
from typing import cast

import torch
from torch import nn
from torch.utils.checkpoint import checkpoint

from autovla.models.families.pi0_5._openpi_compat import AdaRMSBlock, PrefixKVCache
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
        self.action_in_projection = nn.Linear(config.action_dimension, config.expert_hidden_size)
        self.time_mlp = nn.Sequential(
            nn.Linear(config.expert_hidden_size, config.expert_hidden_size * 2),
            nn.SiLU(),
            nn.Linear(config.expert_hidden_size * 2, config.expert_hidden_size),
        )
        self.expert_layers = nn.ModuleList(
            AdaRMSBlock(
                config.expert_hidden_size,
                config.expert_intermediate_size,
                config.expert_num_heads,
                config.expert_num_key_value_heads,
                config.prefix_hidden_size,
                epsilon=config.rms_norm_epsilon,
                rope_theta=config.rope_theta,
            )
            for _ in range(config.expert_num_layers)
        )
        self.action_out_projection = nn.Linear(config.expert_hidden_size, config.action_dimension)
        self.gradient_checkpointing = config.gradient_checkpointing
        self._apply_tuning_plan()

    def _apply_tuning_plan(self) -> None:
        """应用 expert 与输入/输出投影的显式可训练计划。"""

        for parameter in self.expert_layers.parameters():
            parameter.requires_grad_(self.config.tune_action_expert)
        for module in (
            self.action_in_projection,
            self.time_mlp,
            self.action_out_projection,
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
        frequencies = torch.exp(
            torch.arange(half, device=time.device, dtype=torch.float32)
            * (-math.log(10000.0) / max(half - 1, 1))
        )
        angles = time.float()[:, None] * frequencies[None] * 1000.0
        embedding = torch.cat((angles.sin(), angles.cos()), dim=-1)
        if embedding.shape[-1] < self.config.expert_hidden_size:
            embedding = torch.nn.functional.pad(embedding, (0, 1))
        return self.time_mlp(embedding.to(dtype=self.action_in_projection.weight.dtype))

    def build_prefix_cache(self, backbone_output: BackboneOutput) -> PrefixKVCache:
        """一次性为全部 expert 层生成前缀 K/V，推理步骤仅共享读取。"""

        prefix = backbone_output.features
        mask = backbone_output.attention_mask
        positions = torch.clamp(mask.long().cumsum(dim=1) - 1, min=0)
        positions = torch.where(mask, positions, torch.zeros_like(positions))
        keys: list[torch.Tensor] = []
        values: list[torch.Tensor] = []
        for layer in self.expert_layers:
            key, value = layer.prefix_kv(prefix, positions)
            keys.append(key)
            values.append(value)
        return PrefixKVCache(tuple(keys), tuple(values), mask, positions)

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
        hidden = self.action_in_projection(noisy_actions)
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
        for index, layer in enumerate(self.expert_layers):
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

        return self.action_in_projection(noisy_actions), self._time_embedding(time)

    def project_velocity(self, hidden: torch.Tensor) -> torch.Tensor:
        """把 expert 隐状态投影回 ``[B,H,32]``。"""

        output = self.action_out_projection(hidden)
        if output.shape[-2:] != (
            self.config.action_horizon,
            self.config.action_dimension,
        ):
            raise ValueError("action expert output must match configured [H,32]")
        return output


__all__ = ["Pi05ActionExpert"]
