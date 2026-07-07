"""GPU200 遥测报告与表格输出。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TypeAlias

from autovla.training.metrics import stable_json_dumps
from autovla.training.performance_tables import (
    JsonScalar,
    PerformanceTable,
    render_markdown_report,
    render_markdown_table,
)
from autovla.training.telemetry.config import TelemetryConfig
from autovla.training.telemetry.samplers import CpuIoTelemetrySnapshot, GpuTelemetrySnapshot

StepSample: TypeAlias = dict[str, JsonScalar]
TableRow: TypeAlias = dict[str, JsonScalar]
MetricMap: TypeAlias = dict[str, JsonScalar]

_GPU_FIELDS = {
    "gpu_memory_total_mb": "MB",
    "gpu_memory_used_mb": "MB",
    "gpu_power_draw_w": "W",
    "gpu_temperature_c": "C",
    "gpu_utilization_pct": "%",
}
_CPU_IO_FIELDS = {
    "cpu_system_pct": "%",
    "cpu_user_pct": "%",
    "io_read_mib_per_s": "MiB/s",
    "io_write_mib_per_s": "MiB/s",
    "memory_rss_mb": "MB",
}


@dataclass(frozen=True, slots=True)
class TelemetryOutputIndex:
    """报告输出文件索引。"""

    files: Mapping[str, Path]


def _missing_marker() -> str:
    """返回统一缺失标记。"""
    return "missing"


def build_step_sample(
    *,
    step: int,
    gpu_snapshot: GpuTelemetrySnapshot | None,
    cpu_io_snapshot: CpuIoTelemetrySnapshot | None,
) -> StepSample:
    """构造单步 JSON 样本。"""
    sample: StepSample = {"step": step}
    if gpu_snapshot is None:
        for key in _GPU_FIELDS:
            sample[key] = _missing_marker()
    else:
        sample.update(
            {
                "gpu_utilization_pct": gpu_snapshot.gpu_utilization_pct,
                "gpu_memory_used_mb": gpu_snapshot.memory_used_mb,
                "gpu_memory_total_mb": gpu_snapshot.memory_total_mb,
                "gpu_temperature_c": gpu_snapshot.temperature_c,
                "gpu_power_draw_w": gpu_snapshot.power_draw_w,
            }
        )
    if cpu_io_snapshot is None:
        for key in _CPU_IO_FIELDS:
            sample[key] = _missing_marker()
    else:
        sample.update(
            {
                "cpu_user_pct": cpu_io_snapshot.cpu_user_pct,
                "cpu_system_pct": cpu_io_snapshot.cpu_system_pct,
                "io_read_mib_per_s": cpu_io_snapshot.io_read_mib_per_s,
                "io_write_mib_per_s": cpu_io_snapshot.io_write_mib_per_s,
                "memory_rss_mb": cpu_io_snapshot.memory_rss_mb,
            }
        )
    sample["model_runtime_status"] = "metadata_only_unverified"
    return sample


def _summarize_metric(step_samples: tuple[StepSample, ...], key: str) -> JsonScalar:
    """对 metric 求均值, 无数值时返回缺失标记。"""
    numeric_values = [
        float(value)
        for sample in step_samples
        if isinstance((value := sample[key]), (int, float)) and not isinstance(value, bool)
    ]
    if not numeric_values:
        return _missing_marker()
    return round(sum(numeric_values) / len(numeric_values), 6)


@dataclass(frozen=True, slots=True)
class AggregateSummary:
    """聚合遥测摘要。"""

    dataset_fingerprint: str
    datastore_name: str
    max_steps: int
    missing_metrics: tuple[str, ...]
    model_family_key: str
    model_runtime_status: str
    observed_step_count: int
    statistics_fingerprint: str
    transform_fingerprint: str
    metrics: Mapping[str, JsonScalar]

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 结构。"""
        return {
            "dataset_fingerprint": self.dataset_fingerprint,
            "datastore_name": self.datastore_name,
            "max_steps": self.max_steps,
            "missing_metrics": list(self.missing_metrics),
            "metrics": dict(self.metrics),
            "model_family_key": self.model_family_key,
            "model_runtime_status": self.model_runtime_status,
            "observed_step_count": self.observed_step_count,
            "statistics_fingerprint": self.statistics_fingerprint,
            "transform_fingerprint": self.transform_fingerprint,
        }


def _aggregate_summary(
    config: TelemetryConfig, step_samples: tuple[StepSample, ...]
) -> AggregateSummary:
    """构造 aggregate JSON 负载。"""
    metric_keys = tuple(_GPU_FIELDS) + tuple(_CPU_IO_FIELDS)
    missing_metrics = tuple(
        sorted(
            key
            for key in metric_keys
            if any(sample[key] == _missing_marker() for sample in step_samples)
        )
    )
    metrics: MetricMap = {key: _summarize_metric(step_samples, key) for key in metric_keys}
    return AggregateSummary(
        dataset_fingerprint=config.dataset_fingerprint,
        datastore_name=config.datastore_name,
        max_steps=config.max_steps,
        missing_metrics=missing_metrics,
        model_family_key=config.model_family_key,
        model_runtime_status="metadata_only_unverified",
        observed_step_count=len(step_samples),
        statistics_fingerprint=config.statistics_fingerprint,
        transform_fingerprint=config.transform_fingerprint,
        metrics=metrics,
    )


