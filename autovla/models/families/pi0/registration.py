"""Pi0 specification-only 注册元数据。"""

from autovla.models.families.pi0.specification import PI0_SPEC, Pi0ModelSpec


def registration() -> Pi0ModelSpec:
    """返回不含 runtime factory 的 Pi0 规范。"""
    return PI0_SPEC


__all__ = ["registration"]
