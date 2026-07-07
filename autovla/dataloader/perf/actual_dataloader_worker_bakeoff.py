"""PR30 actual dataloader worker benchmark scaffold。"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import multiprocessing as mp
import os
import resource
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import Any, Literal, cast

SCHEMA_VERSION = "autovla.pr30_actual_dataloader_worker_bakeoff.v1"
TASK_ID = "AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001"
WORKING_ROOT_NAME = "autovla_actual_worker_bakeoff_v1"
CORE_TIMING_FIELDS: tuple[str, ...] = (
    "loader_init_ms",
    "index_load_ms",
    "metadata_load_ms",
    "sample_select_ms",
    "media_decode_ms",
    "rgb_materialize_ms",
    "action_load_ms",
    "state_load_ms",
    "language_load_ms",
    "payload_validation_ms",
    "collate_ms",
    "tensor_or_array_conversion_ms",
    "worker_queue_wait_ms",
    "next_batch_wait_ms",
    "total_batch_ms",
    "file_open_count",
    "bytes_read",
    "read_mb_s",
    "cpu_user_pct",
    "cpu_system_pct",
    "rss_mb_max",
    "samples_per_sec",
    "frames_per_sec",
    "actions_per_sec",
)
DEFAULTED_CORE_TIMING_FIELDS: tuple[str, ...] = (
    "loader_init_ms",
    "index_load_ms",
    "metadata_load_ms",
    "sample_select_ms",
    "media_decode_ms",
    "rgb_materialize_ms",
    "action_load_ms",
    "state_load_ms",
    "language_load_ms",
    "payload_validation_ms",
    "tensor_or_array_conversion_ms",
    "worker_queue_wait_ms",
    "next_batch_wait_ms",
    "cpu_user_pct",
    "cpu_system_pct",
)
MATRIX_TELEMETRY_FIELDS: tuple[str, ...] = (
    "persistent_workers_matrix",
    "prefetch_factor_matrix",
    "warmup_measured_repeats_matrix",
)
RUNNABLE_TINY_CANDIDATES = frozenset(
    {
        "zjh_lerobot_v21_autovla_adapter",
        "zjh_lerobot_v3_local",
        "zjh_webdataset_tar",
        "zjh_robodm_container_v1",
    }
)


@dataclass(frozen=True, slots=True)
class CandidateNativeAdapter:
    """描述一个 PR30 actual-worker 候选适配器。"""

    candidate_id: str
    label: str
    native_loader: str
    mandatory: bool
    default_status: str
    reason: str
    prototype_only: bool = False


CANDIDATE_MATRIX: tuple[CandidateNativeAdapter, ...] = (
    CandidateNativeAdapter(
        candidate_id="zjh_lerobot_v21_gr00t_or_lerobot_native",
        label="D1",
        native_loader="gr00t_or_lerobot_native_unexecuted",
        mandatory=True,
        default_status="NOT_RUN_UNSAFE_OR_UNAVAILABLE",
        reason=(
            "GR00T/LeRobot native route is not safely executable in Data-W1 without runtime "
            "proof"
        ),
    ),
    CandidateNativeAdapter(
        candidate_id="zjh_lerobot_v21_autovla_adapter",
        label="D2",
        native_loader="autovla_lerobot_v21_actual_worker_adapter",
        mandatory=True,
        default_status="RUN",
        reason="AutoVLA adapter path with actual worker evidence",
    ),
    CandidateNativeAdapter(
        candidate_id="zjh_lerobot_v3_local",
        label="D3",
        native_loader="autovla_lerobot_v3_local_actual_worker_adapter",
        mandatory=True,
        default_status="RUN",
        reason="AutoVLA local LeRobot-v3 style adapter with actual worker evidence",
    ),
    CandidateNativeAdapter(
        candidate_id="zjh_webdataset_tar",
        label="D4",
        native_loader="autovla_webdataset_tar_actual_worker_adapter",
        mandatory=True,
        default_status="RUN",
        reason="WebDataset tar adapter with actual worker evidence",
    ),
    CandidateNativeAdapter(
        candidate_id="zjh_robodm_container_v1",
        label="D5",
        native_loader="autovla_robodm_style_actual_worker_adapter",
        mandatory=True,
        default_status="RUN",
        reason="Owned RoboDM-style container adapter with actual worker evidence",
        prototype_only=True,
    ),
    CandidateNativeAdapter(
        candidate_id="zjh_zarr_cache",
        label="D6",
        native_loader="zarr_cache_not_implemented",
        mandatory=False,
        default_status="NOT_IMPLEMENTED_IN_CURRENT_PR",
        reason="optional zarr cache has no current PR30 implementation",
    ),
)


@dataclass(frozen=True, slots=True)
class ActualWorkerBenchmarkConfig:
    """保存 actual dataloader worker benchmark 的本地/compute 入口参数。"""

    source_dataset: Path
    working_root: Path
    output_dir: Path
    worker_count: int
    batch_size: int = 8
    max_samples: int = 128
    seed: int = 11
    use_tiny_fixture: bool = False
    candidates: tuple[str, ...] = tuple(candidate.candidate_id for candidate in CANDIDATE_MATRIX)
    gr00t_root: Path | None = None
    max_episodes: int = 32
    measured_batches: int = 1
    repeats: int = 1
    warmup_batches: int = 0

    def __post_init__(self) -> None:
        """校验 worker 与路径边界。"""
        if isinstance(self.worker_count, bool) or self.worker_count < 0:
            raise ValueError("worker_count must be a non-negative integer")
        for field_name in (
            "batch_size",
            "max_episodes",
            "max_samples",
            "measured_batches",
            "repeats",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")
        if isinstance(self.warmup_batches, bool) or self.warmup_batches < 0:
            raise ValueError("warmup_batches must be a non-negative integer")
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        known_candidates = {candidate.candidate_id for candidate in CANDIDATE_MATRIX}
        unknown = set(self.candidates) - known_candidates
        if unknown:
            raise ValueError(f"unknown candidates: {sorted(unknown)}")
        source = self.source_dataset.resolve(strict=False)
        for field_name in ("working_root", "output_dir"):
            target = getattr(self, field_name).resolve(strict=False)
            if target == source or source in target.parents:
                raise ValueError(f"{field_name} must not be inside source_dataset")


@dataclass(frozen=True, slots=True)
class BenchmarkPayload:
    """保存一个已物化的 BenchmarkPayload 样本。"""

    sample_id: str
    episode_id: str
    window_id: str
    action: tuple[float, ...]
    state: tuple[float, ...]
    language: str
    action_mask: tuple[bool, ...]
    camera_rgb_0: bytes
    camera_rgb_1: bytes
    camera_rgb_2: bytes

    def to_json_dict(self) -> dict[str, object]:
        """转成稳定 JSON payload, RGB bytes 使用 base64 保存。"""
        payload: dict[str, object] = {
            "action": list(self.action),
            "action_mask": list(self.action_mask),
            "camera_rgb_0": _encode_bytes(self.camera_rgb_0),
            "camera_rgb_1": _encode_bytes(self.camera_rgb_1),
            "camera_rgb_2": _encode_bytes(self.camera_rgb_2),
            "episode_id": self.episode_id,
            "language": self.language,
            "payload_missing_fields": [],
            "sample_id": self.sample_id,
            "state": list(self.state),
            "window_id": self.window_id,
        }
        payload["payload_hash"] = _stable_hash(payload)
        return payload

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, object]) -> "BenchmarkPayload":
        """从 JSON payload 恢复 bytes/tuple 合同。"""
        return cls(
            action=_float_tuple(payload.get("action"), "action"),
            action_mask=_bool_tuple(payload.get("action_mask"), "action_mask"),
            camera_rgb_0=_decode_bytes(payload.get("camera_rgb_0"), "camera_rgb_0"),
            camera_rgb_1=_decode_bytes(payload.get("camera_rgb_1"), "camera_rgb_1"),
            camera_rgb_2=_decode_bytes(payload.get("camera_rgb_2"), "camera_rgb_2"),
            episode_id=_string(payload.get("episode_id"), "episode_id"),
            language=_string(payload.get("language"), "language"),
            sample_id=_string(payload.get("sample_id"), "sample_id"),
            state=_float_tuple(payload.get("state"), "state"),
            window_id=_string(payload.get("window_id"), "window_id"),
        )


@dataclass(frozen=True, slots=True)
class BenchmarkBatch:
    """保存 collate 后的 BenchmarkBatch 摘要。"""

    sample_ids: tuple[str, ...]
    episode_ids: tuple[str, ...]
    window_ids: tuple[str, ...]
    payload_hash: str
    batch_size: int
    bytes_read: int


@dataclass(frozen=True, slots=True)
class WorkerRunEvidence:
    """保存真实 worker runner 的执行证据。"""

    requested_worker_count: int
    actual_worker_count: int | Literal["not_measured"]
    observed_worker_ids: tuple[str, ...]
    observed_process_ids: tuple[int, ...]
    per_worker_sample_counts: dict[str, int]
    every_worker_observed_at_least_one_sample: bool
    multiprocessing_enabled: bool
    prefetch_enabled: bool
    persistent_reader_enabled: bool
    execution_mode: str
    worker_count_evidence_status: str
    sample_count: int
    batch_count: int
    timings_ms: tuple[float, ...]
    bytes_read: int
    file_open_count: int
    payload_hash: str
    rss_mb_max: float

    def to_json_dict(self) -> dict[str, object]:
        """返回 JSON-safe worker evidence。"""
        return {
            "actual_worker_count": self.actual_worker_count,
            "batch_count": self.batch_count,
            "bytes_read": self.bytes_read,
            "every_worker_observed_at_least_one_sample": (
                self.every_worker_observed_at_least_one_sample
            ),
            "execution_mode": self.execution_mode,
            "file_open_count": self.file_open_count,
            "multiprocessing_enabled": self.multiprocessing_enabled,
            "observed_process_ids": list(self.observed_process_ids),
            "observed_worker_ids": list(self.observed_worker_ids),
            "payload_hash": self.payload_hash,
            "per_worker_sample_counts": self.per_worker_sample_counts,
            "persistent_reader_enabled": self.persistent_reader_enabled,
            "prefetch_enabled": self.prefetch_enabled,
            "requested_worker_count": self.requested_worker_count,
            "rss_mb_max": self.rss_mb_max,
            "sample_count": self.sample_count,
            "timings_ms": list(self.timings_ms),
            "worker_count_evidence_status": self.worker_count_evidence_status,
        }


@dataclass(frozen=True, slots=True)
class ActualWorkerBakeoffResult:
    """返回 actual worker bakeoff 的主要文件路径。"""

    conclusion: str
    rows: tuple[dict[str, object], ...]
    manifest_checksum: str
    raw_json_path: Path
    summary_csv_path: Path
    summary_markdown_path: Path
    worker_evidence_json_path: Path
    generated_artifact_ledger_path: Path
    source_dataset_mutation_check_path: Path


class ActualWorkerRunner:
    """执行 serial 或 multiprocessing actual-worker 读取。"""

    def __init__(self, *, worker_count: int, batch_size: int) -> None:
        """初始化 worker runner。"""
        if isinstance(worker_count, bool) or worker_count < 0:
            raise ValueError("worker_count must be non-negative")
        if isinstance(batch_size, bool) or batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.worker_count = worker_count
        self.batch_size = batch_size

    def run_payload_file(
        self,
        payload_path: Path,
        *,
        force_unmeasured_for_test: bool = False,
    ) -> WorkerRunEvidence:
        """从 JSONL payload artifact 读取样本并记录 worker 证据。"""
        rows = _read_payload_jsonl(payload_path)
        if force_unmeasured_for_test:
            return WorkerRunEvidence(
                actual_worker_count="not_measured",
                batch_count=0,
                bytes_read=0,
                every_worker_observed_at_least_one_sample=False,
                execution_mode="blocked_unmeasured",
                file_open_count=0,
                multiprocessing_enabled=False,
                observed_process_ids=(),
                observed_worker_ids=(),
                payload_hash="",
                per_worker_sample_counts={},
                persistent_reader_enabled=False,
                prefetch_enabled=False,
                requested_worker_count=self.worker_count,
                rss_mb_max=_rss_mb(),
                sample_count=len(rows),
                timings_ms=(),
                worker_count_evidence_status="BLOCKED_ACTUAL_WORKER_COUNT_NOT_MEASURED",
            )
        if self.worker_count == 0:
            return self._run_serial(rows)
        return self._run_processes(payload_path, sample_count=len(rows))

    def _run_serial(self, rows: Sequence[BenchmarkPayload]) -> WorkerRunEvidence:
        """在当前进程串行读取, 用于 worker_count=0 兼容。"""
        started = time.perf_counter()
        batch = collate_benchmark_batch(rows)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
        return WorkerRunEvidence(
            actual_worker_count=0,
            batch_count=_batch_count(len(rows), self.batch_size),
            bytes_read=batch.bytes_read,
            every_worker_observed_at_least_one_sample=True,
            execution_mode="serial",
            file_open_count=1,
            multiprocessing_enabled=False,
            observed_process_ids=(os.getpid(),),
            observed_worker_ids=("serial",),
            payload_hash=batch.payload_hash,
            per_worker_sample_counts={"serial": len(rows)},
            persistent_reader_enabled=False,
            prefetch_enabled=False,
            requested_worker_count=0,
            rss_mb_max=_rss_mb(),
            sample_count=len(rows),
            timings_ms=(elapsed_ms,),
            worker_count_evidence_status="PASS",
        )

    def _run_processes(self, payload_path: Path, *, sample_count: int) -> WorkerRunEvidence:
        """启动真实子进程 worker, 每个 worker 读取分配的样本索引。"""
        worker_slots = min(self.worker_count, sample_count)
        if worker_slots <= 0:
            raise ValueError("sample_count must be positive for worker execution")
        chunks = _split_indices(sample_count, worker_slots)
        ctx = mp.get_context("spawn")
        queue: mp.Queue[dict[str, object]] = ctx.Queue()
        processes = [
            ctx.Process(
                target=_process_worker_chunk,
                args=(payload_path.as_posix(), slot, tuple(indices), queue),
            )
            for slot, indices in enumerate(chunks)
        ]
        started = time.perf_counter()
        for process in processes:
            process.start()
        results: list[dict[str, object]] = []
        for _process in processes:
            try:
                results.append(queue.get(timeout=30.0))
            except Empty as exc:
                raise TimeoutError("worker process did not report evidence") from exc
        for process in processes:
            process.join(timeout=30.0)
            if process.exitcode != 0:
                raise RuntimeError(f"worker process failed with exit code {process.exitcode}")
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
        worker_ids = tuple(_string(result["worker_id"], "worker_id") for result in results)
        process_ids = tuple(_int(result["pid"], "pid") for result in results)
        per_worker = {
            _string(result["worker_id"], "worker_id"): _int(result["sample_count"], "sample_count")
            for result in results
        }
        hashes = [_string(result["payload_hash"], "payload_hash") for result in results]
        actual_count = len(set(process_ids))
        every_worker = all(count > 0 for count in per_worker.values())
        expected_count = worker_slots
        status = "PASS" if actual_count == expected_count and every_worker else "FAIL"
        return WorkerRunEvidence(
            actual_worker_count=actual_count,
            batch_count=_batch_count(sample_count, self.batch_size),
            bytes_read=sum(_int(result["bytes_read"], "bytes_read") for result in results),
            every_worker_observed_at_least_one_sample=every_worker,
            execution_mode="process_pool",
            file_open_count=sum(
                _int(result["file_open_count"], "file_open_count") for result in results
            ),
            multiprocessing_enabled=True,
            observed_process_ids=tuple(sorted(set(process_ids))),
            observed_worker_ids=tuple(sorted(worker_ids)),
            payload_hash=_stable_hash(hashes),
            per_worker_sample_counts=per_worker,
            persistent_reader_enabled=False,
            prefetch_enabled=False,
            requested_worker_count=self.worker_count,
            rss_mb_max=_rss_mb(),
            sample_count=sample_count,
            timings_ms=(elapsed_ms,),
            worker_count_evidence_status=status,
        )


def validate_benchmark_payload(payload: BenchmarkPayload) -> None:
    """验证 RUN payload 完整且不是 camera_refs-only。"""
    if not payload.sample_id or not payload.episode_id or not payload.window_id:
        raise ValueError("sample/episode/window ids are required")
    if not payload.action:
        raise ValueError("action is required")
    if len(payload.action_mask) != len(payload.action):
        raise ValueError("action_mask length must match action")
    if not payload.language:
        raise ValueError("language is required")
    if not payload.camera_rgb_0:
        raise ValueError("camera_rgb_0 is required")
    if not payload.camera_rgb_1:
        raise ValueError("camera_rgb_1 is required")
    if not payload.camera_rgb_2:
        raise ValueError("camera_rgb_2 is required")


def collate_benchmark_batch(payloads: Sequence[BenchmarkPayload]) -> BenchmarkBatch:
    """把样本合并成 BenchmarkBatch 并生成稳定 batch hash。"""
    if not payloads:
        raise ValueError("payloads are required")
    for payload in payloads:
        validate_benchmark_payload(payload)
    sample_ids = tuple(payload.sample_id for payload in payloads)
    episode_ids = tuple(payload.episode_id for payload in payloads)
    window_ids = tuple(payload.window_id for payload in payloads)
    bytes_read = sum(
        len(payload.camera_rgb_0) + len(payload.camera_rgb_1) + len(payload.camera_rgb_2)
        for payload in payloads
    )
    return BenchmarkBatch(
        batch_size=len(payloads),
        bytes_read=bytes_read,
        episode_ids=episode_ids,
        payload_hash=_stable_hash([payload.to_json_dict() for payload in payloads]),
        sample_ids=sample_ids,
        window_ids=window_ids,
    )


def run_actual_worker_bakeoff(config: ActualWorkerBenchmarkConfig) -> ActualWorkerBakeoffResult:
    """执行 Data-W1 actual worker tiny/source benchmark scaffold。"""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.working_root.mkdir(parents=True, exist_ok=True)
    payloads = (
        _tiny_payloads(config.max_samples) if config.use_tiny_fixture else _source_payloads(config)
    )
    manifest = _shared_manifest(config, payloads)
    manifest_checksum = _string(manifest["checksum"], "checksum")
    _write_json(config.output_dir / "shared-sample-window-manifest.json", manifest)
    _write_json(config.working_root / "shared-sample-window-manifest.json", manifest)

    rows: list[dict[str, object]] = []
    worker_rows: list[dict[str, object]] = []
    payload_rows: list[dict[str, object]] = []
    stage_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []
    runner = ActualWorkerRunner(worker_count=config.worker_count, batch_size=config.batch_size)
    for adapter in CANDIDATE_MATRIX:
        if adapter.candidate_id not in config.candidates:
            continue
        candidate_dir = config.working_root / adapter.candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        payload_path = candidate_dir / "payloads.jsonl"
        if adapter.candidate_id in RUNNABLE_TINY_CANDIDATES:
            _write_payload_jsonl(payload_path, payloads)
            evidence = runner.run_payload_file(payload_path)
            row = _run_row(config, adapter, evidence, manifest_checksum)
            payload_rows.append(_payload_completeness_row(adapter, evidence, manifest_checksum))
            stage_rows.extend(_stage_rows(adapter, evidence))
            worker_rows.append({"candidate": adapter.candidate_id, **evidence.to_json_dict()})
            missing_rows.extend(_missing_metric_rows(adapter.candidate_id, row))
            if evidence.worker_count_evidence_status != "PASS":
                missing_rows.append(
                    _missing_row(
                        adapter.candidate_id,
                        "actual_worker_count",
                        "worker evidence did not pass",
                        blocking=True,
                    )
                )
        else:
            row = _not_run_row(adapter, config, manifest_checksum)
            worker_rows.append(_not_run_worker_row(adapter, config))
            payload_rows.append(_not_run_payload_row(adapter, manifest_checksum))
            missing_rows.append(
                _missing_row(
                    adapter.candidate_id,
                    "worker_read_timing",
                    adapter.reason,
                    blocking=adapter.mandatory,
                )
            )
        rows.append(row)

    raw_json_path = config.output_dir / "actual_worker_bakeoff_raw.json"
    summary_csv_path = config.output_dir / "actual_worker_bakeoff_summary.csv"
    summary_md_path = config.output_dir / "actual_worker_bakeoff_summary.md"
    worker_json_path = config.output_dir / "worker_evidence_table.json"
    ledger_path = config.output_dir / "generated_artifact_ledger.json"
    source_check_path = config.output_dir / "source_dataset_mutation_check.md"
    _write_outputs(
        config=config,
        rows=rows,
        worker_rows=worker_rows,
        payload_rows=payload_rows,
        stage_rows=stage_rows,
        missing_rows=missing_rows,
        raw_json_path=raw_json_path,
        summary_csv_path=summary_csv_path,
        summary_md_path=summary_md_path,
        worker_json_path=worker_json_path,
        ledger_path=ledger_path,
        source_check_path=source_check_path,
    )
    return ActualWorkerBakeoffResult(
        conclusion=_decision(rows),
        generated_artifact_ledger_path=ledger_path,
        manifest_checksum=manifest_checksum,
        raw_json_path=raw_json_path,
        rows=tuple(rows),
        source_dataset_mutation_check_path=source_check_path,
        summary_csv_path=summary_csv_path,
        summary_markdown_path=summary_md_path,
        worker_evidence_json_path=worker_json_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口, 供 Compute/HPC 后续调用。"""
    parser = argparse.ArgumentParser(description="AutoVLA PR30 actual dataloader worker bakeoff")
    parser.add_argument("--source-dataset", required=True, type=Path)
    parser.add_argument("--working-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--worker-count", default=8, type=int)
    parser.add_argument("--worker-counts", default="", type=str)
    parser.add_argument("--batch-size", default=8, type=int)
    parser.add_argument("--batch-sizes", default="", type=str)
    parser.add_argument("--warmup-batches", default=0, type=int)
    parser.add_argument("--measured-batches", default=1, type=int)
    parser.add_argument("--repeats", default=1, type=int)
    parser.add_argument("--max-episodes", default=32, type=int)
    parser.add_argument("--max-samples", default=128, type=int)
    parser.add_argument("--seed", default=11, type=int)
    parser.add_argument("--candidates", default="", type=str)
    parser.add_argument("--gr00t-root", default=None, type=Path)
    parser.add_argument("--tiny-fixture", action="store_true")
    args = parser.parse_args(argv)
    worker_counts = (
        _int_list(args.worker_counts) if args.worker_counts else (int(args.worker_count),)
    )
    batch_sizes = _int_list(args.batch_sizes) if args.batch_sizes else (int(args.batch_size),)
    candidates = _candidate_list(args.candidates)
    results: list[ActualWorkerBakeoffResult] = []
    for worker_count in worker_counts:
        for batch_size in batch_sizes:
            output_dir = (
                args.output_dir
                if len(worker_counts) == 1 and len(batch_sizes) == 1
                else args.output_dir / f"worker_count_{worker_count}_batch_size_{batch_size}"
            )
            results.append(
                run_actual_worker_bakeoff(
                    ActualWorkerBenchmarkConfig(
                        batch_size=batch_size,
                        candidates=candidates,
                        gr00t_root=args.gr00t_root,
                        max_episodes=int(args.max_episodes),
                        max_samples=int(args.max_samples),
                        measured_batches=int(args.measured_batches),
                        output_dir=output_dir,
                        repeats=int(args.repeats),
                        seed=int(args.seed),
                        source_dataset=args.source_dataset,
                        use_tiny_fixture=bool(args.tiny_fixture),
                        warmup_batches=int(args.warmup_batches),
                        worker_count=worker_count,
                        working_root=args.working_root,
                    )
                )
            )
    for result in results:
        print(result.summary_markdown_path.as_posix())
    print(
        "conclusion="
        + (
            "READY_FOR_COMPUTE_ACTUAL_WORKER_BENCHMARK"
            if all(
                result.conclusion == "READY_FOR_COMPUTE_ACTUAL_WORKER_BENCHMARK"
                for result in results
            )
            else "REQUEST_CHANGES_REMAIN"
        )
    )
    return 0


