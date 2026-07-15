"""R3 旧 dataloader 导入的单向兼容测试。"""

from __future__ import annotations

from autovla.data.normalization import DatasetStatistics as CanonicalDatasetStatistics
from autovla.data.normalization import FeatureStatistics as CanonicalFeatureStatistics
from autovla.dataloader.statistics import DatasetStatistics, FeatureStatistics


def test_legacy_statistics_imports_should_preserve_identity() -> None:
    """验证 M1/M2 名称直接指向唯一规范类。"""
    assert FeatureStatistics is CanonicalFeatureStatistics
    assert DatasetStatistics is CanonicalDatasetStatistics
