"""Pi0.5 旧注册调用兼容层。"""

from autovla.models.families.pi0_5.family import PI05_SPEC, Pi05FamilyDefinition


def registration() -> Pi05FamilyDefinition:
    """返回唯一 Pi0.5 家族定义。"""

    return PI05_SPEC


__all__ = ["registration"]
