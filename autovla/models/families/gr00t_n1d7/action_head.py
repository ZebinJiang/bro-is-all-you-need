"""GR00T N1.7 embodiment-conditioned AlternateVLDiT 动作头。"""

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


class _AlternateVLDiTBlock(nn.Module):
    """交替执行动作自注意力、VL 交叉注意力和前馈更新。"""

    def __init__(self, width: int, heads: int, *, cross_attention: bool) -> None:
        """构造 pre-norm attention block, 不拥有训练生命周期。"""

        super().__init__()
        self.self_norm = nn.LayerNorm(width)
        self.self_attention = nn.MultiheadAttention(width, heads, batch_first=True)
        self.cross_attention_enabled = cross_attention
        self.cross_norm = nn.LayerNorm(width)
        self.cross_attention = nn.MultiheadAttention(width, heads, batch_first=True)
        self.ff_norm = nn.LayerNorm(width)
        self.feed_forward = nn.Sequential(
            nn.Linear(width, width * 4),
            nn.GELU(approximate="tanh"),
            nn.Linear(width * 4, width),
        )

    def forward(
        self,
        hidden: torch.Tensor,
        vl_features: torch.Tensor,
        vl_padding_mask: torch.Tensor,
    ) -> torch.Tensor:
        """保持 ``[B,S,1024]`` 布局并在指定块读取 VL token。"""

        normalized = self.self_norm(hidden)
        hidden = (
            hidden + self.self_attention(normalized, normalized, normalized, need_weights=False)[0]
        )
        if self.cross_attention_enabled:
            query = self.cross_norm(hidden)
            hidden = (
                hidden
                + self.cross_attention(
                    query,
                    vl_features,
                    vl_features,
                    key_padding_mask=vl_padding_mask,
                    need_weights=False,
                )[0]
            )
        return hidden + self.feed_forward(self.ff_norm(hidden))


class _EmbodimentProjectors(nn.Module):
    """用 32 个 embodiment embedding 调制状态、动作和输出投影。"""

    def __init__(self, config: Gr00tN1d7Config) -> None:
        """构造固定 132 维 envelope 的共享线性映射。"""

        super().__init__()
        width = config.action_model_width
        self.embodiment_embedding = nn.Embedding(config.max_num_embodiments, width)
        self.state_encoder = nn.Linear(config.max_state_dim, width)
        self.action_encoder = nn.Linear(config.max_action_dim, width)
        self.action_decoder = nn.Linear(width, config.max_action_dim)

    def condition(self, values: torch.Tensor, embodiment_ids: torch.Tensor) -> torch.Tensor:
        """把 ``[B,W]`` embodiment 向量广播到序列。"""

        return values + self.embodiment_embedding(embodiment_ids).unsqueeze(1)


