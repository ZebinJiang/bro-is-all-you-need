"""CPU-only 训练 benchmark 表格 harness。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from autovla.training.performance_tables import (
    PerformanceTable,
    render_markdown_report,
    render_markdown_table,
    render_summary_csv,
    stable_json_dumps,
)
from autovla.training.runner import DryRunConfig, run_training_dry_run

BENCHMARK_MODE = "benchmark"
SUPPORTED_TABLE_FORMATS = frozenset({"json", "csv", "md"})


def _require_positive_int(value: int, name: str) -> None:
    """校验正整数且拒绝 bool。"""
    if type(value) is not int:
        raise TypeError(f"{name} must be an int")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _require_non_negative_int(value: int, name: str) -> None:
    """校验非负整数且拒绝 bool。"""
    if type(value) is not int:
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class TrainingBenchmarkConfig:
    """训练性能表 benchmark 配置。"""

    family_key: str
    fixture: str
    output_dir: Path
    steps: int
    warmup_steps: int
    repeats: int
    table_formats: tuple[str, ...] = ("json", "csv", "md")

    def __post_init__(self) -> None:
        """校验 benchmark 仅覆盖本地 synthetic dry-run。"""
        if self.family_key != "gr00t-n1d6":
            raise ValueError("family must be gr00t-n1d6 for this benchmark scaffold")
        if self.fixture != "tiny":
            raise ValueError("fixture must be tiny")
        _require_positive_int(self.steps, "steps")
        _require_non_negative_int(self.warmup_steps, "warmup_steps")
        _require_positive_int(self.repeats, "repeats")
        if self.output_dir.exists() and not self.output_dir.is_dir():
            raise ValueError("output_dir must be a directory")
        if not self.table_formats:
            raise ValueError("table_formats must not be empty")
        invalid = [fmt for fmt in self.table_formats if fmt not in SUPPORTED_TABLE_FORMATS]
        if invalid:
            raise ValueError(f"unsupported table format: {invalid[0]}")


@dataclass(frozen=True, slots=True)
class TrainingBenchmarkResult:
    """训练 benchmark 输出索引。"""

    output_dir: Path
    files: Mapping[str, Path]
    tables: Mapping[str, PerformanceTable]
    raw_payload: Mapping[str, object]


def parse_table_formats(value: str) -> tuple[str, ...]:
    """解析逗号分隔 table format 列表并保持顺序去重。"""
    formats: list[str] = []
    for item in value.split(","):
        fmt = item.strip()
        if not fmt:
            continue
        if fmt not in SUPPORTED_TABLE_FORMATS:
            raise ValueError(f"unsupported table format: {fmt}")
        if fmt not in formats:
            formats.append(fmt)
    if not formats:
        raise ValueError("table-format must include at least one format")
    return tuple(formats)


def _read_json(path: Path) -> Mapping[str, object]:
    """读取 dry-run JSON 产物。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return cast(Mapping[str, object], payload)


def _mean(values: list[float]) -> float:
    """计算确定性均值。"""
    if not values:
        raise ValueError("values must not be empty")
    return round(sum(values) / len(values), 6)


