"""Pi0.5 specification-only 注册元数据。"""

from autovla.models.families.pi0_5.specification import PI0_5_SPEC, Pi0_5ModelSpec


def registration() -> Pi0_5ModelSpec:
    """返回不含 runtime factory 的 Pi0.5 规范。"""
    return PI0_5_SPEC


__all__ = ["registration"]
