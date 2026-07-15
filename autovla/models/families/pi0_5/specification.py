"""Pi0.5 旧规范导入兼容层;唯一事实源位于 ``family``。"""

from autovla.models.families.pi0_5.family import PI05_SPEC, Pi05FamilyDefinition

PI0_5_SPEC = PI05_SPEC
Pi0_5ModelSpec = Pi05FamilyDefinition

__all__ = ["PI0_5_SPEC", "Pi0_5ModelSpec"]
