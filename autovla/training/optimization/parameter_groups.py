"""基于显式参数角色构建 AdamW 参数组。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from torch import nn


class ParameterRole(str, Enum):
    """声明参数属于骨干、动作头或通用训练组件。"""

    BACKBONE = "backbone"
    ACTION_HEAD = "action_head"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ParameterGroupOptions:
    """保存各参数角色学习率与权重衰减。"""

    learning_rate: float
    backbone_learning_rate: float | None
    action_head_learning_rate: float | None
    weight_decay: float


_NO_DECAY_MODULES = (
    nn.LayerNorm,
    nn.GroupNorm,
    nn.BatchNorm1d,
    nn.BatchNorm2d,
    nn.BatchNorm3d,
    nn.Embedding,
)


def build_parameter_groups(
    model: nn.Module,
    roles: Mapping[str, ParameterRole],
    options: ParameterGroupOptions,
) -> list[dict[str, object]]:
    """按显式角色、bias 和归一化模块构建无重复参数组。

    ``roles`` 必须覆盖每个可训练参数,函数不会从参数名猜测骨干或动作头。
    bias 与已知归一化/Embedding 参数强制使用零衰减。
    """

    modules = dict(model.named_modules())
    grouped: dict[tuple[ParameterRole, bool], list[nn.Parameter]] = {}
    trainable_names: set[str] = set()
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        trainable_names.add(name)
        if name not in roles:
            raise ValueError(f"missing explicit parameter role for {name!r}")
        role = roles[name]
        module_name, _, leaf_name = name.rpartition(".")
        owner = modules.get(module_name, model if not module_name else None)
        no_decay = leaf_name == "bias" or isinstance(owner, _NO_DECAY_MODULES)
        grouped.setdefault((role, no_decay), []).append(parameter)
    unknown = set(roles) - trainable_names
    if unknown:
        raise ValueError(
            f"parameter roles reference unknown or frozen parameters: {sorted(unknown)}"
        )
    if not grouped:
        raise ValueError("model has no trainable parameters")

    role_lrs = {
        ParameterRole.BACKBONE: options.backbone_learning_rate or options.learning_rate,
        ParameterRole.ACTION_HEAD: options.action_head_learning_rate or options.learning_rate,
        ParameterRole.OTHER: options.learning_rate,
    }
    return [
        {
            "params": parameters,
            "lr": role_lrs[role],
            "weight_decay": 0.0 if no_decay else options.weight_decay,
            "parameter_role": role.value,
            "decay": not no_decay,
        }
        for (role, no_decay), parameters in sorted(
            grouped.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
    ]


__all__ = ["ParameterGroupOptions", "ParameterRole", "build_parameter_groups"]