def _table_rows_from_aggregate(aggregate: AggregateSummary) -> tuple[TableRow, ...]:
    """将 aggregate 指标变成通用表格行。"""
    missing_metric_names = set(aggregate.missing_metrics)
    rows: list[TableRow] = []
    for key in tuple(_GPU_FIELDS) + tuple(_CPU_IO_FIELDS):
        if key in missing_metric_names:
            status = "missing"
        else:
            status = "PASS" if aggregate.metrics[key] != _missing_marker() else "missing"
        unit = _GPU_FIELDS.get(key, _CPU_IO_FIELDS.get(key, ""))
        rows.append(
            {"metric": key, "value": aggregate.metrics[key], "unit": unit, "status": status}
        )
    rows.append(
        {
            "metric": "model_runtime_status",
            "value": aggregate.model_runtime_status,
            "unit": "",
            "status": "WARN",
        }
    )
    return tuple(rows)


def _step_table(step_samples: tuple[StepSample, ...]) -> PerformanceTable:
    """生成逐步表格。"""
    return PerformanceTable(
        name="gpu200_step_samples",
        title="GPU200 Step Samples",
        columns=("step", "gpu_utilization_pct", "cpu_user_pct", "io_read_mib_per_s", "status"),
        rows=tuple(
            {
                "step": sample["step"],
                "gpu_utilization_pct": sample["gpu_utilization_pct"],
                "cpu_user_pct": sample["cpu_user_pct"],
                "io_read_mib_per_s": sample["io_read_mib_per_s"],
                "status": (
                    "PASS"
                    if sample["gpu_utilization_pct"] != _missing_marker()
                    or sample["cpu_user_pct"] != _missing_marker()
                    else "missing"
                ),
            }
            for sample in step_samples
        ),
    )


def _aggregate_table(aggregate: AggregateSummary) -> PerformanceTable:
    """生成 aggregate 表格。"""
    return PerformanceTable(
        name="gpu200_aggregate",
        title="GPU200 Aggregate",
        columns=("metric", "value", "unit", "status"),
        rows=_table_rows_from_aggregate(aggregate),
    )


def _missing_table(aggregate: AggregateSummary) -> PerformanceTable:
    """生成缺失指标表。"""
    return PerformanceTable(
        name="gpu200_missing_metrics",
        title="GPU200 Missing Metrics",
        columns=("metric", "value", "unit", "status"),
        rows=tuple(
            {"metric": metric, "value": _missing_marker(), "unit": "", "status": "missing"}
            for metric in aggregate.missing_metrics
        )
        or ({"metric": "none", "value": "none", "unit": "", "status": "PASS"},),
    )


def _environment_table(config: TelemetryConfig) -> PerformanceTable:
    """生成环境/边界表。"""
    return PerformanceTable(
        name="gpu200_environment",
        title="GPU200 Environment",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {"metric": "env_profile", "value": config.env_profile, "unit": "", "status": "PASS"},
            {
                "metric": "wandb_mode",
                "value": "offline_only",
                "unit": "",
                "status": "PASS",
            },
            {"metric": "hf_network", "value": False, "unit": "", "status": "PASS"},
            {"metric": "real_model_runtime", "value": False, "unit": "", "status": "PASS"},
            {"metric": "real_dataset_mutation", "value": False, "unit": "", "status": "PASS"},
        ),
    )


def write_telemetry_outputs(
    config: TelemetryConfig, step_samples: tuple[StepSample, ...]
) -> Mapping[str, Path]:
    """写出逐步/聚合 JSON 与 Markdown 表格。"""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = _aggregate_summary(config, step_samples)
    aggregate_payload = {
        "aggregate": aggregate.to_json_dict(),
        "schema_version": "autovla.training.telemetry.aggregate.v1",
        "step_samples": list(step_samples),
    }
    step_table = _step_table(step_samples)
    aggregate_table = _aggregate_table(aggregate)
    missing_table = _missing_table(aggregate)
    environment_table = _environment_table(config)
    files = {
        "step_samples_json": config.output_dir / "telemetry_step_samples.json",
        "aggregate_json": config.output_dir / "telemetry_aggregate.json",
        "step_table": config.output_dir / "telemetry_step_table.md",
        "aggregate_table": config.output_dir / "telemetry_aggregate_table.md",
        "missing_table": config.output_dir / "telemetry_missing_table.md",
        "environment_table": config.output_dir / "telemetry_environment_table.md",
        "summary_markdown": config.output_dir / "telemetry_summary.md",
    }
    files["step_samples_json"].write_text(stable_json_dumps(list(step_samples)), encoding="utf-8")
    files["aggregate_json"].write_text(stable_json_dumps(aggregate_payload), encoding="utf-8")
    files["step_table"].write_text(render_markdown_table(step_table), encoding="utf-8")
    files["aggregate_table"].write_text(render_markdown_table(aggregate_table), encoding="utf-8")
    files["missing_table"].write_text(render_markdown_table(missing_table), encoding="utf-8")
    files["environment_table"].write_text(
        render_markdown_table(environment_table), encoding="utf-8"
    )
    files["summary_markdown"].write_text(
        render_markdown_report((aggregate_table, missing_table, environment_table)),
        encoding="utf-8",
    )
    return MappingProxyType(files)
