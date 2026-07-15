"""Pi 路线图历史导入兼容层。"""

from autovla.models.families.pi0.specification import PI0_SPEC
from autovla.models.families.pi0_5.specification import PI0_5_SPEC
from autovla.models.families.pi0_fast.specification import PI0_FAST_SPEC

# 旧容器保留,成员直接指向规范定义。
PI_ROADMAP_FAMILY_SPECS = (PI0_SPEC, PI0_FAST_SPEC, PI0_5_SPEC)

__all__ = ["PI_ROADMAP_FAMILY_SPECS"]