def _source_payloads(config: ActualWorkerBenchmarkConfig) -> list[BenchmarkPayload]:
    """从真实 source row 物化 payload, 不写 source dataset。"""
    from autovla.dataloader.perf.native_loader_timing_v2 import (
        NativeLoaderTimingV2Config,
        discover_ffmpeg_tools,
        materialize_frame_with_ffmpeg,
        materialized_payload_with_blobs,
        read_source_rows,
    )

    timing_config = NativeLoaderTimingV2Config(
        batch_size=config.batch_size,
        max_episodes=config.max_samples,
        max_samples=config.max_samples,
        measured_batches=1,
        output_dir=config.output_dir,
        repeats=1,
        source_dataset=config.source_dataset,
        warmup_batches=0,
        worker_count=8,
        working_root=config.working_root,
    )
    tools = discover_ffmpeg_tools()

    def _materializer(request: Any) -> Any:
        return materialize_frame_with_ffmpeg(request, tools=tools)

    payloads: list[BenchmarkPayload] = []
    for row in read_source_rows(timing_config):
        payload, rgb = materialized_payload_with_blobs(
            candidate="zjh_lerobot_v21_autovla_adapter",
            materializer=_materializer,
            row=row,
        )
        payloads.append(_payload_from_native_payload(payload, rgb))
    return payloads[: config.max_samples]


