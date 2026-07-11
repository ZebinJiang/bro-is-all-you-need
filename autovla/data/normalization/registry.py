"""AutoVLA 归一化变换注册表。"""

from autovla.core.registry import ComponentRegistry, ImportStringFactory
from autovla.data.normalization.transforms import NormalizationTransform


class NormalizationRegistry(ComponentRegistry[ImportStringFactory[NormalizationTransform]]):
    """保存归一化变换懒工厂元数据。"""


def build_normalization_registry() -> NormalizationRegistry:
    """构造不选择默认策略的归一化注册表。"""
    registry = NormalizationRegistry("autovla-normalization")
    registry.register(
        "statistics",
        ImportStringFactory(
            "autovla.data.normalization.transforms:StatisticsNormalizationTransform"
        ),
    )
    return registry


__all__ = ["NormalizationRegistry", "build_normalization_registry"]
