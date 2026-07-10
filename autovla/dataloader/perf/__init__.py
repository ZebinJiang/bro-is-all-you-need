"""DataLoader 性能工具的轻量懒加载导出。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autovla.dataloader.perf.benchmark import BenchmarkResult, run_benchmark
    from autovla.dataloader.perf.config import BenchmarkMode, PerfBenchmarkConfig
    from autovla.dataloader.perf.metrics import PerfMetrics, percentile
    from autovla.dataloader.perf.report import (
        PerfClassification,
        classify_perf_report,
        classify_training_store_comparison,
    )
    from autovla.dataloader.perf.synthetic import (
        SyntheticDataloaderBenchmarkConfig,
        SyntheticDataloaderBenchmarkResult,
        run_synthetic_dataloader_benchmark,
    )
    from autovla.dataloader.perf.training_store import (
        PFS_STORAGE_BACKEND,
        TRAINING_STORE_FORMAT,
        TRAINING_STORE_SCHEMA_VERSION,
    )

_EXPORTS = {
    "PFS_STORAGE_BACKEND": "autovla.dataloader.perf.training_store",
    "TRAINING_STORE_FORMAT": "autovla.dataloader.perf.training_store",
    "TRAINING_STORE_SCHEMA_VERSION": "autovla.dataloader.perf.training_store",
    "BenchmarkMode": "autovla.dataloader.perf.config",
    "BenchmarkResult": "autovla.dataloader.perf.benchmark",
    "PerfBenchmarkConfig": "autovla.dataloader.perf.config",
    "PerfClassification": "autovla.dataloader.perf.report",
    "PerfMetrics": "autovla.dataloader.perf.metrics",
    "SyntheticDataloaderBenchmarkConfig": "autovla.dataloader.perf.synthetic",
    "SyntheticDataloaderBenchmarkResult": "autovla.dataloader.perf.synthetic",
    "classify_perf_report": "autovla.dataloader.perf.report",
    "classify_training_store_comparison": "autovla.dataloader.perf.report",
    "percentile": "autovla.dataloader.perf.metrics",
    "run_benchmark": "autovla.dataloader.perf.benchmark",
    "run_synthetic_dataloader_benchmark": "autovla.dataloader.perf.synthetic",
}

__all__ = [
    "PFS_STORAGE_BACKEND",
    "TRAINING_STORE_FORMAT",
    "TRAINING_STORE_SCHEMA_VERSION",
    "BenchmarkMode",
    "BenchmarkResult",
    "PerfBenchmarkConfig",
    "PerfClassification",
    "PerfMetrics",
    "SyntheticDataloaderBenchmarkConfig",
    "SyntheticDataloaderBenchmarkResult",
    "classify_perf_report",
    "classify_training_store_comparison",
    "percentile",
    "run_benchmark",
    "run_synthetic_dataloader_benchmark",
]


def __getattr__(name: str) -> object:
    """按需解析性能工具公共导出。"""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共导出名称。"""
    return sorted(set(globals()) | set(__all__))