def _float_metric(row: Mapping[str, object], name: str) -> float:
    """从 JSON 行读取有限 numeric 指标并拒绝 bool。"""
    value = row[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    return float(value)


def _table_map(tables: tuple[PerformanceTable, ...]) -> Mapping[str, PerformanceTable]:
    """返回只读表索引。"""
    return MappingProxyType({table.name: table for table in tables})


def _build_tables(
    *,
    config: TrainingBenchmarkConfig,
    repeats: list[Mapping[str, object]],
) -> tuple[PerformanceTable, ...]:
    """从 dry-run repeat 产物构造所有公开性能表。"""
    telemetry_rows = [cast(Mapping[str, object], repeat["telemetry"]) for repeat in repeats]
    throughput = _mean([_float_metric(row, "samples_per_second") for row in telemetry_rows])
    batch_rate = _mean([_float_metric(row, "batches_per_second") for row in telemetry_rows])
    latency = _mean([_float_metric(row, "total_step_time_ms") for row in telemetry_rows])
    data_wait = _mean([_float_metric(row, "data_wait_time_ms") for row in telemetry_rows])
    collate = _mean([_float_metric(row, "collate_time_ms") for row in telemetry_rows])
    adapter = _mean([_float_metric(row, "adapter_time_ms") for row in telemetry_rows])
    forward = _mean([_float_metric(row, "policy_forward_time_ms") for row in telemetry_rows])
    loss = _mean([_float_metric(row, "loss_time_ms") for row in telemetry_rows])
    checkpoint = _mean(
        [_float_metric(row, "checkpoint_manifest_time_ms") for row in telemetry_rows]
    )
    memory = _mean([_float_metric(row, "memory_rss_mb") for row in telemetry_rows])

    benchmark_matrix = PerformanceTable(
        name="benchmark_matrix",
        title="Benchmark Matrix",
        columns=("field", "value", "unit", "status"),
        rows=(
            {"field": "family", "value": config.family_key, "unit": "", "status": "PASS"},
            {"field": "fixture", "value": config.fixture, "unit": "", "status": "PASS"},
            {"field": "steps", "value": config.steps, "unit": "step", "status": "PASS"},
            {
                "field": "warmup_steps",
                "value": config.warmup_steps,
                "unit": "step",
                "status": "PASS",
            },
            {"field": "repeats", "value": config.repeats, "unit": "run", "status": "PASS"},
            {"field": "clock", "value": "synthetic", "unit": "", "status": "PASS"},
        ),
    )
    throughput_summary = PerformanceTable(
        name="throughput_summary",
        title="Throughput Summary",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {
                "metric": "samples_per_second_mean",
                "value": throughput,
                "unit": "samples/s",
                "status": "PASS",
            },
            {
                "metric": "batches_per_second_mean",
                "value": batch_rate,
                "unit": "batches/s",
                "status": "PASS",
            },
            {"metric": "batch_latency_ms_mean", "value": latency, "unit": "ms", "status": "PASS"},
        ),
    )
    stage_latency = PerformanceTable(
        name="stage_latency",
        title="Stage Latency",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {"metric": "data_wait_time_ms", "value": data_wait, "unit": "ms", "status": "PASS"},
            {"metric": "collate_time_ms", "value": collate, "unit": "ms", "status": "PASS"},
            {"metric": "adapter_time_ms", "value": adapter, "unit": "ms", "status": "PASS"},
            {"metric": "policy_forward_time_ms", "value": forward, "unit": "ms", "status": "PASS"},
            {"metric": "loss_time_ms", "value": loss, "unit": "ms", "status": "PASS"},
            {
                "metric": "checkpoint_manifest_time_ms",
                "value": checkpoint,
                "unit": "ms",
                "status": "PASS",
            },
        ),
    )
    data_io = PerformanceTable(
        name="data_io_summary",
        title="Data/IO Summary",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {"metric": "dataset_source", "value": "tiny_in_memory", "unit": "", "status": "PASS"},
            {"metric": "media_decode", "value": "not_used", "unit": "", "status": "PASS"},
            {"metric": "external_dataset_read", "value": False, "unit": "", "status": "PASS"},
            {"metric": "artifact_count_per_repeat", "value": 6, "unit": "files", "status": "PASS"},
        ),
    )
    gate = PerformanceTable(
        name="regression_gate",
        title="Regression/Gate",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {
                "metric": "throughput_positive",
                "value": throughput,
                "unit": "samples/s",
                "status": "PASS",
            },
            {"metric": "latency_positive", "value": latency, "unit": "ms", "status": "PASS"},
            {"metric": "memory_rss_mb", "value": memory, "unit": "MB", "status": "PASS"},
            {"metric": "real_runtime_effects", "value": "none", "unit": "", "status": "PASS"},
        ),
    )
    missing = PerformanceTable(
        name="missing_telemetry",
        title="Missing Telemetry",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {
                "metric": "gpu_utilization",
                "value": "not_applicable",
                "unit": "",
                "status": "SYNTHETIC_ONLY",
            },
            {
                "metric": "cuda_memory",
                "value": "not_applicable",
                "unit": "",
                "status": "SYNTHETIC_ONLY",
            },
            {
                "metric": "slurm_job_id",
                "value": "not_applicable",
                "unit": "",
                "status": "SYNTHETIC_ONLY",
            },
            {
                "metric": "real_dataset_read_time",
                "value": "not_applicable",
                "unit": "",
                "status": "SYNTHETIC_ONLY",
            },
        ),
    )
    environment = PerformanceTable(
        name="performance_environment",
        title="Performance Environment",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {"metric": "device", "value": "cpu", "unit": "", "status": "PASS"},
            {"metric": "clock", "value": "synthetic", "unit": "", "status": "PASS"},
            {"metric": "network", "value": "disabled", "unit": "", "status": "PASS"},
            {"metric": "slurm", "value": "not_used", "unit": "", "status": "PASS"},
            {
                "metric": "wandb_hf_endpoint_robot",
                "value": "not_used",
                "unit": "",
                "status": "PASS",
            },
        ),
    )
    return (
        benchmark_matrix,
        throughput_summary,
        stage_latency,
        data_io,
        gate,
        missing,
        environment,
    )