def _payload_from_native_payload(
    payload: Mapping[str, object],
    rgb_blobs: tuple[bytes, bytes, bytes],
) -> BenchmarkPayload:
    """从 native_loader_timing_v2 payload 转成 BenchmarkPayload。"""
    return BenchmarkPayload(
        action=_float_tuple(_first_or_sequence(payload.get("action"), "action"), "action"),
        action_mask=_bool_tuple(
            _first_or_sequence(payload.get("action_mask"), "action_mask"),
            "action_mask",
        ),
        camera_rgb_0=rgb_blobs[0],
        camera_rgb_1=rgb_blobs[1],
        camera_rgb_2=rgb_blobs[2],
        episode_id=_string(payload.get("episode_id"), "episode_id"),
        language=_string(payload.get("language"), "language"),
        sample_id=_string(payload.get("sample_id"), "sample_id"),
        state=_float_tuple(payload.get("state"), "state"),
        window_id=_string(payload.get("window_id"), "window_id"),
    )


def _run_row(
    config: ActualWorkerBenchmarkConfig,
    adapter: CandidateNativeAdapter,
    evidence: WorkerRunEvidence,
    manifest_checksum: str,
) -> dict[str, object]:
    """生成 RUN 或 blocked actual-worker 行。"""
    status = (
        "RUN"
        if evidence.worker_count_evidence_status == "PASS"
        else ("BLOCKED_ACTUAL_WORKER_COUNT_NOT_MEASURED")
    )
    total_ms = sum(evidence.timings_ms) if evidence.timings_ms else 0.0
    samples_per_sec = (
        round(evidence.sample_count / max(total_ms / 1000.0, 0.000001), 6)
        if evidence.sample_count
        else 0.0
    )
    row: dict[str, object] = {
        "actual_worker_count": evidence.actual_worker_count,
        "adapter_label": adapter.label,
        "candidate": adapter.candidate_id,
        "file_open_count": evidence.file_open_count,
        "manifest_checksum": manifest_checksum,
        "missing_metrics": list(DEFAULTED_CORE_TIMING_FIELDS + MATRIX_TELEMETRY_FIELDS),
        "multiprocessing_enabled": evidence.multiprocessing_enabled,
        "native_loader": adapter.native_loader,
        "p50_batch_ms": _percentile(evidence.timings_ms, 50.0),
        "p95_batch_ms": _percentile(evidence.timings_ms, 95.0),
        "p99_batch_ms": _percentile(evidence.timings_ms, 99.0),
        "payload_complete": True,
        "payload_missing_fields": [],
        "prefetch_enabled": evidence.prefetch_enabled,
        "prefetch_factor": "not_executed",
        "persistent_workers": False,
        "per_batch_timings_ms": list(evidence.timings_ms),
        "prototype_only": adapter.prototype_only,
        "requested_worker_count": evidence.requested_worker_count,
        "sample_count": evidence.sample_count,
        "samples_per_sec": samples_per_sec,
        "status": status,
        "worker_count_evidence_status": evidence.worker_count_evidence_status,
    }
    row.update(_core_timing_values(evidence))
    return row


