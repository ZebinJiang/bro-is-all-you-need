"""DataLoader synthetic 性能表 scaffold。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from autovla.training.performance_tables import (
    PerformanceTable,
    render_markdown_report,
    render_summary_csv,
    stable_json_dumps,
)

SUPPORTED_TABLE_FORMATS = frozenset({"json", "csv", "md"})
SYNTHETIC_BACKEND = "synthetic"
SYNTHETIC_FIXTURE = "tiny"


def _require_positive_int(value: int, *, field: str) -> None:
    """校验正整数并拒绝 bool。"""
    if type(value) is not int:
        raise ValueError(f"{field} must be a positive int")
    if value <= 0:
        raise ValueError(f"{field} must be positive")


def parse_table_formats(value: str) -> tuple[str, ...]:
    """解析逗号分隔输出格式。"""
    formats: list[str] = []
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        if item not in SUPPORTED_TABLE_FORMATS:
            raise ValueError(f"unsupported table format: {item}")
        if item not in formats:
            formats.append(item)
    if not formats:
        raise ValueError("table-format must include at least one format")
    return tuple(formats)


@dataclass(frozen=True, slots=True)
class SyntheticDataloaderBenchmarkConfig:
    """DataLoader synthetic benchmark 配置。"""

    fixture: str
    max_samples: int
    batch_size: int
    output_dir: Path
    table_formats: tuple[str, ...] = ("json", "csv", "md")
    backend: str = SYNTHETIC_BACKEND

    def __post_init__(self) -> None:
        """校验 Stage 3 只允许 tiny synthetic 范围。"""
        if self.backend != SYNTHETIC_BACKEND:
            raise ValueError("backend must be synthetic")
        if self.fixture != SYNTHETIC_FIXTURE:
            raise ValueError("fixture must be tiny for the synthetic scaffold")
        _require_positive_int(self.max_samples, field="max_samples")
        _require_positive_int(self.batch_size, field="batch_size")
        if self.output_dir.exists() and not self.output_dir.is_dir():
            raise ValueError("output_dir must be a directory")
        if not self.table_formats:
            raise ValueError("table_formats must not be empty")
        invalid = [fmt for fmt in self.table_formats if fmt not in SUPPORTED_TABLE_FORMATS]
        if invalid:
            raise ValueError(f"unsupported table format: {invalid[0]}")
        object.__setattr__(self, "output_dir", Path(self.output_dir))

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定配置 payload。"""
        return {
            "backend": self.backend,
            "batch_size": self.batch_size,
            "fixture": self.fixture,
            "max_samples": self.max_samples,
            "output_dir": self.output_dir.as_posix(),
            "table_formats": list(self.table_formats),
        }


@dataclass(frozen=True, slots=True)
class SyntheticDataloaderBenchmarkResult:
    """DataLoader synthetic benchmark 输出索引。"""

    output_dir: Path
    files: Mapping[str, Path]
    tables: Mapping[str, PerformanceTable]
    summary: Mapping[str, object]


def _table_map(tables: tuple[PerformanceTable, ...]) -> Mapping[str, PerformanceTable]:
    """返回只读表索引。"""
    return MappingProxyType({table.name: table for table in tables})


