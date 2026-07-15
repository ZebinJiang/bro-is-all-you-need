"""GR00T N1.6.1 规范定义的历史注册入口。"""

from __future__ import annotations

from autovla.models.families.gr00t_n1d6.specification import (
    GR00T_N1D6_SPEC,
)
from autovla.models.families.specification import ModelFamilyDefinition

# 历史类型名与规范定义保持同一类型身份,不再维护第二套注册结构。
Gr00tN1d6Registration = ModelFamilyDefinition


def registration() -> Gr00tN1d6Registration:
    """返回规范定义同一对象,且不导入任何模型运行时。"""
    return GR00T_N1D6_SPEC


__all__ = ["Gr00tN1d6Registration", "registration"]