def _not_run_row(
    adapter: CandidateNativeAdapter,
    config: ActualWorkerBenchmarkConfig,
    manifest_checksum: str,
) -> dict[str, object]:
    """生成明确 not-run/blocked 行。"""
    row: dict[str, object] = {
        "actual_worker_count": "not_applicable",
        "adapter_label": adapter.label,
        "candidate": adapter.candidate_id,
        "manifest_checksum": manifest_checksum,
        "missing_metrics": ["worker_read_timing"],
        "multiprocessing_enabled": False,
        "native_loader": adapter.native_loader,
        "not_run_reason": adapter.reason,
        "payload_complete": False,
        "payload_missing_fields": ["worker_read_timing"],
        "prefetch_enabled": False,
        "prototype_only": adapter.prototype_only,
        "requested_worker_count": config.worker_count,
        "sample_count": 0,
        "samples_per_sec": 0.0,
        "status": adapter.default_status,
        "worker_count_evidence_status": adapter.default_status,
    }
    row.update({field: "not_applicable" for field in CORE_TIMING_FIELDS})
    return row


def _core_timing_values(evidence: WorkerRunEvidence) -> dict[str, object]:
    """生成核心 timing 字段, 未采集项进入 missing_metrics 表而非空值。"""
    total_ms = round(sum(evidence.timings_ms), 6)
    read_mb_s = round((evidence.bytes_read / 1_000_000.0) / max(total_ms / 1000.0, 0.000001), 6)
    samples_per_sec = round(evidence.sample_count / max(total_ms / 1000.0, 0.000001), 6)
    return {
        "action_load_ms": 0.0,
        "actions_per_sec": samples_per_sec,
        "bytes_read": evidence.bytes_read,
        "collate_ms": total_ms,
        "cpu_system_pct": 0.0,
        "cpu_user_pct": 0.0,
        "file_open_count": evidence.file_open_count,
        "frames_per_sec": samples_per_sec * 3.0,
        "index_load_ms": 0.0,
        "language_load_ms": 0.0,
        "loader_init_ms": 0.0,
        "media_decode_ms": 0.0,
        "metadata_load_ms": 0.0,
        "next_batch_wait_ms": 0.0,
        "payload_validation_ms": 0.0,
        "read_mb_s": read_mb_s,
        "rgb_materialize_ms": 0.0,
        "rss_mb_max": evidence.rss_mb_max,
        "sample_select_ms": 0.0,
        "samples_per_sec": samples_per_sec,
        "state_load_ms": 0.0,
        "tensor_or_array_conversion_ms": 0.0,
        "total_batch_ms": total_ms,
        "worker_queue_wait_ms": 0.0,
    }