def _synthetic_metrics(config: SyntheticDataloaderBenchmarkConfig) -> dict[str, float | str]:
    """生成确定性 synthetic metrics。"""
    batch_count = max((config.max_samples + config.batch_size - 1) // config.batch_size, 1)
    input_prepare_ms = 0.08
    collate_ms = 0.05
    object_assembly_ms = 0.03
    artifact_write_ms = 0.02
    batch_latency_ms = round(input_prepare_ms + collate_ms + object_assembly_ms, 6)
    total_ms = max(batch_latency_ms * batch_count, 0.001)
    return {
        "artifact_write_ms_p50": artifact_write_ms,
        "batch_latency_ms_max": batch_latency_ms,
        "batch_latency_ms_p50": batch_latency_ms,
        "batch_latency_ms_p95": batch_latency_ms,
        "bytes_read": 0.0,
        "bytes_written": 0.0,
        "collate_ms_p50": collate_ms,
        "file_open_count": 0.0,
        "input_prepare_ms_p50": input_prepare_ms,
        "missing_telemetry": "gpu,cuda,slurm,media_decode,real_dataset",
        "object_assembly_ms_p50": object_assembly_ms,
        "samples_per_second": round(config.max_samples / (total_ms / 1000.0), 6),
    }


def _build_tables(
    config: SyntheticDataloaderBenchmarkConfig,
) -> tuple[PerformanceTable, ...]:
    """构造 Stage 3 必需七张性能表。"""
    metrics = _synthetic_metrics(config)
    batch_count = max((config.max_samples + config.batch_size - 1) // config.batch_size, 1)
    benchmark_matrix = PerformanceTable(
        name="benchmark_matrix",
        title="Benchmark Matrix",
        columns=("scenario", "backend", "fixture", "status"),
        rows=(
            {
                "backend": "synthetic",
                "fixture": "tiny",
                "scenario": "synthetic_metadata_only",
                "status": "PASS",
            },
            {
                "backend": "synthetic",
                "fixture": "tiny",
                "scenario": "synthetic_collate_only",
                "status": "PASS",
            },
            {
                "backend": "synthetic",
                "fixture": "tiny",
                "scenario": "synthetic_adapter_payload_only",
                "status": "PASS",
            },
            {
                "backend": "synthetic",
                "fixture": "tiny",
                "scenario": "synthetic_artifact_write",
                "status": "PASS",
            },
        ),
    )
    throughput_summary = PerformanceTable(
        name="throughput_summary",
        title="Throughput Summary",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {
                "metric": "samples_per_second",
                "status": "PASS",
                "unit": "samples/s",
                "value": metrics["samples_per_second"],
            },
            {
                "metric": "batch_count",
                "status": "PASS",
                "unit": "batch",
                "value": batch_count,
            },
        ),
    )
    stage_latency = PerformanceTable(
        name="stage_latency",
        title="Stage Latency",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {
                "metric": "batch_latency_ms_p50",
                "status": "PASS",
                "unit": "ms",
                "value": metrics["batch_latency_ms_p50"],
            },
            {
                "metric": "batch_latency_ms_p95",
                "status": "PASS",
                "unit": "ms",
                "value": metrics["batch_latency_ms_p95"],
            },
            {
                "metric": "batch_latency_ms_max",
                "status": "PASS",
                "unit": "ms",
                "value": metrics["batch_latency_ms_max"],
            },
            {
                "metric": "input_prepare_ms_p50",
                "status": "PASS",
                "unit": "ms",
                "value": metrics["input_prepare_ms_p50"],
            },
            {
                "metric": "collate_ms_p50",
                "status": "PASS",
                "unit": "ms",
                "value": metrics["collate_ms_p50"],
            },
            {
                "metric": "object_assembly_ms_p50",
                "status": "PASS",
                "unit": "ms",
                "value": metrics["object_assembly_ms_p50"],
            },
            {
                "metric": "artifact_write_ms_p50",
                "status": "PASS",
                "unit": "ms",
                "value": metrics["artifact_write_ms_p50"],
            },
        ),
    )
    data_io = PerformanceTable(
        name="data_io_summary",
        title="Data/IO Summary",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {"metric": "file_open_count", "status": "PASS", "unit": "files", "value": 0},
            {"metric": "bytes_read", "status": "PASS", "unit": "bytes", "value": 0},
            {"metric": "bytes_written", "status": "PASS", "unit": "bytes", "value": 0},
            {"metric": "media_decode", "status": "PASS", "unit": "", "value": "not_used"},
            {"metric": "real_dataset_read", "status": "PASS", "unit": "", "value": "not_used"},
        ),
    )
    regression_gate = PerformanceTable(
        name="regression_gate",
        title="Regression/Gate",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {
                "metric": "synthetic_only_scope",
                "status": "PASS",
                "unit": "",
                "value": "enforced",
            },
            {
                "metric": "no_real_training",
                "status": "PASS",
                "unit": "",
                "value": "enforced",
            },
            {
                "metric": "no_dataset_materialization",
                "status": "PASS",
                "unit": "",
                "value": "enforced",
            },
        ),
    )
    missing = PerformanceTable(
        name="missing_telemetry",
        title="Missing Telemetry",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {
                "metric": "missing_telemetry",
                "status": "SYNTHETIC_ONLY",
                "unit": "",
                "value": metrics["missing_telemetry"],
            },
            {
                "metric": "gpu_utilization",
                "status": "SYNTHETIC_ONLY",
                "unit": "",
                "value": "not_collected",
            },
            {
                "metric": "slurm_job_id",
                "status": "SYNTHETIC_ONLY",
                "unit": "",
                "value": "not_collected",
            },
        ),
    )
    environment = PerformanceTable(
        name="performance_environment",
        title="Environment",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {"metric": "backend", "status": "PASS", "unit": "", "value": "synthetic"},
            {"metric": "fixture", "status": "PASS", "unit": "", "value": "tiny"},
            {"metric": "network", "status": "PASS", "unit": "", "value": "disabled"},
            {"metric": "gpu", "status": "PASS", "unit": "", "value": "not_used"},
            {"metric": "slurm", "status": "PASS", "unit": "", "value": "not_used"},
            {
                "metric": "wandb_hf_endpoint_robot",
                "status": "PASS",
                "unit": "",
                "value": "not_used",
            },
        ),
    )
    return (
        benchmark_matrix,
        throughput_summary,
        stage_latency,
        data_io,
        regression_gate,
        missing,
        environment,
    )


