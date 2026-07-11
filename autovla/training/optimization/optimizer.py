"""AutoVLA AdamW 优化器工厂。"""

from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import nn

from autovla.config.schema.optimization import OptimizationConfig
from autovla.training.optimization.parameter_groups import (
    ParameterGroupOptions,
    ParameterRole,
    build_parameter_groups,
)


def create_adamw(
    model: nn.Module,
    roles: Mapping[str, ParameterRole],
    config: OptimizationConfig,
) -> torch.optim.AdamW:
    """根据显式参数角色创建 AdamW,拒绝其他优化器键。"""

    if config.optimizer_key != "adamw":
        raise ValueError(f"unsupported optimizer key: {config.optimizer_key!r}")
    groups = build_parameter_groups(
        model,
        roles,
        ParameterGroupOptions(
            learning_rate=config.learning_rate,
            backbone_learning_rate=config.backbone_learning_rate,
            action_head_learning_rate=config.action_head_learning_rate,
            weight_decay=config.weight_decay,
        ),
    )
    return torch.optim.AdamW(
        groups,
        lr=config.learning_rate,
        betas=config.betas,
        eps=config.epsilon,
    )


__all__ = ["create_adamw"]