class Gr00tN1d7ActionHead(ActionHead):
    """实现 32 层 AlternateVLDiT、4 层 VL self-attention 与四步 Euler。"""

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
        """构造参数图; 固定 hook 仅用于确定性验证, 不进入 state dict。"""

        initialize_torch_module(super())
        if not isinstance(cast(object, config), Gr00tN1d7Config):
            raise TypeError("action head requires Gr00tN1d7Config")
        self.config = config
        self.schedule = FlowMatchingSchedule(
            beta_alpha=config.flow_beta_alpha,
            beta_beta=config.flow_beta_beta,
            time_scale=config.flow_time_scale,
            timestep_buckets=config.timestep_buckets,
            inference_steps=config.num_inference_steps,
        )
        self.projectors = _EmbodimentProjectors(config)
        width = config.action_model_width
        self.vlln = nn.LayerNorm(config.backbone_hidden_size)
        self.vl_projection = nn.Linear(config.backbone_hidden_size, width)
        self.vl_self_attention = nn.ModuleList(
            nn.TransformerEncoderLayer(
                d_model=width,
                nhead=config.action_attention_heads,
                dim_feedforward=width * 4,
                batch_first=True,
                norm_first=True,
            )
            for _ in range(config.vl_self_attention_layers)
        )
        self.diffusion_model = nn.ModuleList(
            _AlternateVLDiTBlock(
                width,
                config.action_attention_heads,
                cross_attention=index % 2 == 0,
            )
            for index in range(config.diffusion_layers)
        )
        self.position_embedding = nn.Embedding(config.action_horizon + 1, width)
        self.time_embedding = nn.Embedding(config.timestep_buckets, width)
        self.mask_token = nn.Parameter(torch.zeros(1, 1, width))
        nn.init.normal_(self.position_embedding.weight, std=0.02)
        nn.init.normal_(self.time_embedding.weight, std=0.02)
        nn.init.normal_(self.mask_token, std=0.02)
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
        """返回动作头与 embodiment projector 的显式策略。"""

        return {
            "action_head_trainable": self.config.tune_action_head,
            "embodiment_projectors_trainable": self.config.tune_projectors,
        }

    def _apply_tune_policy(self) -> None:
        """先冻结全部, 再按 artifact 开关解冻投影、扩散和 VLLN。"""

        self.requires_grad_(False)
        if not self.config.tune_action_head:
            return
        if self.config.tune_projectors:
            self.projectors.requires_grad_(True)
            self.position_embedding.requires_grad_(True)
            self.time_embedding.requires_grad_(True)
            self.mask_token.requires_grad_(True)
            self.vl_projection.requires_grad_(True)
        if self.config.tune_diffusion_model:
            self.diffusion_model.requires_grad_(True)
            self.vl_self_attention.requires_grad_(True)
        if self.config.tune_vlln:
            self.vlln.requires_grad_(True)

    def _state_features(self, batch: ModelInputBatch) -> torch.Tensor:
        """编码 ``[B,T,132]`` 状态并应用逐样本 dropout。"""

        state = self.projectors.state_encoder(batch.state)
        state = self.projectors.condition(state, batch.embodiment_ids)
        if self.training and self.config.state_dropout_probability > 0:
            dropped = torch.rand(state.shape[0], device=state.device)
            dropped = dropped.lt(self.config.state_dropout_probability).reshape(-1, 1, 1)
            state = torch.where(dropped, self.mask_token.to(state.dtype), state)
        return state

    def _vl_features(self, output: BackboneOutput) -> torch.Tensor:
        """先执行四层 VL self-attention, 再供交替扩散块读取。"""

        values = self.vl_projection(self.vlln(output.features))
        padding = ~output.attention_mask
        for layer in self.vl_self_attention:
            values = layer(values, src_key_padding_mask=padding)
        return values

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
        """预测保持 ``[B,40,132]`` 的流速度。"""

        action = self.projectors.action_encoder(actions)
        action = self.projectors.condition(action, batch.embodiment_ids)
        positions = torch.arange(actions.shape[1], device=actions.device)
        action = action + self.position_embedding(positions).unsqueeze(0)
        time = self.time_embedding(timesteps.clamp(0, self.config.timestep_buckets - 1))
        hidden = torch.cat((state_features, action + time.unsqueeze(1)), dim=1)
        padding = ~backbone_output.attention_mask
        for block in self.diffusion_model:
            hidden = block(hidden, vl_features, padding)
        decoded = self.projectors.action_decoder(hidden[:, -actions.shape[1] :])
        return decoded

    def compute_loss(
        self,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
    ) -> ActionHeadOutput:
        """按有效元素总数归一化 flow-matching MSE。"""

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
                actions.shape[0], actions.device, actions.dtype, self.schedule
            )
        trajectory, target = interpolate_flow(noise, actions, continuous_time)
        timesteps = (continuous_time * self.schedule.timestep_buckets).long()
        predicted = self._predict_velocity(
            trajectory,
            timesteps,
            backbone_output=backbone_output,
            batch=batch,
            state_features=self._state_features(batch),
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
        """从固定或随机 Gaussian noise 执行恰好四次显式 Euler 更新。"""

        with torch.no_grad():
            initial = torch.randn(
                (batch.batch_size, self.config.action_horizon, self.config.max_action_dim),
                device=backbone_output.features.device,
                dtype=backbone_output.features.dtype,
                generator=generator,
            )
            if self._noise_hook is not None:
                initial = self._noise_hook(initial)
            state = self.projectors.condition(
                self.projectors.state_encoder(batch.state), batch.embodiment_ids
            )
            vl_features = self._vl_features(backbone_output)

            def velocity(actions: torch.Tensor, timesteps: torch.Tensor) -> torch.Tensor:
                """复用同一参数图返回 Euler 当前速度。"""

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
