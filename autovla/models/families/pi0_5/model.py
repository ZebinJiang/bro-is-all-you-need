# SPDX-License-Identifier: Apache-2.0
# Source: https://github.com/Physical-Intelligence/openpi/tree/15a9616a00943ada6c20a0f158e3adb39df2ccac
# License: Apache-2.0 source; model, tokenizer and checkpoint terms are separate.
# Reuse: Adapted official prefix/action-expert composition.
# AutoVLA changes: Canonical model interface and action_head parameter ownership.
# ruff: noqa: RUF002
"""Pi0.5 单一前缀/动作 expert 组合模型。"""

from __future__ import annotations

from collections.abc import Callable

import torch

from autovla.models.families.pi0_5._openpi_compat import PrefixKVCache
from autovla.models.families.pi0_5.action_head import Pi05ActionExpert
from autovla.models.families.pi0_5.backbone import Pi05VisionLanguageBackbone
from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.interfaces.model import VisionLanguageActionModel
from autovla.models.outputs import ActionPrediction, ModelInputBatch, ModelOutput


class Pi05Model(VisionLanguageActionModel):
    """组合唯一 PaliGemma/SigLIP 前缀与 Gemma action expert。"""

    def __init__(
        self,
        config: Pi05Config,
        backbone: Pi05VisionLanguageBackbone,
        action_head: Pi05ActionExpert,
    ) -> None:
        """注册全部组件并关闭配置身份漂移。"""

        super().__init__()
        if backbone.config != config or action_head.config != config:
            raise ValueError("Pi0.5 components must share one exact config")
        self.config = config
        self.backbone = backbone
        self.action_head = action_head

    @property
    def action_expert(self) -> Pi05ActionExpert:
        """保留旧 Python 属性，但不注册第二个 state-dict 命名空间。"""

        return self.action_head

    def forward(self, batch: ModelInputBatch) -> ModelOutput:
        """执行前缀编码、flow velocity 与严格 masked scalar loss。"""

        backbone_output = self.backbone(batch)
        action_output = self.action_expert.compute_loss(backbone_output, batch)
        return ModelOutput(action_output.loss, backbone_output, action_output)

    def predict_actions(
        self,
        batch: ModelInputBatch,
        *,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """前缀只编码一次，并在十步 Euler 中复用同一层级 cache。"""

        with torch.no_grad():
            backbone_output = self.backbone(batch)
            return self.action_expert.predict_actions(backbone_output, batch, generator=generator)

    def gradient_checkpointing_enable(self) -> None:
        """同时启用前缀和 expert gradient checkpointing。"""

        self.backbone.gradient_checkpointing_enable()
        self.action_expert.gradient_checkpointing_enable()

    def gradient_checkpointing_disable(self) -> None:
        """同时关闭前缀和 expert gradient checkpointing。"""

        self.backbone.gradient_checkpointing_disable()
        self.action_expert.gradient_checkpointing_disable()

    def parameter_plan(self) -> dict[str, tuple[str, ...]]:
        """按标准 state-dict 名返回互斥的可训练和冻结参数清单。"""

        trainable: list[str] = []
        frozen: list[str] = []
        for name, parameter in self.named_parameters():
            (trainable if parameter.requires_grad else frozen).append(name)
        if not trainable or not frozen or set(trainable) & set(frozen):
            raise RuntimeError("Pi0.5 parameter tuning plan must contain disjoint sets")
        return {"trainable": tuple(trainable), "frozen": tuple(frozen)}

    @staticmethod
    def flow_training_sample(
        actions: torch.Tensor,
        noise: torch.Tensor,
        time: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """兼容入口：返回 OpenPI 方向的插值和速度目标。"""

        if time.shape == (actions.shape[0], 1, 1):
            time = time[:, 0, 0]
        return Pi05ActionExpert.flow_training_sample(actions, noise, time)

    def euler_denoise(
        self,
        noise: torch.Tensor,
        prefix_cache: PrefixKVCache | object,
        velocity_fn: Callable[[torch.Tensor, float, object], torch.Tensor],
    ) -> torch.Tensor:
        """兼容入口：固定十步读取同一 cache，禁止回调替换 cache。"""

        if noise.shape[-2:] != (
            self.config.action_horizon,
            self.config.action_dimension,
        ):
            raise ValueError("Euler noise must match configured [H,32]")
        value = noise
        step = -1.0 / self.config.num_inference_steps
        for index in range(self.config.num_inference_steps):
            velocity = velocity_fn(value, 1.0 + index * step, prefix_cache)
            if isinstance(velocity, tuple):
                raise TypeError("velocity_fn must not return or replace prefix cache")
            if velocity.shape != value.shape:
                raise ValueError("velocity must preserve action shape")
            value = value + step * velocity
        return value


__all__ = ["Pi05Model"]