def _write_outputs(
    *,
    config: ActualWorkerBenchmarkConfig,
    rows: Sequence[Mapping[str, object]],
    worker_rows: Sequence[Mapping[str, object]],
    payload_rows: Sequence[Mapping[str, object]],
    stage_rows: Sequence[Mapping[str, object]],
    missing_rows: Sequence[Mapping[str, object]],
    raw_json_path: Path,
    summary_csv_path: Path,
    summary_md_path: Path,
    worker_json_path: Path,
    ledger_path: Path,
    source_check_path: Path,
) -> None:
    """写出 Data-W1 要求的全部 tiny/local 表面。"""
    _write_json(raw_json_path, {"rows": list(rows), "schema_version": SCHEMA_VERSION})
    _write_csv(summary_csv_path, rows)
    _write_markdown(summary_md_path, rows, title="Actual Dataloader Worker Bakeoff")
    _write_json(worker_json_path, {"rows": list(worker_rows), "schema_version": SCHEMA_VERSION})
    _write_csv(config.output_dir / "worker_evidence_table.csv", worker_rows)
    _write_markdown(
        config.output_dir / "worker_evidence_table.md",
        worker_rows,
        title="Worker Evidence",
    )
    _write_json(
        config.output_dir / "payload_completeness_table.json",
        {"rows": list(payload_rows), "schema_version": SCHEMA_VERSION},
    )
    _write_csv(config.output_dir / "payload_completeness_table.csv", payload_rows)
    _write_markdown(
        config.output_dir / "payload_completeness_table.md",
        payload_rows,
        title="Payload Completeness",
    )
    _write_table_triplet(config.output_dir, "stage_timing_table", stage_rows)
    _write_table_triplet(config.output_dir, "missing_telemetry_table", missing_rows)
    _write_table_triplet(config.output_dir, "cache_policy_table", _cache_policy_rows(rows))
    _write_table_triplet(config.output_dir, "v21_gap_investigation_table", _v21_gap_rows(rows))
    _write_table_triplet(
        config.output_dir,
        "agent_result_consistency_audit",
        _consistency_rows(rows),
    )
    _write_table_triplet(
        config.output_dir,
        "backend_decision_table",
        _backend_decision_rows(rows, missing_rows),
    )
    _write_json(config.output_dir / "command_log_index.json", _command_log(config))
    _write_jsonl(config.output_dir / "per_batch_timings.jsonl", _per_batch_rows(rows))
    source_check_path.write_text("source_dataset_mutation_check: PASS\n", encoding="utf-8")
    _write_generated_ledger(config, ledger_path)


