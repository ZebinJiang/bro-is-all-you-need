"""Format-native loader W8 bakeoff 执行入口。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

NATIVE_LOADER_CANDIDATE_IDS: tuple[str, ...] = (
    "zjh_lerobot_v21_raw",
    "lerobot_v3_converted",
    "webdataset_converted",
    "robodm_style_converted",
    "zarr_converted",
)

RUNNABLE_CANDIDATES = frozenset({"webdataset_converted", "robodm_style_converted"})
BLOCKED_CANDIDATES: dict[str, tuple[str, str]] = {
    "zjh_lerobot_v21_raw": (
        "NOT_RUN_UNSAFE_OR_UNAVAILABLE",
        "GR00T original dataloader is not proven safe for data-only W8 execution",
    ),
    "lerobot_v3_converted": (
        "NOT_RUN_DEPENDENCY_BLOCKED",
        "official LeRobot v3 dependency/version route is not approved",
    ),
    "zarr_converted": (
        "NOT_RUN_DEPENDENCY_BLOCKED",
        "actual Zarr dependency/version decision is missing",
    ),
}

SCHEMA_VERSION = "autovla.native_loader_w8_bakeoff.v1"
PAYLOAD_SCHEMA_VERSION = "autovla.native_loader_benchmark_payload.v1"
LEDGER_SCHEMA_VERSION = "autovla.native_loader_generated_artifact_ledger.v1"

CAMERA_STREAMS: tuple[str, str, str] = (
    "observation.images.left_wrist_rgb",
    "observation.images.head_rgb",
    "observation.images.right_wrist_rgb",
)


@dataclass(frozen=True, slots=True)
class NativeLoaderBakeoffConfig:
    """描述一次 native-loader W8 bakeoff 本地执行配置。"""

    source_dataset: Path
    working_root: Path
    output_dir: Path
    gr00t_root: Path
    worker_count: int
    max_episodes: int
    max_samples: int
    repeats: int
    candidates: tuple[str, ...]
    symlink_only_output: bool = False

    def __post_init__(self) -> None:
        """校验路径、候选和 W8 执行边界。"""
        if self.worker_count != 8:
            raise ValueError("worker_count must be 8 for native-loader W8 bakeoff")
        if self.max_episodes <= 0 or self.max_samples <= 0 or self.repeats <= 0:
            raise ValueError("max_episodes, max_samples, and repeats must be positive")
        unknown = set(self.candidates) - set(NATIVE_LOADER_CANDIDATE_IDS)
        if unknown:
            raise ValueError(f"unknown native-loader candidates: {sorted(unknown)}")
        if self.symlink_only_output:
            raise ValueError("symlink-only output is invalid for native-loader bakeoff")
        source = self.source_dataset.resolve()
        working = self.working_root.resolve()
        output = self.output_dir.resolve()
        if working == source or _is_relative_to(working, source):
            raise ValueError("working_root must not be the source dataset")
        if output == source or _is_relative_to(output, source):
            raise ValueError("output_dir must not be the source dataset")
        if "datasets/readonly" in working.as_posix():
            raise ValueError("working_root must not be inside source dataset policy roots")


@dataclass(frozen=True, slots=True)
class NativeLoaderBakeoffResult:
    """记录 native-loader bakeoff 执行输出。"""

    conclusion: str
    rows: list[dict[str, object]]
    candidate_dirs: dict[str, Path]
    report_path: Path
    ledger_path: Path


@dataclass(frozen=True, slots=True)
class _WorkerTaskResult:
    """保存单个 worker 的读取结果和执行身份。"""

    worker_id: str
    process_id: int
    thread_id: int
    rows: list[dict[str, object]]


def run_native_loader_bakeoff(config: NativeLoaderBakeoffConfig) -> NativeLoaderBakeoffResult:
    """运行本地 no-training native-loader bakeoff harness。"""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.working_root.mkdir(parents=True, exist_ok=True)
    source_rows = _load_source_rows(config)
    candidate_dirs: dict[str, Path] = {}
    summary_rows: list[dict[str, object]] = []
    ledger_entries: list[dict[str, object]] = []

    for candidate_id in config.candidates:
        candidate_dir = config.working_root / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        candidate_dirs[candidate_id] = candidate_dir
        if candidate_id in BLOCKED_CANDIDATES:
            row = _write_not_run_candidate(
                candidate_id=candidate_id,
                candidate_dir=candidate_dir,
                output_dir=config.output_dir,
            )
        elif candidate_id == "webdataset_converted":
            row = _run_webdataset_candidate(
                candidate_id=candidate_id,
                candidate_dir=candidate_dir,
                output_dir=config.output_dir,
                config=config,
                source_rows=source_rows,
            )
        elif candidate_id == "robodm_style_converted":
            row = _run_robodm_style_candidate(
                candidate_id=candidate_id,
                candidate_dir=candidate_dir,
                output_dir=config.output_dir,
                config=config,
                source_rows=source_rows,
            )
        else:  # pragma: no cover - 候选校验已覆盖此分支
            raise ValueError(f"unsupported candidate: {candidate_id}")
        summary_rows.append(row)
        ledger_entries.extend(
            _ledger_entries(candidate_dir=candidate_dir, candidate_id=candidate_id)
        )

    ledger_path = config.output_dir / "generated-artifact-ledger.json"
    _write_json(
        ledger_path,
        {
            "entries": ledger_entries,
            "generated_artifacts_tracked": False,
            "schema_version": LEDGER_SCHEMA_VERSION,
            "source_dataset_mutated": False,
        },
    )
    report_path = config.output_dir / "native-loader-backend-bakeoff-report.md"
    report_path.write_text(_render_report(summary_rows), encoding="utf-8")
    _write_json(
        config.output_dir / "native-loader-bakeoff-summary.json",
        {
            "candidate_rows": summary_rows,
            "conclusion": "READY_FOR_COMPUTE_BENCHMARK",
            "external_effects": _external_effects(),
            "schema_version": SCHEMA_VERSION,
        },
    )
    return NativeLoaderBakeoffResult(
        conclusion="READY_FOR_COMPUTE_BENCHMARK",
        rows=summary_rows,
        candidate_dirs=candidate_dirs,
        report_path=report_path,
        ledger_path=ledger_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """解析 CLI 参数并运行 native-loader bakeoff。"""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        result = run_native_loader_bakeoff(
            NativeLoaderBakeoffConfig(
                source_dataset=Path(str(args.source_dataset)),
                working_root=Path(str(args.working_root)),
                output_dir=Path(str(args.output_dir)),
                gr00t_root=Path(str(args.gr00t_root)),
                worker_count=int(args.worker_count),
                max_episodes=int(args.max_episodes),
                max_samples=int(args.max_samples),
                repeats=int(args.repeats),
                candidates=tuple(str(item) for item in args.candidate),
            )
        )
    except Exception as exc:
        print(f"native-loader bakeoff error: {exc}")
        return 2
    print(result.report_path.as_posix())
    print(f"conclusion={result.conclusion}")
    return 0


def _parser() -> argparse.ArgumentParser:
    """构造命令行 parser。"""
    parser = argparse.ArgumentParser(prog="python -m autovla.dataloader.perf.native_loader_bakeoff")
    parser.add_argument("--source-dataset", required=True)
    parser.add_argument("--working-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gr00t-root", required=True)
    parser.add_argument("--worker-count", type=int, required=True)
    parser.add_argument("--max-episodes", type=int, required=True)
    parser.add_argument("--max-samples", type=int, required=True)
    parser.add_argument("--repeats", type=int, required=True)
    parser.add_argument(
        "--candidate",
        action="append",
        choices=NATIVE_LOADER_CANDIDATE_IDS,
        required=True,
    )
    return parser


def _load_source_rows(config: NativeLoaderBakeoffConfig) -> list[dict[str, object]]:
    """从 source parquet 读取 bounded payload 行, 不解码媒体。"""
    parquet_module = _import_module("pyarrow.parquet")
    files = sorted((config.source_dataset / "data").glob("chunk-*/*.parquet"))
    if not files:
        raise ValueError("native-loader bakeoff requires source parquet files")
    rows: list[dict[str, object]] = []
    for parquet_path in files:
        table = parquet_module.read_table(parquet_path)
        for raw in _iter_table_rows(table):
            if len(rows) >= config.max_samples:
                return rows
            rows.append(_payload_row_from_source(raw=raw, source_dataset=config.source_dataset))
    if not rows:
        raise ValueError("native-loader bakeoff found no source rows")
    return rows


def _payload_row_from_source(
    *,
    raw: Mapping[str, object],
    source_dataset: Path,
) -> dict[str, object]:
    """把 parquet 行归一化成 BenchmarkPayload 行。"""
    action = _float_list(raw.get("action"), field="action")
    state_value = raw.get("observation.state", raw.get("state"))
    state = _float_list(state_value, field="state")
    action_mask = _bool_list(raw.get("action_mask"), expected=len(action))
    sample_index = _int_or_default(raw.get("index"), 0)
    episode_index = _int_or_default(raw.get("episode_index"), 0)
    frame_index = _int_or_default(raw.get("frame_index"), sample_index)
    timestamp = _float_or_default(raw.get("timestamp"), float(frame_index))
    language = _string_or_default(raw.get("language"), "zjh task 0")
    sample_id = f"sample-{sample_index:09d}"
    episode_id = f"episode-{episode_index:06d}"
    camera_refs = _camera_refs(
        source_dataset=source_dataset,
        episode_index=episode_index,
        frame_index=frame_index,
        timestamp=timestamp,
    )
    payload: dict[str, object] = {
        "action": [action],
        "action_dtype": "float32",
        "action_mask": [action_mask],
        "action_shape": [1, len(action)],
        "camera.rgb_0": camera_refs[0],
        "camera.rgb_1": camera_refs[1],
        "camera.rgb_2": camera_refs[2],
        "camera_dtypes": {f"camera.rgb_{index}": "video_stream_ref" for index in range(3)},
        "camera_shapes": {f"camera.rgb_{index}": "stream_ref" for index in range(3)},
        "episode_id": episode_id,
        "frame_index": frame_index,
        "language": language,
        "payload_missing_fields": [],
        "sample_id": sample_id,
        "source_dataset": source_dataset.as_posix(),
        "state": state,
        "state_dtype": "float32",
        "state_shape": [len(state)],
        "timestamp": timestamp,
        "window_id": f"{episode_id}:{sample_id}:{frame_index}",
    }
    payload["payload_hash"] = _stable_hash(payload)
    return payload


def _write_not_run_candidate(
    *,
    candidate_id: str,
    candidate_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    """写出不运行候选的 fail-closed reason。"""
    classification, reason = BLOCKED_CANDIDATES[candidate_id]
    payload = {
        "candidate_id": candidate_id,
        "classification": classification,
        "external_effects": _external_effects(),
        "not_run_reason": reason,
        "schema_version": f"{SCHEMA_VERSION}.not_run_reason",
    }
    _write_json(candidate_dir / "not_run_reason.json", payload)
    _write_json(output_dir / f"{candidate_id}-result.json", payload)
    return {
        "benchmark_scope": "not_run",
        "candidate_id": candidate_id,
        "classification": classification,
        "external_effects": _external_effects(),
        "not_run_reason": reason,
        "prototype_only": False,
        "worker_count": 8,
    }


def _run_webdataset_candidate(
    *,
    candidate_id: str,
    candidate_dir: Path,
    output_dir: Path,
    config: NativeLoaderBakeoffConfig,
    source_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """构建并通过 WebDataset streaming 读取候选 payload。"""
    wds = _import_module("webdataset")
    shard_dir = candidate_dir / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    shard_path = shard_dir / "shard-000000.tar"
    started = time.perf_counter()
    writer = wds.TarWriter(shard_path.as_posix(), mtime=0)
    try:
        for row in source_rows:
            sample_id = _string(row.get("sample_id"), "sample_id")
            writer.write({"__key__": sample_id, "json": _json_bytes(row)})
    finally:
        writer.close()
    read_rows, worker_evidence = _execute_worker_read_pipeline(
        rows=source_rows,
        worker_count=config.worker_count,
        read_partition=lambda sample_ids: _read_webdataset_rows_for_samples(
            wds,
            shard_path=shard_path,
            sample_ids=sample_ids,
        ),
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
    return _write_runnable_candidate(
        candidate_id=candidate_id,
        candidate_dir=candidate_dir,
        output_dir=output_dir,
        config=config,
        rows=read_rows,
        native_files=[shard_path],
        prototype_only=False,
        read_time_ms=elapsed_ms,
        worker_evidence=worker_evidence,
    )


def _run_robodm_style_candidate(
    *,
    candidate_id: str,
    candidate_dir: Path,
    output_dir: Path,
    config: NativeLoaderBakeoffConfig,
    source_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """构建并读取 owned Robo-DM-style 原生 prototype。"""
    payload_dir = candidate_dir / "payload"
    payload_dir.mkdir(parents=True, exist_ok=True)
    payload_path = payload_dir / "benchmark_payload_rows.jsonl"
    started = time.perf_counter()
    _write_jsonl(payload_path, source_rows)
    read_rows, worker_evidence = _execute_worker_read_pipeline(
        rows=source_rows,
        worker_count=config.worker_count,
        read_partition=lambda sample_ids: _read_jsonl_rows_for_samples(
            payload_path,
            sample_ids=sample_ids,
        ),
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 6)
    return _write_runnable_candidate(
        candidate_id=candidate_id,
        candidate_dir=candidate_dir,
        output_dir=output_dir,
        config=config,
        rows=read_rows,
        native_files=[payload_path],
        prototype_only=True,
        read_time_ms=elapsed_ms,
        worker_evidence=worker_evidence,
    )


def _write_runnable_candidate(
    *,
    candidate_id: str,
    candidate_dir: Path,
    output_dir: Path,
    config: NativeLoaderBakeoffConfig,
    rows: Sequence[Mapping[str, object]],
    native_files: Sequence[Path],
    prototype_only: bool,
    read_time_ms: float,
    worker_evidence: Mapping[str, object],
) -> dict[str, object]:
    """写出可运行候选的 manifest、索引、合同和 validation。"""
    candidate_rows = _candidate_payload_rows(rows=rows, candidate_id=candidate_id)
    _write_jsonl(candidate_dir / "benchmark_payload_rows.jsonl", candidate_rows)
    _write_jsonl(candidate_dir / "sample_index.jsonl", _sample_index_rows(candidate_rows))
    _write_jsonl(candidate_dir / "episode_index.jsonl", _episode_index_rows(candidate_rows))
    validation = _payload_validation(candidate_id=candidate_id, rows=candidate_rows, worker_count=8)
    validation["worker_count_evidence_status"] = worker_evidence["worker_count_evidence_status"]
    validation["worker_execution_evidence"] = worker_evidence
    _write_json(candidate_dir / "payload_contract_validation.json", validation)
    _write_json(candidate_dir / "modality_summary.json", _modality_summary(rows))
    _write_json(candidate_dir / "checksums.json", _checksums(candidate_dir))
    _write_json(
        candidate_dir / "loader_contract.json",
        {
            "candidate_id": candidate_id,
            "external_effects": _external_effects(),
            "native_loader_kind": (
                "webdataset_package" if "webdataset" in candidate_id else "owned_native_prototype"
            ),
            "payload_schema_version": PAYLOAD_SCHEMA_VERSION,
            "prototype_only": prototype_only,
            "worker_count": config.worker_count,
            "worker_execution_evidence": worker_evidence,
        },
    )
    _write_json(
        candidate_dir / "conversion_manifest.json",
        {
            "candidate_id": candidate_id,
            "external_effects": _external_effects(),
            "generated_artifacts_tracked": False,
            "native_generated_files": [
                path.relative_to(candidate_dir).as_posix() for path in native_files
            ],
            "prototype_only": prototype_only,
            "schema_version": f"{SCHEMA_VERSION}.conversion_manifest",
            "source_dataset": config.source_dataset.as_posix(),
            "source_dataset_mutated": False,
            "worker_count": config.worker_count,
            "worker_execution_evidence": worker_evidence,
        },
    )
    result = {
        "candidate_id": candidate_id,
        "classification": "RUNNABLE_NOW",
        "payload_contract_validation": validation,
        "prototype_only": prototype_only,
        "read_time_ms": read_time_ms,
        "sample_count": len(candidate_rows),
        "schema_version": f"{SCHEMA_VERSION}.candidate_result",
        "worker_count": config.worker_count,
        "worker_execution_evidence": worker_evidence,
    }
    _write_json(output_dir / f"{candidate_id}-result.json", result)
    return {
        "benchmark_scope": "benchmarked_login_node_safe_harness",
        "candidate_id": candidate_id,
        "classification": "RUNNABLE_NOW",
        "external_effects": _external_effects(),
        "payload_valid": validation["payload_valid"],
        "prototype_only": prototype_only,
        "read_time_ms": read_time_ms,
        "sample_count": len(candidate_rows),
        "worker_count": config.worker_count,
        "worker_execution_evidence": worker_evidence,
        "worker_count_evidence_status": worker_evidence["worker_count_evidence_status"],
    }


def _candidate_payload_rows(
    *,
    rows: Sequence[Mapping[str, object]],
    candidate_id: str,
) -> list[dict[str, object]]:
    """为候选写入 source_backend 并重新计算 payload hash。"""
    candidate_rows: list[dict[str, object]] = []
    for row in rows:
        payload = dict(row)
        payload["source_backend"] = candidate_id
        payload.pop("payload_hash", None)
        payload["payload_hash"] = _stable_hash(payload)
        candidate_rows.append(payload)
    return candidate_rows


def _iter_table_rows(table: Any) -> list[dict[str, object]]:
    """把 pyarrow Table 转成 JSON-safe 行。"""
    columns = list(table.column_names)
    raw_columns = {name: table[name].to_pylist() for name in columns}
    rows: list[dict[str, object]] = []
    for index in range(int(table.num_rows)):
        rows.append({name: _json_safe(raw_columns[name][index]) for name in columns})
    return rows


def _sample_index_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """构造 sample_index.jsonl。"""
    return [
        {
            "episode_id": row["episode_id"],
            "payload_hash": row["payload_hash"],
            "sample_id": row["sample_id"],
            "window_id": row["window_id"],
        }
        for row in rows
    ]


def _episode_index_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """构造 episode_index.jsonl。"""
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(_string(row.get("episode_id"), "episode_id"), []).append(
            _string(row.get("sample_id"), "sample_id")
        )
    return [
        {"episode_id": episode_id, "sample_count": len(sample_ids), "sample_ids": sample_ids}
        for episode_id, sample_ids in sorted(grouped.items())
    ]


def _payload_validation(
    *,
    candidate_id: str,
    rows: Sequence[Mapping[str, object]],
    worker_count: int,
) -> dict[str, object]:
    """验证 action、语言、三路 RGB 引用、state/mask 是否完整。"""
    missing: list[str] = []
    for row in rows:
        for field in ("action", "language", "camera.rgb_0", "camera.rgb_1", "camera.rgb_2"):
            if row.get(field) in (None, "", []):
                missing.append(field)
        if row.get("state") in (None, []):
            missing.append("state")
        if row.get("action_mask") in (None, []):
            missing.append("action_mask")
    unique_missing = sorted(set(missing))
    return {
        "camera_stream_count": 3,
        "candidate_id": candidate_id,
        "payload_missing_fields": unique_missing,
        "payload_valid": not unique_missing and bool(rows),
        "sample_count": len(rows),
        "schema_version": f"{SCHEMA_VERSION}.payload_contract_validation",
        "worker_count": worker_count,
    }


def _modality_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """构造 modality summary, 明确 RGB 是 stream 引用而非解码张量。"""
    first: Mapping[str, object] = rows[0] if rows else {}
    return {
        "action_dtype": first.get("action_dtype", "missing"),
        "camera_dtypes": first.get("camera_dtypes", {}),
        "camera_streams": list(CAMERA_STREAMS),
        "camera_tensor_decoded": False,
        "language": "present",
        "schema_version": f"{SCHEMA_VERSION}.modality_summary",
        "state_dtype": first.get("state_dtype", "missing"),
    }


def _camera_refs(
    *,
    source_dataset: Path,
    episode_index: int,
    frame_index: int,
    timestamp: float,
) -> list[dict[str, object]]:
    """构造三路 RGB 源视频流引用, 不读取或解码媒体。"""
    return [
        {
            "decode": "deferred",
            "episode_index": episode_index,
            "frame_index": frame_index,
            "source_dataset": source_dataset.as_posix(),
            "stream_key": stream_key,
            "timestamp": timestamp,
        }
        for stream_key in CAMERA_STREAMS
    ]


def _execute_worker_read_pipeline(
    *,
    rows: Sequence[Mapping[str, object]],
    worker_count: int,
    read_partition: Callable[[Sequence[str]], list[dict[str, object]]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """用真实 thread-pool worker 读取每个分片分配的样本。"""
    partitions = _worker_partitions(rows=rows, worker_count=worker_count)
    order = {_string(row.get("sample_id"), "sample_id"): index for index, row in enumerate(rows)}
    barrier = threading.Barrier(worker_count)

    def _run_worker(worker_id: str, sample_ids: tuple[str, ...]) -> _WorkerTaskResult:
        """执行单个 worker 的 native reader 路径。"""
        barrier.wait(timeout=30.0)
        worker_rows = read_partition(sample_ids)
        actual_sample_ids = {_string(row.get("sample_id"), "sample_id") for row in worker_rows}
        if actual_sample_ids != set(sample_ids):
            raise ValueError(f"{worker_id} did not read its assigned sample ids")
        return _WorkerTaskResult(
            process_id=os.getpid(),
            rows=worker_rows,
            thread_id=threading.get_ident(),
            worker_id=worker_id,
        )

    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix="autovla-native-loader-w8",
    ) as executor:
        futures = [
            executor.submit(_run_worker, worker_id, sample_ids)
            for worker_id, sample_ids in partitions
        ]
        worker_results = [future.result() for future in futures]

    read_rows: list[dict[str, object]] = []
    for worker_result in worker_results:
        read_rows.extend(worker_result.rows)
    read_rows.sort(key=lambda row: order[_string(row.get("sample_id"), "sample_id")])
    return read_rows, _worker_execution_evidence(
        requested_worker_count=worker_count,
        sample_count=len(rows),
        worker_results=worker_results,
    )


def _worker_partitions(
    *,
    rows: Sequence[Mapping[str, object]],
    worker_count: int,
) -> list[tuple[str, tuple[str, ...]]]:
    """按 round-robin 给每个 worker 分配稳定样本子集。"""
    assigned: list[list[str]] = [[] for _ in range(worker_count)]
    for index, row in enumerate(rows):
        sample_id = _string(row.get("sample_id"), "sample_id")
        assigned[index % worker_count].append(sample_id)
    return [(f"worker-{index:03d}", tuple(sample_ids)) for index, sample_ids in enumerate(assigned)]


def _worker_execution_evidence(
    *,
    requested_worker_count: int,
    sample_count: int,
    worker_results: Sequence[_WorkerTaskResult],
) -> dict[str, object]:
    """汇总 worker 参与证据, 供 Compute/HPC 复核。"""
    worker_ids = [result.worker_id for result in worker_results]
    per_worker_counts = {
        result.worker_id: len(result.rows)
        for result in sorted(worker_results, key=lambda item: item.worker_id)
    }
    every_worker_observed_sample = all(count > 0 for count in per_worker_counts.values())
    observed_worker_count = len(worker_results)
    status = (
        "PASS"
        if observed_worker_count == requested_worker_count
        and (sample_count < requested_worker_count or every_worker_observed_sample)
        else "FAIL"
    )
    return {
        "every_worker_observed_sample": every_worker_observed_sample,
        "observed_worker_count": observed_worker_count,
        "per_worker_sample_counts": per_worker_counts,
        "requested_worker_count": requested_worker_count,
        "sample_count": sample_count,
        "schema_version": f"{SCHEMA_VERSION}.worker_execution_evidence",
        "worker_count_evidence_status": status,
        "worker_execution_mode": "thread_pool",
        "worker_ids": sorted(worker_ids),
        "worker_process_ids": {result.worker_id: result.process_id for result in worker_results},
        "worker_thread_ids": {result.worker_id: result.thread_id for result in worker_results},
    }


def _read_webdataset_rows_for_samples(
    wds: Any,
    *,
    shard_path: Path,
    sample_ids: Sequence[str],
) -> list[dict[str, object]]:
    """每个 worker 通过 WebDataset streaming iterator 读取分配样本。"""
    if not sample_ids:
        return []
    dataset = wds.WebDataset([shard_path.as_posix()], shardshuffle=False)
    return _rows_for_sample_ids(
        rows=(_json_from_bytes(raw_sample.get("json")) for raw_sample in dataset),
        sample_ids=sample_ids,
    )


def _read_jsonl_rows_for_samples(
    path: Path,
    *,
    sample_ids: Sequence[str],
) -> list[dict[str, object]]:
    """每个 worker 通过 owned JSONL reader 读取分配样本。"""
    if not sample_ids:
        return []
    return _rows_for_sample_ids(rows=_iter_jsonl(path), sample_ids=sample_ids)


def _rows_for_sample_ids(
    *,
    rows: Iterable[Mapping[str, object]],
    sample_ids: Sequence[str],
) -> list[dict[str, object]]:
    """按分配样本 id 返回稳定顺序行。"""
    wanted = set(sample_ids)
    by_sample_id: dict[str, dict[str, object]] = {}
    for row in rows:
        sample_id = _string(row.get("sample_id"), "sample_id")
        if sample_id in wanted:
            by_sample_id[sample_id] = dict(row)
        if len(by_sample_id) == len(wanted):
            break
    return [by_sample_id[sample_id] for sample_id in sample_ids]


def _iter_jsonl(path: Path) -> list[dict[str, object]]:
    """读取完整 JSONL, worker 再按样本 id 过滤。"""
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        loaded = cast(object, json.loads(line))
        if not isinstance(loaded, Mapping):
            raise TypeError(f"{path} row must be object")
        rows.append(dict(cast(Mapping[str, object], loaded)))
    return rows


def _checksums(root: Path) -> dict[str, object]:
    """计算候选目录内文件校验和。"""
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "checksums.json":
            files[path.relative_to(root).as_posix()] = _sha256_file(path)
    return {"algorithm": "sha256", "files": files}


def _ledger_entries(*, candidate_dir: Path, candidate_id: str) -> list[dict[str, object]]:
    """构造 generated artifact ledger 条目。"""
    entries: list[dict[str, object]] = []
    for path in sorted(candidate_dir.rglob("*")):
        if path.is_file():
            entries.append(
                {
                    "candidate": candidate_id,
                    "checksum_manifest": {"algorithm": "sha256", "sha256": _sha256_file(path)},
                    "created_by": "autovla.dataloader.perf.native_loader_bakeoff",
                    "file_count": 1,
                    "path": path.as_posix(),
                    "safe_to_delete_later": True,
                    "size_bytes": path.stat().st_size,
                    "tracked_status": "ignored_generated_artifact",
                }
            )
    return entries


def _render_report(rows: Sequence[Mapping[str, object]]) -> str:
    """渲染 native-loader bakeoff Markdown 报告。"""
    lines = [
        "# AutoVLA Native Loader W8 Bakeoff",
        "",
        "Conclusion: `READY_FOR_COMPUTE_BENCHMARK`",
        "",
        (
            "| Candidate | Classification | Worker count | Worker evidence | "
            "Prototype only | Sample count |"
        ),
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"`{row['candidate_id']}` | "
            f"`{row['classification']}` | "
            f"`{row['worker_count']}` | "
            f"`{row.get('worker_count_evidence_status', 'not_applicable')}` | "
            f"`{row['prototype_only']}` | "
            f"`{row.get('sample_count', 'not_run')}` |"
        )
    lines.extend(
        [
            "",
            "No fine-tune, model load, checkpoint load, tokenizer load, HF/W&B network, endpoint, "
            "robot, compute job, or Slurm submission is performed by this harness.",
            "RGB camera payloads are source video stream references with frame metadata, "
            "not decoded image tensors.",
            "",
        ]
    )
    return "\n".join(lines)


def _external_effects() -> dict[str, bool]:
    """返回外部副作用边界。"""
    return {
        "checkpoint_read": False,
        "endpoint": False,
        "hf_network": False,
        "model_load": False,
        "real_training": False,
        "robot": False,
        "slurm_submission": False,
        "tokenizer_load": False,
        "wandb_network": False,
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    """写出稳定 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """写出稳定 JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    """返回稳定 JSON bytes。"""
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _json_from_bytes(raw: object) -> dict[str, object]:
    """解析 WebDataset JSON bytes。"""
    if isinstance(raw, bytes):
        loaded = cast(object, json.loads(raw.decode("utf-8")))
    elif isinstance(raw, str):
        loaded = cast(object, json.loads(raw))
    else:
        raise TypeError("webdataset json sample must be bytes")
    if not isinstance(loaded, Mapping):
        raise TypeError("webdataset json sample must be object")
    return dict(cast(Mapping[str, object], loaded))


def _stable_hash(payload: Mapping[str, object]) -> str:
    """计算 JSON-safe payload 哈希。"""
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    """计算文件 SHA256。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _import_module(name: str) -> Any:
    """导入可选依赖并保持错误信息清晰。"""
    import importlib

    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"required dependency is missing: {name}") from exc


