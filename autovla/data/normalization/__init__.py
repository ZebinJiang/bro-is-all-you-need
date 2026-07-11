"""AutoVLA 归一化公共接口。"""

from autovla.data.normalization.registry import (
    NormalizationRegistry,
    build_normalization_registry,
)
from autovla.data.normalization.statistics import (
    FeatureNormalizationStatistics,
    NormalizationStatistics,
)
from autovla.data.normalization.transforms import (
    NormalizationTransform,
    RelativeActionTransform,
    StatisticsNormalizationTransform,
)

__all__ = [
    "FeatureNormalizationStatistics",
    "NormalizationRegistry",
    "NormalizationStatistics",
    "NormalizationTransform",
    "RelativeActionTransform",
    "StatisticsNormalizationTransform",
    "build_normalization_registry",
]