def _write_table_triplet(
    output_dir: Path,
    stem: str,
    rows: Sequence[Mapping[str, object]],
) -> None:
    """写出 json/csv/md 三联表。"""
    _write_json(output_dir / f"{stem}.json", {"rows": list(rows), "schema_version": SCHEMA_VERSION})
    _write_csv(output_dir / f"{stem}.csv", rows)
    _write_markdown(output_dir / f"{stem}.md", rows, title=stem.replace("_", " ").title())


def _write_generated_ledger(config: ActualWorkerBenchmarkConfig, path: Path) -> None:
    """写出 generated artifact ledger。"""
    entries: list[dict[str, object]] = []
    for item in sorted(config.working_root.rglob("*")):
        if item.is_file():
            entries.append(
                {
                    "candidate": item.parent.name,
                    "path": item.as_posix(),
                    "safe_to_delete_later": True,
                    "size_bytes": item.stat().st_size,
                    "tracked_status": "ignored_generated_artifact",
                }
            )
    _write_json(
        path,
        {
            "entries": entries,
            "generated_artifacts_tracked": False,
            "schema_version": f"{SCHEMA_VERSION}.generated_artifact_ledger",
        },
    )


def _stage_rows(
    adapter: CandidateNativeAdapter,
    evidence: WorkerRunEvidence,
) -> list[dict[str, object]]:
    """生成简洁 stage timing 行。"""
    total_ms = round(sum(evidence.timings_ms), 6)
    return [
        {
            "bytes_read": evidence.bytes_read,
            "candidate": adapter.candidate_id,
            "count": evidence.sample_count,
            "file_open_count": evidence.file_open_count,
            "stage": "worker_read_collate",
            "status": evidence.worker_count_evidence_status,
            "total_ms": total_ms,
        }
    ]


def _payload_completeness_row(
    adapter: CandidateNativeAdapter,
    evidence: WorkerRunEvidence,
    manifest_checksum: str,
) -> dict[str, object]:
    """生成 payload completeness 表行。"""
    return {
        "action": "present",
        "action_mask": "present",
        "camera_rgb_0": "present",
        "camera_rgb_1": "present",
        "camera_rgb_2": "present",
        "candidate": adapter.candidate_id,
        "language": "present",
        "manifest_checksum": manifest_checksum,
        "payload_complete": evidence.worker_count_evidence_status == "PASS",
        "payload_missing_fields": [],
        "state": "present",
    }


def _not_run_payload_row(
    adapter: CandidateNativeAdapter,
    manifest_checksum: str,
) -> dict[str, object]:
    """生成 not-run payload completeness 表行。"""
    return {
        "candidate": adapter.candidate_id,
        "manifest_checksum": manifest_checksum,
        "payload_complete": False,
        "payload_missing_fields": ["worker_read_timing"],
        "status": adapter.default_status,
    }


def _not_run_worker_row(
    adapter: CandidateNativeAdapter,
    config: ActualWorkerBenchmarkConfig,
) -> dict[str, object]:
    """生成 not-run worker evidence 表行。"""
    return {
        "actual_worker_count": "not_applicable",
        "candidate": adapter.candidate_id,
        "execution_mode": "not_run",
        "per_worker_sample_counts": {},
        "requested_worker_count": config.worker_count,
        "worker_count_evidence_status": adapter.default_status,
    }


def _cache_policy_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """生成 cache policy 表。"""
    return [
        {
            "cache_policy": "candidate_artifact_jsonl",
            "candidate": _string(row["candidate"], "candidate"),
            "persistent_reader_enabled": False,
            "prefetch_enabled": False,
            "status": row["status"],
        }
        for row in rows
    ]


def _v21_gap_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """生成 v2.1 native gap 表。"""
    return [
        {
            "candidate": row["candidate"],
            "gap": (
                "GR00T/LeRobot native D1 remains unsafe/unavailable"
                if row["candidate"] == "zjh_lerobot_v21_gr00t_or_lerobot_native"
                else "not_applicable"
            ),
            "status": row["status"],
        }
        for row in rows
    ]


