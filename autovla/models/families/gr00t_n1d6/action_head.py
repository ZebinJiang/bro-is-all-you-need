"""GR00T N1.6.1 masked flow-matching 动作头。"""

from __future__ import annotations

import torch
from torch import nn

from autovla.models._torch_typing import initialize_torch_module
from autovla.models.components.flow_matching import (
    FlowMatchingSchedule,
    euler_integrate,
    interpolate_flow,
    sample_beta_time,
)
from autovla.models.families.gr00t_n1d6._nvidia.dit import (
    AlternateVisionLanguageDiffusionTransformer,
)
from autovla.models.families.gr00t_n1d6.config import Gr00tN1d6Config
from autovla.models.families.gr00t_n1d6.embodiment import EmbodimentConditioner
from autovla.models.interfaces.action_head import ActionHead
from autovla.models.outputs import (
    ActionHeadOutput,
    ActionPrediction,
    BackboneOutput,
    ModelInputBatch,
)


class Gr00tN1d6ActionHead(ActionHead):
    """实现 N1.6.1 beta-time 训练与四步显式 Euler 动作生成。"""

    def __init__(self, config: Gr00tN1d6Config) -> None:
        """构造 embodiment 投影、交替 VL-DiT、位置嵌入和 VLLN。"""
        initialize_torch_module(super())
        self.config = config
        self.schedule = FlowMatchingSchedule(
            beta_alpha=config.noise_beta_alpha,
            beta_beta=config.noise_beta_beta,
            time_scale=config.noise_time_scale,
            timestep_buckets=config.num_timestep_buckets,
            inference_steps=config.num_inference_steps,
        )
        self.conditioner = EmbodimentConditioner(config)
        self.model = AlternateVisionLanguageDiffusionTransformer(
            num_layers=config.num_layers,
            num_attention_heads=config.num_attention_heads,
            attention_head_dim=config.attention_head_dim,
            output_dim=config.action_hidden_size,
            cross_attention_dim=config.backbone_embedding_dim,
            dropout=config.attention_dropout,
            attend_text_every_n_blocks=config.attend_text_every_n_blocks,
        )
        self.vlln = nn.LayerNorm(config.backbone_embedding_dim)
        self.position_embedding = nn.Embedding(
            config.max_sequence_length,
            config.input_embedding_dim,
        )
        nn.init.normal_(self.position_embedding.weight, mean=0.0, std=0.02)
        self.mask_token = (
            nn.Parameter(0.02 * torch.randn(1, 1, config.input_embedding_dim))
            if config.state_dropout_probability > 0
            else None
        )
        self._apply_tune_policy()

    def _apply_tune_policy(self) -> None:
        """按 aggregate 和 granular 开关确定最终可训练参数。"""
        self.requires_grad_(False)
        if self.config.tune_action_head:
            if self.config.tune_projector:
                self.conditioner.requires_grad_(True)
                self.position_embedding.requires_grad_(True)
                if self.mask_token is not None:
                    self.mask_token.requires_grad_(True)
            if self.config.tune_diffusion_model:
                self.model.requires_grad_(True)
            if self.config.tune_vlln:
                self.vlln.requires_grad_(True)
        if self.config.trainable_parameters_fp32:
            for parameter in self.parameters():
                if parameter.requires_grad:
                    parameter.data = parameter.data.float()

    def train(self, mode: bool = True) -> "Gr00tN1d6ActionHead":
        """切换模式并强制所有冻结模块保持 eval。"""
        super().train(mode)
        if mode:
            if not self.config.tune_projector:
                self.conditioner.eval()
                self.position_embedding.eval()
            if not self.config.tune_diffusion_model:
                self.model.eval()
            if not self.config.tune_vlln:
                self.vlln.eval()
        return self

    def _state_features(self, batch: ModelInputBatch) -> torch.Tensor:
        """编码状态并应用可配置 dropout/noise。"""
        features = self.conditioner.encode_state(batch.state, batch.embodiment_ids)
        if self.training and self.config.state_dropout_probability > 0:
            if self.mask_token is None:
                raise RuntimeError("state dropout requires mask_token")
            dropped = torch.rand(features.shape[0], device=features.device)
            dropped = (dropped < self.config.state_dropout_probability).reshape(-1, 1, 1)
            features = torch.where(dropped, self.mask_token.to(features.dtype), features)
        if self.training and self.config.state_noise_scale > 0:
            features = features + torch.randn_like(features) * self.config.state_noise_scale
        return features

    def _predict_velocity(
        self,
        actions: torch.Tensor,
        timesteps: torch.Tensor,
        *,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
        state_features: torch.Tensor,
    ) -> torch.Tensor:
        """执行动作时间编码、交替 VL-DiT 和 embodiment 解码。"""
        action_features = self.conditioner.encode_actions(
            actions,
            timesteps,
            batch.embodiment_ids,
        )
        positions = torch.arange(
            actions.shape[1],
            dtype=torch.long,
            device=actions.device,
        )
        action_features = action_features + self.position_embedding(positions).unsqueeze(0)
        state_action = torch.cat((state_features, action_features), dim=1)
        model_output = self.model(
            state_action,
            self.vlln(backbone_output.features),
            timestep=timesteps,
            image_mask=backbone_output.image_mask,
            backbone_attention_mask=backbone_output.attention_mask,
        )
        decoded = self.conditioner.decode(model_output, batch.embodiment_ids)
        return decoded[:, -actions.shape[1] :]

    def compute_loss(
        self,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
        *,
        noise: torch.Tensor | None = None,
        continuous_time: torch.Tensor | None = None,
    ) -> ActionHeadOutput:
        """计算 Gaussian 插值速度目标和有限 valid-count masked MSE。

        ``noise`` 与 ``continuous_time`` 是确定性验证钩子。生产调用不传入时
        保持官方 Gaussian/Beta 采样路径,传入时仍严格校验形状、设备和 dtype。
        """
        if batch.actions is None or batch.action_mask is None:
            raise ValueError("flow-matching training requires actions and action_mask")
        actions = batch.actions
        if noise is None:
            noise = torch.randn_like(actions)
        else:
            if (
                noise.shape != actions.shape
                or noise.device != actions.device
                or noise.dtype != actions.dtype
            ):
                raise ValueError("fixed noise must match action shape, device, and dtype")
            if not bool(torch.isfinite(noise).all()):
                raise ValueError("fixed flow noise must be finite")
        if continuous_time is None:
            continuous_time = sample_beta_time(
                actions.shape[0],
                device=actions.device,
                dtype=actions.dtype,
                schedule=self.schedule,
            )
        else:
            if (
                continuous_time.shape != (actions.shape[0],)
                or continuous_time.device != actions.device
                or continuous_time.dtype != actions.dtype
            ):
                raise ValueError("fixed flow time must match batch shape, device, and dtype")
            if not bool(torch.isfinite(continuous_time).all()):
                raise ValueError("fixed flow time must be finite")
            if not bool(
                ((continuous_time >= 0) & (continuous_time <= self.schedule.time_scale)).all()
            ):
                raise ValueError("fixed flow time must lie in the configured interval")
        finite_padding_target = torch.where(
            batch.action_mask,
            actions,
            torch.zeros_like(actions),
        )
        trajectory, target_velocity = interpolate_flow(
            noise,
            finite_padding_target,
            continuous_time,
        )
        timesteps = (continuous_time * self.schedule.timestep_buckets).long()
        predicted_velocity = self._predict_velocity(
            trajectory,
            timesteps,
            backbone_output=backbone_output,
            batch=batch,
            state_features=self._state_features(batch),
        )
        loss, elementwise = _finite_masked_mean_squared_error(
            predicted_velocity,
            target_velocity,
            batch.action_mask,
        )
        return ActionHeadOutput(
            loss=loss,
            elementwise_loss=elementwise,
            action_mask=batch.action_mask,
            predicted_velocity=predicted_velocity,
            target_velocity=target_velocity,
            metrics={
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
        """从 Gaussian noise 开始执行恰好四步 Euler 积分。"""
        with torch.no_grad():
            return self._predict_actions_without_grad(
                backbone_output,
                batch,
                generator=generator,
            )

    def _predict_actions_without_grad(
        self,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
        *,
        generator: torch.Generator | None,
    ) -> ActionPrediction:
        """在调用方建立的 no-grad 上下文中执行 Euler 积分。"""
        initial = torch.randn(
            (
                batch.batch_size,
                self.config.action_horizon,
                self.config.max_action_dim,
            ),
            dtype=backbone_output.features.dtype,
            device=backbone_output.features.device,
            generator=generator,
        )
        state_features = self.conditioner.encode_state(batch.state, batch.embodiment_ids)

        def velocity(actions: torch.Tensor, timesteps: torch.Tensor) -> torch.Tensor:
            """为 Euler 积分返回当前速度。"""
            return self._predict_velocity(
                actions,
                timesteps,
                backbone_output=backbone_output,
                batch=batch,
                state_features=state_features,
            )

        actions = euler_integrate(initial, velocity, schedule=self.schedule)
        mask = (
            batch.action_mask
            if batch.action_mask is not None
            else torch.ones_like(actions, dtype=torch.bool)
        )
        return ActionPrediction(normalized_actions=actions, action_mask=mask)


def _finite_masked_mean_squared_error(
    prediction: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """只在有效元素上计算 MSE,并让全 padding batch 返回可求导零损失。

    ``torch.where`` 在平方前清除无效位置,因此 padding 区的 NaN/Inf 不会通过
    ``0 * nonfinite`` 污染损失。有效位置若非有限仍自然产生非有限损失,不会被
    静默掩盖。
    """

    if prediction.shape != target.shape or mask.shape != prediction.shape:
        raise ValueError("prediction, target, and mask must share one shape")
    if mask.dtype != torch.bool:
        raise TypeError("flow-matching mask must be strict torch.bool")
    difference = torch.where(mask, prediction - target, torch.zeros_like(prediction))
    elementwise = difference.square()
    valid_count = mask.sum().to(dtype=elementwise.dtype)
    denominator = valid_count.clamp_min(1)
    return elementwise.sum() / denominator, elementwise


__all__ = ["Gr00tN1d6ActionHead"]
