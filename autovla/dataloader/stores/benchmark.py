"""多格式 datastore load-benchmark scaffold。"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from autovla.dataloader.stores.artifact_ledger import (
    ArtifactLedgerEntry,
    summarize_artifact,
    write_artifact_ledger,
)
from autovla.dataloader.stores.common import (
    BenchmarkStats,
    MultiformatDatastoreConfig,
    SourceSample,
    load_source_samples,
    measure_reader,
    write_json,
)
from autovla.dataloader.stores.lerobot_compat import build_raw_isaac_candidate_root
from autovla.dataloader.stores.lerobot_v3_builder import build_lerobot_v3_local_candidate
from autovla.dataloader.stores.lerobot_v3_reader import read_lerobot_v3_local_batches
from autovla.dataloader.stores.lerobot_v21_reader import read_raw_batches
from autovla.dataloader.stores.report import write_benchmark_tables
from autovla.dataloader.stores.robodm_builder import build_robodm_container_candidate
from autovla.dataloader.stores.robodm_reader import read_robodm_batches
from autovla.dataloader.stores.sample_window_manifest import (
    SampleWindowManifest,
    build_sample_window_manifest_from_samples,
)
from autovla.dataloader.stores.webdataset_builder import build_webdataset_tar_candidate
from autovla.dataloader.stores.webdataset_reader import read_webdataset_batches


@dataclass(frozen=True, slots=True)
class MultiformatDatastoreResult:
    """保存本地 bakeoff scaffold 产物。"""

    manifest: SampleWindowManifest
    manifest_path: Path
    rows: tuple[dict[str, object], ...]
    json_path: Path
    csv_path: Path
    markdown_path: Path
    ledger_path: Path


def run_multiformat_datastore_bakeoff(
    config: MultiformatDatastoreConfig,
) -> MultiformatDatastoreResult:
    """执行 compute-runnable data-store 构建与 load benchmark。"""
    samples = load_source_samples(config)
    manifest = build_sample_window_manifest_from_samples(config, samples)
    manifest_path = _write_shared_manifest(config, manifest)
    rows: list[dict[str, object]] = []
    artifact_entries: list[ArtifactLedgerEntry] = []

    raw_root = config.output_dir / "zjh_lerobot_v21_raw"
    build_raw_isaac_candidate_root(
        root=raw_root,
        source_dataset=config.source_dataset,
        samples=samples,
    )
    raw_stats = _benchmark_raw_candidate(config=config, samples=samples)
    raw_row = _candidate_row(
        candidate_id="zjh_lerobot_v21_raw",
        status="PASS",
        prototype_only=False,
        reason="read-only raw baseline",
        source_mode="read_only_raw_source",
        manifest=manifest,
        benchmark=raw_stats,
    )
    write_json(raw_root / "candidate_manifest.json", raw_row)
    rows.append(raw_row)
    raw_artifact = summarize_artifact(
        "zjh_lerobot_v21_raw",
        raw_root,
        created_by="autovla.dataloader.stores.benchmark",
    )
    _enrich_row_with_artifact(
        raw_row,
        artifact=raw_artifact,
        manifest=manifest,
        measured_batches=config.measured_batches,
    )
    artifact_entries.append(raw_artifact)

    v3_root = config.working_root / "zjh_lerobot_v3_local"
    v3_build_started = time.perf_counter()
    build_lerobot_v3_local_candidate(
        v3_root,
        source_dataset=config.source_dataset,
        samples=samples,
    )

    def _v3_reader(indices: Sequence[int]) -> list[dict[str, object]]:
        return read_lerobot_v3_local_batches(v3_root, indices)

    v3_stats = measure_reader(
        sample_count=len(samples),
        batch_size=config.batch_size,
        measured_batches=config.measured_batches,
        reader=_v3_reader,
    )
    v3_stats = _with_build_time(
        v3_stats,
        build_time_ms=(time.perf_counter() - v3_build_started) * 1000.0,
    )
    v3_row = _candidate_row(
        candidate_id="zjh_lerobot_v3_local",
        status="PASS",
        prototype_only=False,
        reason="AutoVLA-native local LeRobot v3-style artifact and reader",
        source_mode="lerobot_v3_local_artifact",
        manifest=manifest,
        benchmark=v3_stats,
    )
    rows.append(v3_row)
    v3_artifact = summarize_artifact(
        "zjh_lerobot_v3_local",
        v3_root,
        created_by="autovla.dataloader.stores.benchmark",
    )
    _enrich_row_with_artifact(
        v3_row,
        artifact=v3_artifact,
        manifest=manifest,
        measured_batches=config.measured_batches,
    )
    artifact_entries.append(v3_artifact)

    webdataset_root = config.working_root / "zjh_webdataset_tar"
    webdataset_root.mkdir(parents=True, exist_ok=True)
    wds_build_started = time.perf_counter()
    build_webdataset_tar_candidate(
        webdataset_root,
        samples,
        samples_per_shard=config.samples_per_shard,
    )

    def _webdataset_reader(indices: Sequence[int]) -> list[dict[str, object]]:
        return read_webdataset_batches(webdataset_root, indices)

    wds_stats = measure_reader(
        sample_count=len(samples),
        batch_size=config.batch_size,
        measured_batches=config.measured_batches,
        reader=_webdataset_reader,
    )
    wds_stats = _with_build_time(
        wds_stats,
        build_time_ms=(time.perf_counter() - wds_build_started) * 1000.0,
    )
    wds_row = _candidate_row(
        candidate_id="zjh_webdataset_tar",
        status="PASS",
        prototype_only=False,
        reason="webdataset tar shards built and read through approved package route",
        source_mode="webdataset_tar_artifact",
        manifest=manifest,
        benchmark=wds_stats,
    )
    rows.append(wds_row)
    wds_artifact = summarize_artifact(
        "zjh_webdataset_tar",
        webdataset_root,
        created_by="autovla.dataloader.stores.benchmark",
    )
    _enrich_row_with_artifact(
        wds_row,
        artifact=wds_artifact,
        manifest=manifest,
        measured_batches=config.measured_batches,
    )
    artifact_entries.append(wds_artifact)

    robodm_root = config.working_root / "zjh_robodm_container_v1"
    robodm_root.mkdir(parents=True, exist_ok=True)
    robo_build_started = time.perf_counter()
    build_robodm_container_candidate(
        robodm_root,
        samples,
        samples_per_container=config.samples_per_shard,
    )

    def _robodm_reader(indices: Sequence[int]) -> list[dict[str, object]]:
        return read_robodm_batches(robodm_root, indices)

    robo_stats = measure_reader(
        sample_count=len(samples),
        batch_size=config.batch_size,
        measured_batches=config.measured_batches,
        reader=_robodm_reader,
    )
    robo_stats = _with_build_time(
        robo_stats,
        build_time_ms=(time.perf_counter() - robo_build_started) * 1000.0,
    )
    robo_row = _candidate_row(
        candidate_id="zjh_robodm_container_v1",
        status="PASS",
        prototype_only=True,
        reason="AutoVLA-owned RoboDM-style prototype container",
        source_mode="robodm_style_container_artifact",
        manifest=manifest,
        benchmark=robo_stats,
    )
    rows.append(robo_row)
    robo_artifact = summarize_artifact(
        "zjh_robodm_container_v1",
        robodm_root,
        created_by="autovla.dataloader.stores.benchmark",
    )
    _enrich_row_with_artifact(
        robo_row,
        artifact=robo_artifact,
        manifest=manifest,
        measured_batches=config.measured_batches,
    )
    artifact_entries.append(robo_artifact)

    json_path, csv_path, markdown_path = write_benchmark_tables(
        output_dir=config.output_dir,
        rows=rows,
        manifest=manifest,
    )
    ledger_path = write_artifact_ledger(
        entries=artifact_entries,
        path=config.output_dir / "generated-artifact-ledger.json",
    )
    return MultiformatDatastoreResult(
        manifest=manifest,
        manifest_path=manifest_path,
        rows=tuple(rows),
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
        ledger_path=ledger_path,
    )


def _benchmark_raw_candidate(
    *,
    config: MultiformatDatastoreConfig,
    samples: list[SourceSample],
) -> BenchmarkStats:
    """执行 raw baseline 读取 benchmark。"""

    def _raw_reader(indices: Sequence[int]) -> list[dict[str, object]]:
        return read_raw_batches(samples, indices)

    return measure_reader(
        sample_count=len(samples),
        batch_size=config.batch_size,
        measured_batches=config.measured_batches,
        reader=_raw_reader,
    )


def _candidate_row(
    *,
    candidate_id: str,
    status: str,
    prototype_only: bool,
    reason: str,
    source_mode: str,
    manifest: SampleWindowManifest,
    benchmark: BenchmarkStats,
) -> dict[str, object]:
    """构造统一候选行。"""
    return {
        "action_mask_present": True,
        "benchmark": benchmark.to_json_dict(),
        "camera_views": list(manifest.camera_views),
        "candidate_id": candidate_id,
        "language_present": True,
        "prototype_only": prototype_only,
        "reason": reason,
        "sample_ids": list(manifest.selected_sample_ids),
        "source_mode": source_mode,
        "state_present": True,
        "status": status,
        "window_ids": list(manifest.selected_window_ids),
    }


def _write_shared_manifest(
    config: MultiformatDatastoreConfig,
    manifest: SampleWindowManifest,
) -> Path:
    """把共享公平性 manifest 落到 compute-runnable 约定路径。"""
    manifest_path = (
        config.working_root / "multiformat_bakeoff" / "multiformat_sample_window_manifest.json"
    )
    write_json(manifest_path, manifest.to_json_dict())
    return manifest_path


def _enrich_row_with_artifact(
    row: dict[str, object],
    *,
    artifact: ArtifactLedgerEntry,
    manifest: SampleWindowManifest,
    measured_batches: int,
) -> None:
    """回填 compute-runnable 行的附加字段。"""
    row["artifact_file_count"] = artifact.file_count
    row["artifact_size_bytes"] = artifact.size_bytes
    row["candidate_root"] = artifact.path
    row["episode_count"] = manifest.episode_count
    row["manifest_checksum"] = manifest.checksum
    row["measured_batches"] = measured_batches


def _with_build_time(stats: BenchmarkStats, *, build_time_ms: float) -> BenchmarkStats:
    """回填 build_time_ms。"""
    return BenchmarkStats(
        sample_count=stats.sample_count,
        batch_size=stats.batch_size,
        build_time_ms=build_time_ms,
        p50_ms=stats.p50_ms,
        p95_ms=stats.p95_ms,
        samples_per_second=stats.samples_per_second,
    )