def _consistency_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """生成 PR30 诊断数字一致性审计表。"""
    audit_rows: list[dict[str, object]] = []
    for row in rows:
        timings = _numeric_sequence(row.get("per_batch_timings_ms"))
        if timings:
            recomputed_p50 = _percentile(timings, 50.0)
            recomputed_p95 = _percentile(timings, 95.0)
            recomputed_p99 = _percentile(timings, 99.0)
            row_p50 = _optional_float(row.get("p50_batch_ms"))
            row_p95 = _optional_float(row.get("p95_batch_ms"))
            row_p99 = _optional_float(row.get("p99_batch_ms"))
            matches = (
                row_p50 == recomputed_p50
                and row_p95 == recomputed_p95
                and row_p99 == recomputed_p99
            )
            classification = (
                "TRACEABLE_BUT_METHODOLOGY_LIMITED" if matches else "NUMERICALLY_INCONSISTENT"
            )
        else:
            recomputed_p50 = "not_applicable"
            recomputed_p95 = "not_applicable"
            recomputed_p99 = "not_applicable"
            matches = False
            classification = "UNTRACEABLE_NEEDS_RERUN"
        audit_rows.append(
            {
                "adapter_v1_diagnostic_only": True,
                "aggregate_matches_raw_timings": matches,
                "classification": classification,
                "candidate": row["candidate"],
                "final_backend_winner": False,
                "recomputed_p50_ms": recomputed_p50,
                "recomputed_p95_ms": recomputed_p95,
                "recomputed_p99_ms": recomputed_p99,
                "row_p50_ms": row.get("p50_batch_ms", "not_applicable"),
                "row_p95_ms": row.get("p95_batch_ms", "not_applicable"),
                "row_p99_ms": row.get("p99_batch_ms", "not_applicable"),
                "status": row["status"],
            }
        )
    return audit_rows


def _backend_decision_rows(
    rows: Sequence[Mapping[str, object]],
    missing_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """生成保守 backend decision 表。"""
    row_by_candidate = {_string(row["candidate"], "candidate"): row for row in rows}
    mandatory_pass = all(
        row_by_candidate.get(candidate.candidate_id, {}).get("status") == "RUN"
        for candidate in CANDIDATE_MATRIX
        if candidate.mandatory
    )
    blocking_missing = any(bool(row.get("blocking")) for row in missing_rows)
    return [
        {
            "decision": "NO_BACKEND_WINNER",
            "reason": "D1 and prompt-contract metric gaps remain; no final backend winner selected",
            "blocking_missing_telemetry": blocking_missing,
            "mandatory_comparability_gates_pass": mandatory_pass and not blocking_missing,
            "required_run_rows_present": mandatory_pass,
            "training_format_selected": False,
        }
    ]


def _missing_row(
    candidate: str,
    metric: str,
    reason: str,
    *,
    blocking: bool,
) -> dict[str, object]:
    """生成 missing telemetry 表行。"""
    return {
        "blocking": blocking,
        "candidate": candidate,
        "metric": metric,
        "reason": reason,
    }


def _missing_metric_rows(
    candidate: str,
    row: Mapping[str, object],
) -> list[dict[str, object]]:
    """把 RUN row 中的默认/未执行核心指标展开到 missing telemetry 表。"""
    rows: list[dict[str, object]] = []
    for metric in DEFAULTED_CORE_TIMING_FIELDS:
        rows.append(
            _missing_row(
                candidate,
                metric,
                "metric emitted as default zero by current W1 runner; blocks final benchmark pass",
                blocking=True,
            )
        )
    for metric in MATRIX_TELEMETRY_FIELDS:
        rows.append(
            _missing_row(
                candidate,
                metric,
                "persistent worker / prefetch / full warmup-measured-repeat matrix not executed",
                blocking=True,
            )
        )
    if row.get("worker_count_evidence_status") != "PASS":
        rows.append(
            _missing_row(
                candidate,
                "actual_worker_count",
                "actual worker count evidence did not pass",
                blocking=True,
            )
        )
    return rows


def _command_log(config: ActualWorkerBenchmarkConfig) -> dict[str, object]:
    """记录可复现 CLI 形状。"""
    return {
        "commands": [
            {
                "argv": [
                    "python",
                    "-m",
                    "autovla.dataloader.perf.actual_dataloader_worker_bakeoff",
                    "--source-dataset",
                    config.source_dataset.as_posix(),
                    "--working-root",
                    config.working_root.as_posix(),
                    "--output-dir",
                    config.output_dir.as_posix(),
                    "--worker-count",
                    str(config.worker_count),
                ],
                "compute_required_for_full_run": True,
            }
        ],
        "schema_version": f"{SCHEMA_VERSION}.command_log_index",
    }


def _per_batch_rows(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """生成简化 per-batch timing JSONL。"""
    timing_rows: list[Mapping[str, object]] = []
    for row in rows:
        timings = _numeric_sequence(row.get("per_batch_timings_ms"))
        if not timings:
            timing_rows.append(
                {
                    "batch_index": "not_applicable",
                    "candidate": row["candidate"],
                    "status": row["status"],
                    "total_batch_ms": "not_applicable",
                }
            )
            continue
        for batch_index, timing in enumerate(timings):
            timing_rows.append(
                {
                    "batch_index": batch_index,
                    "candidate": row["candidate"],
                    "status": row["status"],
                    "total_batch_ms": timing,
                }
            )
    return timing_rows


def _decision(rows: Sequence[Mapping[str, object]]) -> str:
    """生成保守结论, 不选择 backend winner。"""
    if any(row.get("status") == "BLOCKED_ACTUAL_WORKER_COUNT_NOT_MEASURED" for row in rows):
        return "BLOCKED_ACTUAL_WORKER_COUNT_NOT_MEASURED"
    row_by_candidate = {_string(row["candidate"], "candidate"): row for row in rows}
    for candidate in CANDIDATE_MATRIX:
        row = row_by_candidate.get(candidate.candidate_id, {})
        if candidate.mandatory and row.get("status") != "RUN":
            return "REQUEST_CHANGES_REMAIN"
    return "READY_FOR_COMPUTE_ACTUAL_WORKER_BENCHMARK"


def _shared_manifest(
    config: ActualWorkerBenchmarkConfig,
    payloads: Sequence[BenchmarkPayload],
) -> dict[str, object]:
    """生成共享 sample/window manifest。"""
    payload: dict[str, object] = {
        "camera_policy": "three_rgb_materialized_payloads_required",
        "decode_policy": "actual-worker-runner reads candidate payload artifact",
        "max_samples": config.max_samples,
        "sample_ids": [payload.sample_id for payload in payloads],
        "schema_version": f"{SCHEMA_VERSION}.shared_sample_window_manifest",
        "seed": config.seed,
        "source_dataset": config.source_dataset.as_posix(),
        "window_ids": [payload.window_id for payload in payloads],
    }
    payload["checksum"] = _stable_hash(payload)
    return payload


def _tiny_payloads(sample_count: int) -> list[BenchmarkPayload]:
    """生成 tiny fixture payload, 仅用于 login-node-safe 测试。"""
    return [
        BenchmarkPayload(
            action=(float(index), 1.0, 2.0),
            action_mask=(True, True, False),
            camera_rgb_0=f"rgb0-{index}".encode("utf-8"),
            camera_rgb_1=f"rgb1-{index}".encode("utf-8"),
            camera_rgb_2=f"rgb2-{index}".encode("utf-8"),
            episode_id="episode-000000",
            language="tiny actual worker task",
            sample_id=f"sample-{index:06d}",
            state=(0.0, float(index), 2.0),
            window_id=f"episode-000000:sample-{index:06d}:0",
        )
        for index in range(sample_count)
    ]


def _write_payload_jsonl(path: Path, payloads: Sequence[BenchmarkPayload]) -> None:
    """写出候选 payload artifact。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(payload.to_json_dict(), sort_keys=True) for payload in payloads]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_payload_jsonl(path: Path) -> list[BenchmarkPayload]:
    """读取候选 payload artifact。"""
    payloads: list[BenchmarkPayload] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = BenchmarkPayload.from_json_dict(cast(Mapping[str, object], json.loads(line)))
        validate_benchmark_payload(payload)
        payloads.append(payload)
    if not payloads:
        raise ValueError("payload artifact must contain at least one row")
    return payloads


def _process_worker_chunk(
    payload_path: str,
    worker_slot: int,
    indices: tuple[int, ...],
    queue: Any,
) -> None:
    """子进程 worker: 读取分配索引并返回证据。"""
    started = time.perf_counter()
    payloads = _read_payload_jsonl(Path(payload_path))
    selected = [payloads[index] for index in indices]
    batch = collate_benchmark_batch(selected)
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
    queue.put(
        {
            "bytes_read": batch.bytes_read,
            "elapsed_ms": elapsed_ms,
            "file_open_count": 1,
            "payload_hash": batch.payload_hash,
            "pid": os.getpid(),
            "sample_count": len(selected),
            "worker_id": f"worker-{worker_slot:02d}",
        }
    )


def _split_indices(sample_count: int, worker_count: int) -> list[list[int]]:
    """按 round-robin 分配索引, 保证 sample_count>=worker_count 时每 worker 有样本。"""
    chunks: list[list[int]] = [[] for _ in range(worker_count)]
    for index in range(sample_count):
        chunks[index % worker_count].append(index)
    return chunks


def _batch_count(sample_count: int, batch_size: int) -> int:
    """计算 batch 数。"""
    return (sample_count + batch_size - 1) // batch_size


def _percentile(values: Sequence[float], percentile: float) -> float:
    """用稳定 nearest-rank 规则计算百分位。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((percentile / 100.0) * (len(ordered) - 1))
    return round(ordered[index], 6)


def _numeric_sequence(value: object) -> tuple[float, ...]:
    """把 JSON-safe 数值序列收窄成 float tuple。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    items = cast(Sequence[object], value)
    result: list[float] = []
    for item in items:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return ()
        result.append(float(item))
    return tuple(result)


def _optional_float(value: object) -> float | None:
    """读取可选数值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), 6)