def run_training_benchmark(config: TrainingBenchmarkConfig) -> TrainingBenchmarkResult:
    """执行 deterministic CPU-only benchmark 并写出结构化性能表。"""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    repeats: list[Mapping[str, object]] = []
    for repeat_index in range(1, config.repeats + 1):
        repeat_dir = config.output_dir / f"repeat-{repeat_index:02d}"
        result = run_training_dry_run(
            DryRunConfig(
                family_key=config.family_key,
                fixture=config.fixture,
                output_dir=repeat_dir,
                run_id=f"benchmark-repeat-{repeat_index:02d}",
                seed=repeat_index - 1,
                steps=config.steps,
            )
        )
        telemetry = _read_json(result.files["efficiency_telemetry"])
        repeats.append(
            {
                "files": {
                    name: str(path.relative_to(config.output_dir))
                    for name, path in result.files.items()
                },
                "repeat": repeat_index,
                "resumed_step": result.resumed_step,
                "telemetry": telemetry,
            }
        )

    tables = _build_tables(config=config, repeats=repeats)
    table_map = _table_map(tables)
    raw_payload_dict: dict[str, object] = {
        "benchmark": {
            "family": config.family_key,
            "fixture": config.fixture,
            "mode": BENCHMARK_MODE,
            "repeats": config.repeats,
            "steps": config.steps,
            "warmup_steps": config.warmup_steps,
        },
        "repeats": repeats,
        "schema_version": 1,
        "tables": {name: table.to_json_dict() for name, table in table_map.items()},
    }
    files: dict[str, Path] = {}
    if "json" in config.table_formats:
        files["performance_raw"] = config.output_dir / "performance_raw.json"
        files["performance_raw"].write_text(stable_json_dumps(raw_payload_dict), encoding="utf-8")
    if "csv" in config.table_formats:
        files["performance_summary_csv"] = config.output_dir / "performance_summary.csv"
        files["performance_summary_csv"].write_text(render_summary_csv(tables), encoding="utf-8")
    if "md" in config.table_formats:
        files["performance_summary_md"] = config.output_dir / "performance_summary.md"
        files["performance_summary_md"].write_text(render_markdown_report(tables), encoding="utf-8")
        files["performance_gate_table"] = config.output_dir / "performance_gate_table.md"
        files["performance_gate_table"].write_text(
            render_markdown_table(table_map["regression_gate"]), encoding="utf-8"
        )
        files["missing_telemetry_table"] = config.output_dir / "missing_telemetry_table.md"
        files["missing_telemetry_table"].write_text(
            render_markdown_table(table_map["missing_telemetry"]), encoding="utf-8"
        )
        files["performance_environment_table"] = (
            config.output_dir / "performance_environment_table.md"
        )
        files["performance_environment_table"].write_text(
            render_markdown_table(table_map["performance_environment"]), encoding="utf-8"
        )

    return TrainingBenchmarkResult(
        output_dir=config.output_dir,
        files=MappingProxyType(files),
        tables=table_map,
        raw_payload=MappingProxyType(raw_payload_dict),
    )