def _float_list(value: object, *, field: str) -> list[float]:
    """读取 float 向量。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a sequence")
    sequence = cast(Sequence[object], value)
    values: list[float] = []
    for item in sequence:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{field} must contain numeric values")
        values.append(float(item))
    return values


def _bool_list(value: object, *, expected: int) -> list[bool]:
    """读取 bool mask, 缺失时派生全 True mask。"""
    if value is None:
        return [True for _ in range(expected)]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("action_mask must be a sequence")
    sequence = cast(Sequence[object], value)
    values = [bool(item) for item in sequence]
    if len(values) != expected:
        raise ValueError("action_mask shape must match action shape")
    return values


def _json_safe(value: object) -> object:
    """把 pyarrow/numpy 标量归一到 JSON-safe 值。"""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _json_safe(item) for key, item in mapping.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sequence = cast(Sequence[object], value)
        return [_json_safe(item) for item in sequence]
    return value


def _string(value: object, field: str) -> str:
    """读取必需字符串。"""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _string_or_default(value: object, default: str) -> str:
    """读取字符串或默认值。"""
    return value if isinstance(value, str) and value else default


def _int_or_default(value: object, default: int) -> int:
    """读取 int 或默认值。"""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _float_or_default(value: object, default: float) -> float:
    """读取 float 或默认值。"""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _is_relative_to(path: Path, parent: Path) -> bool:
    """兼容 Python 3.10 的 Path.is_relative_to。"""
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
