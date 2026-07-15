"""Pi0-FAST 轻量注册兼容入口。"""

from autovla.models.families.pi0_fast.specification import PI0_FAST_SPEC


def registration():
    """返回规范定义,不执行任何运行时导入。"""

    return PI0_FAST_SPEC


__all__ = ["registration"]
