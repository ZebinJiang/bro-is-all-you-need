"""GR00T 历史元数据导入兼容层。"""

from autovla.models.families.gr00t_n1d6.specification import GR00T_N1D6_SPEC

# 保持对象身份,不创建 metadata 副本。
GR00T_N1D6_FAMILY_SPEC = GR00T_N1D6_SPEC

__all__ = ["GR00T_N1D6_FAMILY_SPEC"]