def _payload(
    *,
    config: SyntheticDataloaderBenchmarkConfig,
    tables: tuple[PerformanceTable, ...],
) -> dict[str, object]:
    """构造稳定 JSON payload。"""
    stable_config = config.to_json_dict()
    stable_config["output_dir"] = "<output_dir>"
    return {
        "config": stable_config,
        "schema_version": "autovla.dataloader_perf_tables.v1",
        "summary": {
            "backend": "synthetic",
            "fixture": "tiny",
            "no_real_dataset_read": True,
            "no_real_training": True,
            "table_count": len(tables),
        },
        "tables": [table.to_json_dict() for table in tables],
    }


def _render_markdown(
    *,
    tables: tuple[PerformanceTable, ...],
) -> str:
    """渲染含安全边界的 Markdown 报告。"""
    body = render_markdown_report(tables)
    boundary = "\n".join(
        (
            "## Safety Boundary",
            "",
            "- No real dataset read.",
            "- No media decode.",
            "- No full dataset conversion.",
            "- No real training.",
            "- No GPU, Slurm, W&B, Hugging Face, endpoint, or robot action.",
            "",
        )
    )
    return body + "\n" + boundary


def run_synthetic_dataloader_benchmark(
    config: SyntheticDataloaderBenchmarkConfig,
) -> SyntheticDataloaderBenchmarkResult:
    """运行 login-node-safe synthetic DataLoader 性能表 scaffold。"""
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = _build_tables(config)
    files: dict[str, Path] = {}
    if "json" in config.table_formats:
        json_path = output_dir / "dataloader_performance_tables.json"
        json_path.write_text(
            stable_json_dumps(_payload(config=config, tables=tables)),
            encoding="utf-8",
        )
        files["json"] = json_path
    if "csv" in config.table_formats:
        csv_path = output_dir / "dataloader_performance_tables.csv"
        csv_path.write_text(render_summary_csv(tables), encoding="utf-8")
        files["csv"] = csv_path
    if "md" in config.table_formats:
        md_path = output_dir / "dataloader_performance_tables.md"
        md_path.write_text(_render_markdown(tables=tables), encoding="utf-8")
        files["md"] = md_path
    return SyntheticDataloaderBenchmarkResult(
        output_dir=output_dir,
        files=MappingProxyType(files),
        tables=_table_map(tables),
        summary=MappingProxyType(
            {
                "backend": "synthetic",
                "fixture": "tiny",
                "max_samples": config.max_samples,
                "table_count": len(tables),
            }
        ),
    )
