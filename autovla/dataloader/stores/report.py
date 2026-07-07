"""load benchmark JSON/CSV/Markdown writer。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from autovla.dataloader.stores.common import DEFAULT_TABLE_VERSION, write_csv, write_json
from autovla.dataloader.stores.sample_window_manifest import SampleWindowManifest

JSON_REPORT_NAME = "load-benchmark.json"
CSV_REPORT_NAME = "load-benchmark.csv"
MARKDOWN_REPORT_NAME = "load-benchmark.md"


def write_benchmark_tables(
    *,
    output_dir: Path,
    rows: Sequence[Mapping[str, object]],
    manifest: SampleWindowManifest,
) -> tuple[Path, Path, Path]:
    """写出 JSON、CSV、Markdown 三种表。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / JSON_REPORT_NAME
    csv_path = output_dir / CSV_REPORT_NAME
    markdown_path = output_dir / MARKDOWN_REPORT_NAME

    write_json(
        json_path,
        {
            "manifest": manifest.to_json_dict(),
            "rows": list(rows),
            "schema_version": DEFAULT_TABLE_VERSION,
        },
    )
    write_csv(
        csv_path,
        [_flatten_row(row) for row in rows],
        (
            "candidate_id",
            "status",
            "prototype_only",
            "reason",
            "episode_count",
            "sample_count",
            "batch_size",
            "measured_batches",
            "build_time_ms",
            "p50_ms",
            "p95_ms",
            "samples_per_second",
            "artifact_size_bytes",
            "artifact_file_count",
            "candidate_root",
            "manifest_checksum",
        ),
    )
    markdown_path.write_text(render_markdown(rows=rows, manifest=manifest), encoding="utf-8")
    return json_path, csv_path, markdown_path


def render_markdown(
    *,
    rows: Sequence[Mapping[str, object]],
    manifest: SampleWindowManifest,
) -> str:
    """渲染 Markdown 表。"""
    lines = [
        "# AutoVLA Multiformat Datastore GPU200 Bakeoff",
        "",
        f"- Manifest checksum: `{manifest.checksum}`",
        f"- Selected samples: `{manifest.sample_count}`",
        f"- Selected episodes: `{manifest.episode_count}`",
        "",
        "| Candidate | Status | Prototype | Episodes | Samples | Batch | Measured | Build ms | "
        "p50 ms | p95 ms | Samples/s | Artifact bytes | Files | Reason |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
        " ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        flat = _flatten_row(row)
        lines.append(
            "| "
            f"`{flat['candidate_id']}` | `{flat['status']}` | `{flat['prototype_only']}` | "
            f"{flat['episode_count']} | {flat['sample_count']} | {flat['batch_size']} | "
            f"{flat['measured_batches']} | {flat['build_time_ms']} | {flat['p50_ms']} | "
            f"{flat['p95_ms']} | {flat['samples_per_second']} | {flat['artifact_size_bytes']} | "
            f"{flat['artifact_file_count']} | {flat['reason']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _flatten_row(row: Mapping[str, object]) -> dict[str, object]:
    """把嵌套 benchmark 字段铺平成表行。"""
    benchmark = json.loads(json.dumps(row.get("benchmark", {})))
    return {
        "artifact_file_count": row.get("artifact_file_count", "not_run"),
        "artifact_size_bytes": row.get("artifact_size_bytes", "not_run"),
        "batch_size": benchmark.get("batch_size", "not_run"),
        "build_time_ms": benchmark.get("build_time_ms", "not_run"),
        "candidate_root": row.get("candidate_root", "missing"),
        "candidate_id": row.get("candidate_id", "missing"),
        "episode_count": row.get("episode_count", "not_run"),
        "manifest_checksum": row.get("manifest_checksum", "missing"),
        "measured_batches": row.get("measured_batches", "not_run"),
        "p50_ms": benchmark.get("p50_ms", "not_run"),
        "p95_ms": benchmark.get("p95_ms", "not_run"),
        "prototype_only": row.get("prototype_only", False),
        "reason": row.get("reason", ""),
        "sample_count": benchmark.get("sample_count", "not_run"),
        "samples_per_second": benchmark.get("samples_per_second", "not_run"),
        "status": row.get("status", "missing"),
    }