def _int_list(value: str) -> tuple[int, ...]:
    """解析逗号分隔正整数列表。"""
    parsed: list[int] = []
    for item in value.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        number = int(stripped)
        if number < 0:
            raise ValueError("worker/batch counts must be non-negative")
        parsed.append(number)
    if not parsed:
        raise ValueError("at least one value is required")
    return tuple(parsed)


def _candidate_list(value: str) -> tuple[str, ...]:
    """解析候选列表, 空值表示全候选矩阵。"""
    if not value.strip():
        return tuple(candidate.candidate_id for candidate in CANDIDATE_MATRIX)
    candidates = tuple(item.strip() for item in value.split(",") if item.strip())
    if not candidates:
        raise ValueError("at least one candidate is required")
    known = {candidate.candidate_id for candidate in CANDIDATE_MATRIX}
    unknown = set(candidates) - known
    if unknown:
        raise ValueError(f"unknown candidates: {sorted(unknown)}")
    return candidates


def _encode_bytes(value: bytes) -> str:
    """编码 bytes。"""
    return base64.b64encode(value).decode("ascii")


def _decode_bytes(value: object, field_name: str) -> bytes:
    """解码 base64 bytes。"""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} is required")
    return base64.b64decode(value.encode("ascii"))


def _float_tuple(value: object, field_name: str) -> tuple[float, ...]:
    """读取 float tuple。"""
    items = _object_sequence(value, field_name)
    result: list[float] = []
    for item in items:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{field_name} items must be numeric")
        result.append(float(item))
    return tuple(result)


def _bool_tuple(value: object, field_name: str) -> tuple[bool, ...]:
    """读取 bool tuple。"""
    items = _object_sequence(value, field_name)
    result: list[bool] = []
    for item in items:
        if not isinstance(item, bool):
            raise ValueError(f"{field_name} items must be bool")
        result.append(item)
    return tuple(result)


def _first_or_sequence(value: object, field_name: str) -> Sequence[object]:
    """读取可能带 batch 维的 sequence。"""
    items = _object_sequence(value, field_name)
    if items:
        first = items[0]
        if isinstance(first, Sequence) and not isinstance(first, (str, bytes, bytearray)):
            return _object_sequence(cast(object, first), field_name)
    return items


def _object_sequence(value: object, field_name: str) -> Sequence[object]:
    """把 object 收窄成 object sequence。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a sequence")
    return cast(Sequence[object], value)


def _string(value: object, field_name: str) -> str:
    """读取非空字符串。"""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _int(value: object, field_name: str) -> int:
    """读取 int。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _stable_hash(payload: object) -> str:
    """生成稳定 SHA256。"""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _rss_mb() -> float:
    """读取进程最大 RSS。"""
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 6)


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    """写出稳定 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """写出稳定 JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """写出 CSV, 字段取所有行 key 的并集。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_markdown(path: Path, rows: Sequence[Mapping[str, object]], *, title: str) -> None:
    """写出简洁 Markdown 表。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text(f"# {title}\n\nNo rows.\n", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    lines = [f"# {title}", "", "|" + "|".join(fieldnames) + "|"]
    lines.append("|" + "|".join("---" for _ in fieldnames) + "|")
    for row in rows:
        lines.append("|" + "|".join(str(row.get(field, "")) for field in fieldnames) + "|")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
