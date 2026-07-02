"""AutoVLA 数据格式流水线实现。"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import math
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, cast

import numpy as np

from autovla.dataloader.format_pipeline.contracts import (
    BENCHMARK_PAYLOAD_SCHEMA_VERSION,
    DATA_FORMAT_PIPELINE_SCHEMA_VERSION,
    FormatCandidateManifest,
    FormatPipelineConfig,
    FormatPipelineResult,
)
from autovla.dataloader.perf.native_loader_timing_v2 import (
    FrameMaterialization,
    FrameRequest,
    discover_ffmpeg_tools,
    materialize_frame_with_ffmpeg,
    resolve_source_video_path,
)

CAMERA_STREAMS = (
    "observation.images.left_wrist_rgb",
    "observation.images.head_rgb",
    "observation.images.right_wrist_rgb",
)
PAYLOAD_CONTRACT = {
    "action": "required",
    "action_mask": "required_or_derivable",
    "camera.rgb_0": "materialized_rgb_proof_and_bytes",
    "camera.rgb_1": "materialized_rgb_proof_and_bytes",
    "camera.rgb_2": "materialized_rgb_proof_and_bytes",
    "language": "required",
    "payload_hash": "deterministic",
    "state": "required_when_source_has_state",
}
EXTERNAL_EFFECTS = {
    "checkpoint_load": False,
    "endpoint": False,
    "hf_network": False,
    "model_load": False,
    "real_training": False,
    "robot": False,
    "source_dataset_mutation": False,
    "tokenizer_load": False,
    "wandb_network": False,
}

FrameMaterializer = Callable[[FrameRequest], FrameMaterialization]


@dataclass(frozen=True, slots=True)
class SourceRow:
    """保存一个有界 source sample 的数据和三路 frame 请求。"""

    action: list[float]
    action_mask: list[bool]
    episode_id: str
    episode_index: int
    frame_index: int
    frame_requests: tuple[FrameRequest, FrameRequest, FrameRequest]
    language: str
    sample_id: str
    state: list[float]
    timestamp: float
    window_id: str


@dataclass(frozen=True, slots=True)
class MaterializedSample:
    """保存一个 candidate sample 的 payload 与 RGB bytes。"""

    payload: dict[str, object]
    rgb_blobs: tuple[bytes, bytes, bytes]


def build_validate_benchmark_pipeline(config: FormatPipelineConfig) -> FormatPipelineResult:
    """执行 build、validate、benchmark 的完整流水线。"""
    build_format_pipeline(config)
    validate_format_pipeline(config)
    return benchmark_format_pipeline(config)


def build_format_pipeline(config: FormatPipelineConfig) -> FormatPipelineResult:
    """构建所有请求的数据格式候选。"""
    _prepare_roots(config)
    rows = _read_source_rows(config)
    materializer = _frame_materializer(config)
    manifests: list[FormatCandidateManifest] = []
    for candidate in config.candidates:
        if candidate == "raw_zjh_lerobot_v21_baseline":
            manifests.append(_build_raw_baseline(config, rows))
        elif candidate == "webdataset_native":
            samples = _materialize_samples(candidate, rows, materializer)
            manifests.append(_build_webdataset_native(config, rows, samples))
        elif candidate == "robodm_style":
            samples = _materialize_samples(candidate, rows, materializer)
            manifests.append(_build_robodm_style(config, rows, samples))
        elif candidate == "lerobot_v3":
            manifests.append(_build_lerobot_v3_blocked(config, rows))
        else:  # pragma: no cover - FormatPipelineConfig 已校验
            raise ValueError(f"unsupported candidate: {candidate}")
    ledger = _write_generated_artifact_ledger(config, manifests)
    result_json = _write_pipeline_result(
        config=config,
        manifests=manifests,
        phase="build",
        benchmark_rows=[],
        validation_rows=[],
    )
    report = _write_validation_report(
        config=config,
        manifests=manifests,
        benchmark_rows=[],
        validation_rows=[],
        phase="build",
    )
    return _result(config, manifests, ledger, result_json, report)


def validate_format_pipeline(config: FormatPipelineConfig) -> FormatPipelineResult:
    """验证已生成的数据格式候选。"""
    manifests = _load_candidate_manifests(config)
    validation_rows: list[dict[str, object]] = []
    for manifest in manifests:
        payload = manifest.payload
        candidate = _string(payload.get("format_name"), "format_name")
        if payload.get("build_status") == "NOT_RUN_DEPENDENCY_BLOCKED":
            validation_rows.append(_validation_row(candidate, "NOT_RUN_DEPENDENCY_BLOCKED"))
            continue
        _validate_common_manifest(payload)
        root = Path(_string(payload.get("generated_artifact_root"), "generated_artifact_root"))
        _reject_symlink_only_output(root)
        if candidate == "raw_zjh_lerobot_v21_baseline":
            validation_rows.append(_validation_row(candidate, "PASS"))
        elif candidate == "webdataset_native":
            validation_rows.append(_validate_webdataset_store(root))
        elif candidate == "robodm_style":
            validation_rows.append(_validate_robodm_style_store(root))
        else:
            validation_rows.append(_validation_row(candidate, "FAIL_VALIDATION"))
    ledger = _write_generated_artifact_ledger(config, manifests)
    result_json = _write_pipeline_result(
        config=config,
        manifests=manifests,
        phase="validate",
        benchmark_rows=[],
        validation_rows=validation_rows,
    )
    report = _write_validation_report(
        config=config,
        manifests=manifests,
        benchmark_rows=[],
        validation_rows=validation_rows,
        phase="validate",
    )
    return _result(config, manifests, ledger, result_json, report)


def benchmark_format_pipeline(config: FormatPipelineConfig) -> FormatPipelineResult:
    """对已生成的数据格式候选运行有界读取 benchmark。"""
    manifests = _load_candidate_manifests(config)
    rows = _read_source_rows(config)
    materializer = _frame_materializer(config)
    benchmark_rows: list[dict[str, object]] = []
    validation_rows: list[dict[str, object]] = []
    for manifest in manifests:
        candidate = manifest.candidate_id
        payload = manifest.payload
        if payload.get("build_status") == "NOT_RUN_DEPENDENCY_BLOCKED":
            benchmark_rows.append(
                {
                    "benchmark_status": "NOT_RUN_DEPENDENCY_BLOCKED",
                    "candidate": candidate,
                    "missing_metrics": ["candidate_not_run"],
                    "not_run_reason": payload.get("not_run_reason", "dependency blocked"),
                }
            )
            validation_rows.append(_validation_row(candidate, "NOT_RUN_DEPENDENCY_BLOCKED"))
            continue
        if candidate == "raw_zjh_lerobot_v21_baseline":
            benchmark_rows.append(
                _time_reader(
                    candidate=candidate,
                    config=config,
                    episode_count=_episode_count(rows),
                    sample_count=len(rows),
                    read_batch=lambda indices, current_candidate=candidate: [
                        _materialize_sample(current_candidate, rows[index], materializer).payload
                        for index in indices
                    ],
                )
            )
            validation_rows.append(_validation_row(candidate, "PASS"))
        elif candidate == "webdataset_native":
            store_root = Path(
                _string(payload["generated_artifact_root"], "generated_artifact_root")
            )
            benchmark_rows.append(
                _time_reader(
                    candidate=candidate,
                    config=config,
                    episode_count=_int(payload["episode_count"], "episode_count"),
                    sample_count=_int(payload["sample_count"], "sample_count"),
                    read_batch=lambda indices, current_root=store_root: _read_webdataset_samples(
                        current_root, indices
                    ),
                )
            )
            validation_rows.append(_validate_webdataset_store(store_root))
        elif candidate == "robodm_style":
            store_root = Path(
                _string(payload["generated_artifact_root"], "generated_artifact_root")
            )
            benchmark_rows.append(
                _time_reader(
                    candidate=candidate,
                    config=config,
                    episode_count=_int(payload["episode_count"], "episode_count"),
                    sample_count=_int(payload["sample_count"], "sample_count"),
                    read_batch=lambda indices, current_root=store_root: _read_robodm_style_samples(
                        current_root, indices
                    ),
                )
            )
            validation_rows.append(_validate_robodm_style_store(store_root))
    ledger = _write_generated_artifact_ledger(config, manifests)
    result_json = _write_pipeline_result(
        config=config,
        manifests=manifests,
        phase="benchmark",
        benchmark_rows=benchmark_rows,
        validation_rows=validation_rows,
    )
    report = _write_validation_report(
        config=config,
        manifests=manifests,
        benchmark_rows=benchmark_rows,
        validation_rows=validation_rows,
        phase="benchmark",
    )
    return _result(config, manifests, ledger, result_json, report)


def validate_benchmark_payload(payload: Mapping[str, object]) -> None:
    """验证 BenchmarkPayload 字段完整且三路 RGB 已物化。"""
    required = ("action", "language", "payload_hash", "sample_id", "source_backend")
    for field in required:
        if payload.get(field) in (None, "", []):
            raise ValueError(f"{field} is required")
    if payload.get("payload_missing_fields") not in ([], ()):
        raise ValueError("payload_missing_fields must be []")
    for field in ("action", "state"):
        values = payload.get(field)
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise ValueError(f"{field} must be a sequence")
    mask = payload.get("action_mask")
    if not isinstance(mask, Sequence) or isinstance(mask, (str, bytes)):
        raise ValueError("action_mask must be a sequence")
    for item in cast(Sequence[object], mask):
        if not isinstance(item, bool):
            raise ValueError("action_mask must be bool-only")
    for index in range(3):
        proof = _mapping(payload.get(f"camera.rgb_{index}"), f"camera.rgb_{index}")
        shape = _int_list(proof.get("shape"), f"camera.rgb_{index}.shape")
        if len(shape) != 3 or shape[2] != 3:
            raise ValueError(f"camera.rgb_{index} must have RGB shape [H,W,3]")
        byte_length = _positive_int(proof.get("byte_length"), f"camera.rgb_{index}.byte_length")
        if byte_length != shape[0] * shape[1] * shape[2]:
            raise ValueError(f"camera.rgb_{index} byte_length does not match shape")
        if proof.get("dtype") != "uint8":
            raise ValueError(f"camera.rgb_{index} dtype must be uint8")
        if not isinstance(proof.get("sha256"), str) or not proof["sha256"]:
            raise ValueError(f"camera.rgb_{index} sha256 is required")


def _prepare_roots(config: FormatPipelineConfig) -> None:
    """创建输出目录并再次保护 source root。"""
    if not config.source_dataset.is_dir():
        raise FileNotFoundError(f"source dataset does not exist: {config.source_dataset}")
    config.working_root.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)


def _frame_materializer(config: FormatPipelineConfig) -> FrameMaterializer:
    """选择真实 ffmpeg 或 tiny-fixture synthetic materializer。"""
    if config.materializer == "synthetic":

        def _synthetic(request: FrameRequest) -> FrameMaterialization:
            """生成确定性 RGB bytes, 仅用于 tiny fixture。"""
            seed = f"{request.sample_id}:{request.stream_key}:{request.frame_index}".encode("utf-8")
            raw = (seed * ((request.width * request.height * 3 // len(seed)) + 1))[
                : request.width * request.height * 3
            ]
            return FrameMaterialization(
                byte_length=len(raw),
                dtype="uint8",
                height=request.height,
                rgb_bytes=raw,
                sha256=hashlib.sha256(raw).hexdigest(),
                width=request.width,
            )

        return _synthetic
    tools = discover_ffmpeg_tools()

    def _ffmpeg(request: FrameRequest) -> FrameMaterialization:
        """用 ffmpeg 读取 source video frame。"""
        return materialize_frame_with_ffmpeg(request, tools=tools)

    return _ffmpeg


def _read_source_rows(config: FormatPipelineConfig) -> list[SourceRow]:
    """读取 LeRobot-v2.1/ZJH parquet source rows。"""
    metadata = _read_metadata(config.source_dataset)
    tasks = _read_tasks(config.source_dataset)
    cameras = _camera_specs(metadata)
    parquet_module = importlib.import_module("pyarrow.parquet")
    rows: list[SourceRow] = []
    episode_ids: set[int] = set()
    for parquet_path in sorted((config.source_dataset / "data").glob("chunk-*/*.parquet")):
        table = parquet_module.read_table(parquet_path)
        for raw in _iter_table_rows(table):
            episode_index = _int(raw.get("episode_index"), "episode_index")
            if episode_index not in episode_ids and len(episode_ids) >= config.max_episodes:
                continue
            episode_ids.add(episode_index)
            rows.append(
                _source_row(
                    cameras=cameras,
                    metadata=metadata,
                    raw=raw,
                    source_dataset=config.source_dataset,
                    tasks=tasks,
                )
            )
            if len(rows) >= config.max_samples:
                return rows
    if not rows:
        raise ValueError("data format pipeline requires source parquet rows")
    return rows


def _source_row(
    *,
    cameras: Sequence[Mapping[str, object]],
    metadata: Mapping[str, object],
    raw: Mapping[str, object],
    source_dataset: Path,
    tasks: Mapping[int, str],
) -> SourceRow:
    """把 source row 解析为有界样本。"""
    action = _float_list(raw.get("action"), "action")
    state = _float_list(raw.get("observation.state", raw.get("state")), "state")
    action_mask = _bool_list(raw.get("action_mask"), expected=len(action))
    sample_index = _int(raw.get("index"), "index")
    episode_index = _int(raw.get("episode_index"), "episode_index")
    frame_index = _int(raw.get("frame_index"), "frame_index")
    timestamp = _float(raw.get("timestamp"), "timestamp")
    task_index = _int(raw.get("task_index", 0), "task_index")
    language = _string(raw.get("language", tasks.get(task_index, "zjh task")), "language")
    sample_id = f"sample-{sample_index:09d}"
    episode_id = f"episode-{episode_index:06d}"
    requests = tuple(
        _frame_request(
            camera=camera,
            episode_index=episode_index,
            frame_index=frame_index,
            metadata=metadata,
            sample_id=sample_id,
            source_dataset=source_dataset,
            timestamp=timestamp,
        )
        for camera in cameras
    )
    if len(requests) != 3:
        raise ValueError("exactly three RGB camera streams are required")
    return SourceRow(
        action=action,
        action_mask=action_mask,
        episode_id=episode_id,
        episode_index=episode_index,
        frame_index=frame_index,
        frame_requests=requests,
        language=language,
        sample_id=sample_id,
        state=state,
        timestamp=timestamp,
        window_id=f"{episode_id}:{sample_id}:{frame_index}",
    )


def _frame_request(
    *,
    camera: Mapping[str, object],
    episode_index: int,
    frame_index: int,
    metadata: Mapping[str, object],
    sample_id: str,
    source_dataset: Path,
    timestamp: float,
) -> FrameRequest:
    """构造单路 frame 请求。"""
    stream_key = _string(camera.get("stream_key"), "stream_key")
    template = _string(metadata.get("video_path"), "video_path")
    relative_video = template.format(
        episode_chunk=episode_index // 1000,
        episode_index=episode_index,
        video_key=stream_key,
    )
    return FrameRequest(
        frame_index=frame_index,
        height=_positive_int(camera.get("height"), "camera height"),
        sample_id=sample_id,
        stream_key=stream_key,
        timestamp_s=timestamp,
        video_path=resolve_source_video_path(source_dataset, relative_video),
        width=_positive_int(camera.get("width"), "camera width"),
    )


def _materialize_samples(
    candidate: str,
    rows: Sequence[SourceRow],
    materializer: FrameMaterializer,
) -> list[MaterializedSample]:
    """为候选构造物化样本。"""
    return [_materialize_sample(candidate, row, materializer) for row in rows]


def _materialize_sample(
    candidate: str,
    row: SourceRow,
    materializer: FrameMaterializer,
) -> MaterializedSample:
    """构造单个 BenchmarkPayload。"""
    camera_payloads: dict[str, object] = {}
    rgb_blobs: list[bytes] = []
    for index, request in enumerate(row.frame_requests):
        materialized = materializer(request)
        camera_payloads[f"camera.rgb_{index}"] = materialized.proof()
        rgb_blobs.append(materialized.rgb_bytes)
    payload: dict[str, object] = {
        "action": row.action,
        "action_mask": row.action_mask,
        **camera_payloads,
        "episode_id": row.episode_id,
        "frame_index": row.frame_index,
        "language": row.language,
        "payload_missing_fields": [],
        "sample_id": row.sample_id,
        "source_backend": candidate,
        "state": row.state,
        "timestamp": row.timestamp,
        "window_id": row.window_id,
    }
    payload["payload_hash"] = _stable_hash(payload)
    validate_benchmark_payload(payload)
    return MaterializedSample(
        payload=payload,
        rgb_blobs=(rgb_blobs[0], rgb_blobs[1], rgb_blobs[2]),
    )


def _build_raw_baseline(
    config: FormatPipelineConfig,
    rows: Sequence[SourceRow],
) -> FormatCandidateManifest:
    """写出 raw baseline manifest, 不复制 source payload。"""
    root = config.working_root / "raw_zjh_lerobot_v21_baseline"
    root.mkdir(parents=True, exist_ok=True)
    manifest = _common_manifest(
        action_dim=len(rows[0].action),
        build_status="PASS",
        candidate="raw_zjh_lerobot_v21_baseline",
        config=config,
        conversion_time_s=0.0,
        episode_count=_episode_count(rows),
        generated_root=root,
        loader_name="raw_zjh_lerobot_v21_source_baseline",
        loader_version="autovla-owned-v1",
        sample_count=len(rows),
        state_dim=len(rows[0].state),
    )
    manifest["dependency_mode"] = "no_new_dependency"
    manifest["storage_layout"] = "source_baseline_no_generated_payload_copy"
    path = root / "raw_baseline_manifest.json"
    _write_manifest_with_stats(path, root, manifest)
    return FormatCandidateManifest("raw_zjh_lerobot_v21_baseline", path, manifest)


def _build_webdataset_native(
    config: FormatPipelineConfig,
    rows: Sequence[SourceRow],
    samples: Sequence[MaterializedSample],
) -> FormatCandidateManifest:
    """构建 WebDataset-native store。"""
    started = time.perf_counter()
    root = config.working_root / "webdataset_store"
    shard_root = root / "shards"
    shard_root.mkdir(parents=True, exist_ok=True)
    wds_module: Any = importlib.import_module("webdataset")
    sample_index: list[dict[str, object]] = []
    for shard_index, chunk in enumerate(_chunks(samples, config.samples_per_shard)):
        shard_path = shard_root / f"shard-{shard_index:06d}.tar"
        with wds_module.TarWriter(shard_path.as_posix(), mtime=0) as sink:
            for local_index, sample in enumerate(chunk):
                global_index = shard_index * config.samples_per_shard + local_index
                payload = sample.payload
                key = _string(payload["sample_id"], "sample_id")
                sink.write(
                    {
                        "__key__": key,
                        "metadata.json": _json_bytes(_payload_metadata(payload)),
                        "sample_source.json": _json_bytes(_sample_source(payload)),
                        "language.txt": _string(payload["language"], "language").encode("utf-8"),
                        "action.npy": _npy_bytes(payload["action"]),
                        "action_mask.npy": _npy_bytes(payload["action_mask"]),
                        "state.npy": _npy_bytes(payload["state"]),
                        "payload.json": _json_bytes(payload),
                        "rgb_0.bin": sample.rgb_blobs[0],
                        "rgb_1.bin": sample.rgb_blobs[1],
                        "rgb_2.bin": sample.rgb_blobs[2],
                    }
                )
                sample_index.append(
                    {
                        "global_index": global_index,
                        "key": key,
                        "payload_hash": payload["payload_hash"],
                        "shard": shard_path.relative_to(root).as_posix(),
                    }
                )
    _write_jsonl(root / "sample_index.jsonl", sample_index)
    _write_jsonl(root / "episode_index.jsonl", _episode_index_rows(rows))
    _write_json(root / "modality.json", _modality_payload(rows))
    conversion_time_s = _elapsed_s(started)
    _write_json(root / "conversion_report.json", {"candidate": "webdataset_native"})
    _write_json(root / "read_validation_report.json", {"candidate": "webdataset_native"})
    checksums = _write_checksums(
        root,
        exclude_names={"checksums.json", "webdataset_store_manifest.json"},
    )
    manifest = _common_manifest(
        action_dim=len(rows[0].action),
        build_status="PASS",
        candidate="webdataset_native",
        config=config,
        conversion_time_s=conversion_time_s,
        episode_count=_episode_count(rows),
        generated_root=root,
        loader_name="webdataset_package_tar_reader",
        loader_version="webdataset==1.0.2",
        sample_count=len(samples),
        state_dim=len(rows[0].state),
    )
    manifest["checksums"] = checksums
    manifest["dependency_mode"] = "webdataset_package"
    manifest["storage_layout"] = "webdataset_store"
    path = root / "webdataset_store_manifest.json"
    _write_manifest_with_stats(path, root, manifest)
    _write_json(root / "conversion_report.json", _conversion_report(manifest))
    _write_json(
        root / "read_validation_report.json",
        _validation_row("webdataset_native", "PENDING"),
    )
    checksums = _write_checksums(
        root,
        exclude_names={"checksums.json", "webdataset_store_manifest.json"},
    )
    manifest["checksums"] = checksums
    _write_manifest_with_stats(path, root, manifest)
    return FormatCandidateManifest("webdataset_native", path, manifest)


def _build_robodm_style(
    config: FormatPipelineConfig,
    rows: Sequence[SourceRow],
    samples: Sequence[MaterializedSample],
) -> FormatCandidateManifest:
    """构建 AutoVLA-native Robo-DM-style store。"""
    started = time.perf_counter()
    root = config.working_root / "robodm_style_store"
    container_root = root / "containers"
    container_root.mkdir(parents=True, exist_ok=True)
    sample_index: list[dict[str, object]] = []
    for container_index, chunk in enumerate(_chunks(samples, config.samples_per_shard)):
        container_path = container_root / f"container-{container_index:06d}.vla"
        with tarfile.open(container_path, "w") as archive:
            for local_index, sample in enumerate(chunk):
                global_index = container_index * config.samples_per_shard + local_index
                payload = sample.payload
                prefix = _string(payload["sample_id"], "sample_id")
                _tar_add_bytes(
                    archive,
                    f"{prefix}/metadata.json",
                    _json_bytes(_payload_metadata(payload)),
                )
                _tar_add_bytes(
                    archive,
                    f"{prefix}/sample_source.json",
                    _json_bytes(_sample_source(payload)),
                )
                _tar_add_bytes(archive, f"{prefix}/payload.json", _json_bytes(payload))
                _tar_add_bytes(
                    archive,
                    f"{prefix}/language.txt",
                    _string(payload["language"], "language").encode("utf-8"),
                )
                _tar_add_bytes(archive, f"{prefix}/action.npy", _npy_bytes(payload["action"]))
                _tar_add_bytes(
                    archive,
                    f"{prefix}/action_mask.npy",
                    _npy_bytes(payload["action_mask"]),
                )
                _tar_add_bytes(archive, f"{prefix}/state.npy", _npy_bytes(payload["state"]))
                for camera_index, blob in enumerate(sample.rgb_blobs):
                    _tar_add_bytes(archive, f"{prefix}/rgb_{camera_index}.bin", blob)
                sample_index.append(
                    {
                        "container": container_path.relative_to(root).as_posix(),
                        "global_index": global_index,
                        "member_prefix": prefix,
                        "payload_hash": payload["payload_hash"],
                    }
                )
    _write_jsonl(root / "sample_index.jsonl", sample_index)
    _write_jsonl(root / "episode_index.jsonl", _episode_index_rows(rows))
    _write_json(root / "modality.json", _modality_payload(rows))
    conversion_time_s = _elapsed_s(started)
    _write_json(root / "conversion_report.json", {"candidate": "robodm_style"})
    _write_json(root / "read_validation_report.json", {"candidate": "robodm_style"})
    checksums = _write_checksums(
        root,
        exclude_names={"checksums.json", "robodm_style_manifest.json"},
    )
    manifest = _common_manifest(
        action_dim=len(rows[0].action),
        build_status="PASS",
        candidate="robodm_style",
        config=config,
        conversion_time_s=conversion_time_s,
        episode_count=_episode_count(rows),
        generated_root=root,
        loader_name="autovla_owned_robodm_style_container_reader",
        loader_version="autovla-owned-v1",
        sample_count=len(samples),
        state_dim=len(rows[0].state),
    )
    manifest["checksums"] = checksums
    manifest["dependency_mode"] = "autovla_owned_no_upstream_robodm_package"
    manifest["prototype_only"] = False
    manifest["storage_layout"] = "robodm_style_store"
    path = root / "robodm_style_manifest.json"
    _write_manifest_with_stats(path, root, manifest)
    _write_json(root / "conversion_report.json", _conversion_report(manifest))
    _write_json(root / "read_validation_report.json", _validation_row("robodm_style", "PENDING"))
    checksums = _write_checksums(
        root,
        exclude_names={"checksums.json", "robodm_style_manifest.json"},
    )
    manifest["checksums"] = checksums
    _write_manifest_with_stats(path, root, manifest)
    return FormatCandidateManifest("robodm_style", path, manifest)


def _build_lerobot_v3_blocked(
    config: FormatPipelineConfig,
    rows: Sequence[SourceRow],
) -> FormatCandidateManifest:
    """记录 LeRobot v3 依赖阻塞决策, 不生成伪 v3 store。"""
    root = config.working_root / "lerobot_v3_store"
    root.mkdir(parents=True, exist_ok=True)
    manifest = _common_manifest(
        action_dim=len(rows[0].action),
        build_status="NOT_RUN_DEPENDENCY_BLOCKED",
        candidate="lerobot_v3",
        config=config,
        conversion_time_s=0.0,
        episode_count=_episode_count(rows),
        generated_root=root,
        loader_name="not_run_lerobot_v3_dependency_blocked",
        loader_version="not_run",
        sample_count=len(rows),
        state_dim=len(rows[0].state),
    )
    manifest["dependency_mode"] = "actual_lerobot_package_not_approved"
    manifest["not_run_reason"] = (
        "actual LeRobot v3 package/version/native-loader route is not approved in this task"
    )
    manifest["storage_layout"] = "dependency_decision_only"
    path = root / "lerobot_v3_manifest.json"
    _write_manifest_with_stats(path, root, manifest)
    _write_json(root / "dependency_decision.json", manifest)
    _write_manifest_with_stats(path, root, manifest)
    return FormatCandidateManifest("lerobot_v3", path, manifest)


def _common_manifest(
    *,
    action_dim: int,
    build_status: str,
    candidate: str,
    config: FormatPipelineConfig,
    conversion_time_s: float,
    episode_count: int,
    generated_root: Path,
    loader_name: str,
    loader_version: str,
    sample_count: int,
    state_dim: int,
) -> dict[str, object]:
    """构造公共 manifest 字段。"""
    artifact_stats = _artifact_stats(generated_root)
    return {
        "action_dim": action_dim,
        "action_mask_policy": "source_mask_or_bool_all_true_derivable",
        "build_status": build_status,
        "camera_stream_count": 3,
        "checksums": {},
        "conversion_command": "python -m autovla.dataloader.format_pipeline",
        "conversion_time_s": round(conversion_time_s, 6),
        "episode_count": episode_count,
        "external_effects": dict(EXTERNAL_EFFECTS),
        "format_name": candidate,
        "format_version": "v1",
        "generated_artifact_root": generated_root.as_posix(),
        "generated_artifact_size_bytes": artifact_stats["total_size_bytes"],
        "generated_artifacts_tracked": False,
        "generated_file_count": artifact_stats["file_count"],
        "language_present": True,
        "loader_name": loader_name,
        "loader_version": loader_version,
        "no_model_load": True,
        "no_source_mutation": True,
        "no_checkpoint_load": True,
        "no_endpoint": True,
        "no_hf_network": True,
        "no_robot": True,
        "no_tokenizer_load": True,
        "no_training": True,
        "no_wandb_network": True,
        "payload_contract": dict(PAYLOAD_CONTRACT),
        "sample_count": sample_count,
        "schema_version": DATA_FORMAT_PIPELINE_SCHEMA_VERSION,
        "source_dataset_fingerprint": _source_fingerprint(config.source_dataset),
        "source_dataset_path": config.source_dataset.as_posix(),
        "state_dim": state_dim,
        "worker_count": config.worker_count,
    }


def _validate_common_manifest(payload: Mapping[str, object]) -> None:
    """验证公共 manifest 字段完整。"""
    required = (
        "schema_version",
        "format_name",
        "format_version",
        "source_dataset_path",
        "source_dataset_fingerprint",
        "conversion_command",
        "conversion_time_s",
        "generated_artifact_root",
        "generated_file_count",
        "generated_artifact_size_bytes",
        "sample_count",
        "episode_count",
        "camera_stream_count",
        "action_dim",
        "state_dim",
        "language_present",
        "action_mask_policy",
        "loader_name",
        "loader_version",
        "payload_contract",
        "checksums",
        "no_source_mutation",
        "generated_artifacts_tracked",
        "no_training",
        "no_model_load",
    )
    for field in required:
        if field not in payload:
            raise ValueError(f"manifest missing {field}")
    if payload["schema_version"] != DATA_FORMAT_PIPELINE_SCHEMA_VERSION:
        raise ValueError("unsupported manifest schema_version")
    for field in (
        "no_source_mutation",
        "no_training",
        "no_model_load",
        "no_checkpoint_load",
        "no_tokenizer_load",
        "no_hf_network",
        "no_wandb_network",
        "no_endpoint",
        "no_robot",
    ):
        if payload[field] is not True:
            raise ValueError(f"{field} must be true")
    if payload["generated_artifacts_tracked"] is not False:
        raise ValueError("generated_artifacts_tracked must be false")
    if _positive_int(payload["camera_stream_count"], "camera_stream_count") != 3:
        raise ValueError("camera_stream_count must be 3")


def _validate_webdataset_store(root: Path) -> dict[str, object]:
    """验证 WebDataset-native store 可读且 payload 完整。"""
    manifest = _read_json(root / "webdataset_store_manifest.json")
    _validate_common_manifest(manifest)
    for relative in (
        "sample_index.jsonl",
        "episode_index.jsonl",
        "modality.json",
        "checksums.json",
        "conversion_report.json",
    ):
        if not (root / relative).is_file():
            return _validation_row("webdataset_native", "FAIL_VALIDATION", f"missing {relative}")
    payloads = _read_webdataset_samples(root, [0])
    for payload in payloads:
        validate_benchmark_payload(payload)
    report = _validation_row("webdataset_native", "PASS")
    _write_json(root / "read_validation_report.json", report)
    return report


def _validate_robodm_style_store(root: Path) -> dict[str, object]:
    """验证 Robo-DM-style store 可读且 payload 完整。"""
    manifest = _read_json(root / "robodm_style_manifest.json")
    _validate_common_manifest(manifest)
    for relative in (
        "sample_index.jsonl",
        "episode_index.jsonl",
        "modality.json",
        "checksums.json",
        "conversion_report.json",
    ):
        if not (root / relative).is_file():
            return _validation_row("robodm_style", "FAIL_VALIDATION", f"missing {relative}")
    payloads = _read_robodm_style_samples(root, [0])
    for payload in payloads:
        validate_benchmark_payload(payload)
    report = _validation_row("robodm_style", "PASS")
    _write_json(root / "read_validation_report.json", report)
    return report


def _read_webdataset_samples(root: Path, indices: Sequence[int]) -> list[dict[str, object]]:
    """通过 WebDataset package 从 shards 读取 payload。"""
    wds_module: Any = importlib.import_module("webdataset")
    index_rows = _read_jsonl(root / "sample_index.jsonl")
    selected: list[dict[str, object]] = []
    for index in indices:
        row = _mapping(index_rows[index], "sample_index row")
        shard_path = _resolve_under(root, _string(row["shard"], "shard"))
        key = _string(row["key"], "key")
        for sample_obj in wds_module.WebDataset(shard_path.as_posix(), shardshuffle=False):
            sample = _mapping(sample_obj, "webdataset sample")
            if _string(sample.get("__key__"), "__key__") == key:
                selected.append(_payload_from_webdataset_sample(sample))
                break
        else:
            raise ValueError(f"missing webdataset sample key: {key}")
    return selected


def _payload_from_webdataset_sample(sample: Mapping[str, object]) -> dict[str, object]:
    """从 WebDataset sample 还原 BenchmarkPayload。"""
    payload = dict(_mapping(json.loads(_bytes(sample["payload.json"], "payload.json")), "payload"))
    for camera_index in range(3):
        blob = _bytes(sample[f"rgb_{camera_index}.bin"], f"rgb_{camera_index}.bin")
        _verify_rgb_blob(payload, camera_index, blob)
    validate_benchmark_payload(payload)
    return payload


def _read_robodm_style_samples(root: Path, indices: Sequence[int]) -> list[dict[str, object]]:
    """从 AutoVLA-owned Robo-DM-style container 读取 payload。"""
    index_rows = _read_jsonl(root / "sample_index.jsonl")
    payloads: list[dict[str, object]] = []
    for index in indices:
        row = _mapping(index_rows[index], "sample_index row")
        container = _resolve_under(root, _string(row["container"], "container"))
        prefix = _string(row["member_prefix"], "member_prefix")
        with tarfile.open(container, "r") as archive:
            payload = dict(
                _mapping(
                    json.loads(_tar_read_bytes(archive, f"{prefix}/payload.json")),
                    "payload",
                )
            )
            for camera_index in range(3):
                _verify_rgb_blob(
                    payload,
                    camera_index,
                    _tar_read_bytes(archive, f"{prefix}/rgb_{camera_index}.bin"),
                )
        validate_benchmark_payload(payload)
        payloads.append(payload)
    return payloads


def _time_reader(
    *,
    candidate: str,
    config: FormatPipelineConfig,
    episode_count: int,
    read_batch: Callable[[Sequence[int]], list[dict[str, object]]],
    sample_count: int,
) -> dict[str, object]:
    """对候选 reader 做有界 batch timing。"""
    latencies: list[float] = []
    measured_samples = 0
    total_batches = config.warmup_batches + config.measured_batches
    started_all = time.perf_counter()
    for batch_index in range(total_batches):
        indices = _batch_indices(
            sample_count,
            batch_index=batch_index,
            batch_size=config.batch_size,
        )
        started = time.perf_counter()
        payloads = read_batch(indices)
        if len(payloads) != len(indices):
            raise ValueError(f"{candidate} returned the wrong batch size")
        for payload in payloads:
            validate_benchmark_payload(payload)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if batch_index >= config.warmup_batches:
            latencies.append(round(elapsed_ms, 6))
            measured_samples += len(payloads)
    total_s = max(time.perf_counter() - started_all, 0.000001)
    if not latencies:
        raise ValueError("benchmark requires measured latencies")
    return {
        "batch_size": config.batch_size,
        "benchmark_status": "PASS",
        "candidate": candidate,
        "episode_count": episode_count,
        "first_batch_latency_ms": latencies[0],
        "frames_per_second": round((measured_samples * 3) / total_s, 6),
        "max_batch_latency_ms": round(max(latencies), 6),
        "measured_batches": config.measured_batches,
        "missing_metrics": [],
        "p50_batch_latency_ms": round(_percentile(latencies, 50.0), 6),
        "p95_batch_latency_ms": round(_percentile(latencies, 95.0), 6),
        "sample_count": sample_count,
        "samples_per_second": round(measured_samples / total_s, 6),
        "total_measured_time_s": round(total_s, 6),
        "warmup_batches": config.warmup_batches,
        "worker_count": config.worker_count,
    }


def _write_generated_artifact_ledger(
    config: FormatPipelineConfig,
    manifests: Sequence[FormatCandidateManifest],
) -> Path:
    """写出 generated artifact ledger。"""
    entries: list[dict[str, object]] = []
    for manifest in manifests:
        root = Path(_string(manifest.payload["generated_artifact_root"], "generated_artifact_root"))
        stats = _artifact_stats(root)
        checksum_path = root / "checksums.json"
        entries.append(
            {
                "candidate": manifest.candidate_id,
                "checksum_manifest_path": (
                    checksum_path.as_posix() if checksum_path.exists() else ""
                ),
                "file_count": stats["file_count"],
                "path": root.as_posix(),
                "safe_to_delete_later": True,
                "source_dataset_modified": False,
                "total_size_bytes": stats["total_size_bytes"],
                "tracked_status": "ignored_generated_artifact",
            }
        )
    payload = {
        "entries": entries,
        "generated_artifacts_tracked": False,
        "schema_version": f"{DATA_FORMAT_PIPELINE_SCHEMA_VERSION}.generated_artifact_ledger",
        "source_dataset": config.source_dataset.as_posix(),
        "source_dataset_mutated": False,
        "task_id": "AUTOVLA-M3-DATA-FORMAT-PIPELINE-SUITE-001",
        "working_root": config.working_root.as_posix(),
    }
    path = config.output_dir / "generated-artifact-ledger.json"
    _write_json(path, payload)
    _mirror_task_root_output(config, path)
    return path


def _write_pipeline_result(
    *,
    benchmark_rows: Sequence[Mapping[str, object]],
    config: FormatPipelineConfig,
    manifests: Sequence[FormatCandidateManifest],
    phase: str,
    validation_rows: Sequence[Mapping[str, object]],
) -> Path:
    """写出 JSON 汇总。"""
    payload = {
        "benchmark_rows": [dict(row) for row in benchmark_rows],
        "candidate_manifests": [manifest.to_json_dict() for manifest in manifests],
        "candidates": list(config.candidates),
        "external_effects": dict(EXTERNAL_EFFECTS),
        "phase": phase,
        "schema_version": f"{DATA_FORMAT_PIPELINE_SCHEMA_VERSION}.result",
        "source_dataset": config.source_dataset.as_posix(),
        "source_dataset_mutated": False,
        "validation_rows": [dict(row) for row in validation_rows],
        "working_root": config.working_root.as_posix(),
    }
    path = config.output_dir / "data-format-pipeline-results.json"
    _write_json(path, payload)
    return path


def _write_validation_report(
    *,
    benchmark_rows: Sequence[Mapping[str, object]],
    config: FormatPipelineConfig,
    manifests: Sequence[FormatCandidateManifest],
    phase: str,
    validation_rows: Sequence[Mapping[str, object]],
) -> Path:
    """写出 Markdown validation report。"""
    lines = [
        "# AutoVLA Data Format Pipeline Suite",
        "",
        f"- Phase: `{phase}`",
        f"- Source dataset: `{config.source_dataset.as_posix()}`",
        f"- Working root: `{config.working_root.as_posix()}`",
        "- No training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: yes",
        "- Generated artifacts tracked: false",
        "",
        "## Candidate Manifests",
        "",
        "| Candidate | Build status | Dependency mode | Root |",
        "| --- | --- | --- | --- |",
    ]
    for manifest in manifests:
        payload = manifest.payload
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` |".format(
                manifest.candidate_id,
                payload.get("build_status", "unknown"),
                payload.get("dependency_mode", "unknown"),
                payload.get("generated_artifact_root", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Validation",
            "",
            "| Candidate | Status | Reason |",
            "| --- | --- | --- |",
        ]
    )
    for row in validation_rows:
        lines.append(
            "| `{}` | `{}` | `{}` |".format(
                row.get("candidate", ""),
                row.get("validation_status", ""),
                row.get("reason", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Benchmark",
            "",
            "| Candidate | Status | p50 ms | p95 ms | max ms | samples/s |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in benchmark_rows:
        lines.append(
            "| `{}` | `{}` | {} | {} | {} | {} |".format(
                row.get("candidate", ""),
                row.get("benchmark_status", ""),
                row.get("p50_batch_latency_ms", "not_run"),
                row.get("p95_batch_latency_ms", "not_run"),
                row.get("max_batch_latency_ms", "not_run"),
                row.get("samples_per_second", "not_run"),
            )
        )
    path = config.output_dir / "data-format-pipeline-validation.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _mirror_task_root_output(config, path)
    return path


def _result(
    config: FormatPipelineConfig,
    manifests: Sequence[FormatCandidateManifest],
    ledger: Path,
    result_json: Path,
    report: Path,
) -> FormatPipelineResult:
    """构造返回对象。"""
    return FormatPipelineResult(
        candidate_manifests=tuple(manifests),
        generated_artifact_ledger=ledger,
        output_dir=config.output_dir,
        result_json=result_json,
        validation_report=report,
    )


def _load_candidate_manifests(config: FormatPipelineConfig) -> list[FormatCandidateManifest]:
    """从 working root 读取候选 manifest。"""
    paths = {
        "raw_zjh_lerobot_v21_baseline": (
            config.working_root / "raw_zjh_lerobot_v21_baseline" / "raw_baseline_manifest.json"
        ),
        "webdataset_native": (
            config.working_root / "webdataset_store" / "webdataset_store_manifest.json"
        ),
        "robodm_style": config.working_root / "robodm_style_store" / "robodm_style_manifest.json",
        "lerobot_v3": config.working_root / "lerobot_v3_store" / "lerobot_v3_manifest.json",
    }
    manifests: list[FormatCandidateManifest] = []
    for candidate in config.candidates:
        path = paths[candidate]
        if not path.is_file():
            raise FileNotFoundError(f"missing manifest for {candidate}: {path}")
        manifests.append(FormatCandidateManifest(candidate, path, _read_json(path)))
    return manifests


def _validation_row(candidate: str, status: str, reason: str = "") -> dict[str, object]:
    """构造 validation row。"""
    return {
        "candidate": candidate,
        "reason": reason,
        "validation_status": status,
    }


def _payload_metadata(payload: Mapping[str, object]) -> dict[str, object]:
    """返回 sample metadata。"""
    return {
        "episode_id": payload["episode_id"],
        "payload_hash": payload["payload_hash"],
        "sample_id": payload["sample_id"],
        "schema_version": BENCHMARK_PAYLOAD_SCHEMA_VERSION,
        "source_backend": payload["source_backend"],
        "window_id": payload["window_id"],
    }


def _sample_source(payload: Mapping[str, object]) -> dict[str, object]:
    """返回样本 provenance。"""
    return {
        "episode_id": payload["episode_id"],
        "frame_index": payload["frame_index"],
        "sample_id": payload["sample_id"],
        "timestamp": payload["timestamp"],
    }


def _modality_payload(rows: Sequence[SourceRow]) -> dict[str, object]:
    """返回 modality 描述。"""
    return {
        "action_dim": len(rows[0].action),
        "action_mask_policy": "source_mask_or_bool_all_true_derivable",
        "camera_stream_count": 3,
        "language_present": True,
        "state_dim": len(rows[0].state),
    }


def _conversion_report(manifest: Mapping[str, object]) -> dict[str, object]:
    """返回 conversion report。"""
    return {
        "build_status": manifest["build_status"],
        "candidate": manifest["format_name"],
        "conversion_time_s": manifest["conversion_time_s"],
        "generated_artifact_root": manifest["generated_artifact_root"],
        "no_checkpoint_load": True,
        "no_hf_network": True,
        "no_model_load": True,
        "no_source_mutation": True,
        "no_training": True,
        "no_wandb_network": True,
    }


def _episode_index_rows(rows: Sequence[SourceRow]) -> list[dict[str, object]]:
    """返回 episode index rows。"""
    episodes: dict[str, int] = {}
    for row in rows:
        episodes[row.episode_id] = episodes.get(row.episode_id, 0) + 1
    return [
        {
            "episode_id": episode_id,
            "sample_count": count,
        }
        for episode_id, count in sorted(episodes.items())
    ]


def _write_checksums(root: Path, *, exclude_names: set[str] | None = None) -> dict[str, object]:
    """写出 root 下文件 checksum manifest。"""
    excluded = exclude_names or {"checksums.json"}
    checksums: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in excluded:
            checksums[path.relative_to(root).as_posix()] = _sha256(path)
    _write_json(root / "checksums.json", checksums)
    return checksums


def _reject_symlink_only_output(root: Path) -> None:
    """拒绝 symlink-only 或 symlink artifact 输出。"""
    if not root.exists():
        raise ValueError(f"generated root missing: {root}")
    files = [path for path in root.rglob("*") if path.is_file() or path.is_symlink()]
    if not files:
        raise ValueError(f"generated root has no files: {root}")
    if any(path.is_symlink() for path in files):
        raise ValueError(f"symlink artifacts are not allowed: {root}")


def _verify_rgb_blob(payload: Mapping[str, object], index: int, blob: bytes) -> None:
    """校验 RGB bytes 和 payload proof 一致。"""
    proof = _mapping(payload[f"camera.rgb_{index}"], f"camera.rgb_{index}")
    if hashlib.sha256(blob).hexdigest() != proof["sha256"]:
        raise ValueError(f"rgb_{index} sha256 mismatch")
    if len(blob) != _positive_int(proof["byte_length"], "byte_length"):
        raise ValueError(f"rgb_{index} byte length mismatch")


def _batch_indices(sample_count: int, *, batch_index: int, batch_size: int) -> list[int]:
    """返回循环 batch indices。"""
    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    start = (batch_index * batch_size) % sample_count
    return [(start + offset) % sample_count for offset in range(batch_size)]


def _chunks(values: Sequence[MaterializedSample], size: int) -> list[Sequence[MaterializedSample]]:
    """按固定大小切分样本。"""
    return [values[index : index + size] for index in range(0, len(values), size)]


def _camera_specs(metadata: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    """从 metadata features 提取三路相机规格。"""
    features = _mapping(metadata.get("features"), "features")
    specs: list[dict[str, object]] = []
    for stream in CAMERA_STREAMS:
        feature = _mapping(features.get(stream), stream)
        info = _mapping(feature.get("video_info", feature.get("info", {})), "video_info")
        specs.append(
            {
                "height": _positive_int(
                    info.get("video.height", feature.get("height", 0)), f"{stream}.height"
                ),
                "stream_key": stream,
                "width": _positive_int(
                    info.get("video.width", feature.get("width", 0)), f"{stream}.width"
                ),
            }
        )
    return tuple(specs)


def _read_metadata(root: Path) -> dict[str, object]:
    """读取 metadata。"""
    for relative in ("metadata.json", "meta/info.json"):
        path = root / relative
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise TypeError(f"{relative} must contain a JSON object")
            return cast(dict[str, object], loaded)
    raise FileNotFoundError("metadata.json or meta/info.json is required")


def _read_tasks(root: Path) -> dict[int, str]:
    """读取 task_index 到语言文本的映射。"""
    path = root / "meta" / "tasks.jsonl"
    if not path.is_file():
        return {}
    tasks: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        loaded_obj: object = json.loads(line)
        if isinstance(loaded_obj, Mapping):
            loaded = cast(Mapping[str, object], loaded_obj)
            tasks[_int(loaded.get("task_index", len(tasks)), "task_index")] = _string(
                loaded.get("task", "zjh task"), "task"
            )
    return tasks


def _iter_table_rows(table: Any) -> list[dict[str, object]]:
    """把 pyarrow table 转为 Python rows。"""
    names = list(table.column_names)
    columns = {name: table[name].to_pylist() for name in names}
    rows: list[dict[str, object]] = []
    for index in range(int(table.num_rows)):
        rows.append({name: _json_safe(columns[name][index]) for name in names})
    return rows


def _tar_add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    """向 tar 写入确定性 bytes。"""
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mtime = 0
    archive.addfile(info, io.BytesIO(payload))


def _tar_read_bytes(archive: tarfile.TarFile, name: str) -> bytes:
    """从 tar 读取 bytes。"""
    member = archive.extractfile(name)
    if member is None:
        raise ValueError(f"missing tar member: {name}")
    return member.read()


def _npy_bytes(values: object) -> bytes:
    """把数组值写成 .npy bytes。"""
    handle = io.BytesIO()
    np.save(handle, np.asarray(values))
    return handle.getvalue()


def _json_bytes(payload: object) -> bytes:
    """返回规范 JSON bytes。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _write_json(path: Path, payload: object) -> None:
    """写出排序 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest_with_stats(path: Path, root: Path, manifest: dict[str, object]) -> None:
    """写 manifest 并刷新文件数量/大小, 避免报告旧统计。"""
    for _ in range(3):
        stats = _artifact_stats(root)
        manifest["generated_file_count"] = stats["file_count"]
        manifest["generated_artifact_size_bytes"] = stats["total_size_bytes"]
        _write_json(path, manifest)


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON object。"""
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return cast(dict[str, object], loaded)


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """写出 JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[object]:
    """读取 JSONL rows。"""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _mirror_task_root_output(config: FormatPipelineConfig, path: Path) -> None:
    """把关键报告镜像到 task root, 满足治理报告路径。"""
    task_root = config.output_dir.parent
    if task_root == config.output_dir:
        return
    if task_root.name != "AUTOVLA-M3-DATA-FORMAT-PIPELINE-SUITE-001":
        return
    target = task_root / path.name
    target.write_bytes(path.read_bytes())


def _artifact_stats(root: Path) -> dict[str, int]:
    """统计 root 下普通文件数量和大小。"""
    if not root.exists():
        return {"file_count": 0, "total_size_bytes": 0}
    files = [path for path in root.rglob("*") if path.is_file()]
    return {
        "file_count": len(files),
        "total_size_bytes": sum(path.stat().st_size for path in files),
    }


def _source_fingerprint(root: Path) -> str:
    """对 source metadata 和 parquet 文件名/大小做稳定 fingerprint。"""
    digest = hashlib.sha256()
    for path in sorted(root.glob("metadata.json")) + sorted((root / "meta").glob("*.json*")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    for path in sorted((root / "data").glob("chunk-*/*.parquet")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(str(path.stat().st_size).encode("utf-8"))
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    """计算文件 sha256。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(payload: Mapping[str, object]) -> str:
    """计算 JSON-safe 稳定 hash。"""
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def _resolve_under(root: Path, relative: str) -> Path:
    """解析 root 内相对路径。"""
    if not relative or relative.strip() != relative:
        raise ValueError("relative path must be normalized")
    lowered = relative.lower()
    if "://" in lowered or lowered.startswith("pipe:") or lowered.startswith("pipe="):
        raise ValueError("relative path must not be URL or pipe")
    raw = Path(relative)
    if raw.is_absolute():
        raise ValueError("relative path must not be absolute")
    resolved = (root / raw).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError("relative path escapes root")
    return resolved


def _episode_count(rows: Sequence[SourceRow]) -> int:
    """统计 episode 数量。"""
    return len({row.episode_id for row in rows})


def _elapsed_s(started: float) -> float:
    """返回秒级耗时。"""
    return round(max(time.perf_counter() - started, 0.0), 6)


def _percentile(values: Sequence[float], percentile: float) -> float:
    """计算线性插值百分位数。"""
    if not values:
        raise ValueError("values are required")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _json_safe(value: object) -> object:
    """把 numpy/pyarrow 值转成 JSON-safe 值。"""
    if isinstance(value, np.ndarray):
        ndarray_list = cast(object, value.tolist())
        return _json_safe(ndarray_list)
    if isinstance(value, (list, tuple)):
        sequence = cast(Sequence[object], value)
        return [_json_safe(item) for item in sequence]
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _json_safe(item) for key, item in mapping.items()}
    if isinstance(value, np.generic):
        scalar = cast(object, value.item())
        return scalar
    return value


def _mapping(value: object, field: str) -> Mapping[str, object]:
    """解析 mapping。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be a mapping")
    return cast(Mapping[str, object], value)


def _string(value: object, field: str) -> str:
    """解析非空字符串。"""
    if not isinstance(value, str) or not value:
        raise TypeError(f"{field} must be a non-empty string")
    return value


def _int(value: object, field: str) -> int:
    """解析 int。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    return value


def _positive_int(value: object, field: str) -> int:
    """解析正整数。"""
    parsed = _int(value, field)
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _float(value: object, field: str) -> float:
    """解析 float。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    return float(value)


def _float_list(value: object, field: str) -> list[float]:
    """解析 float list。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{field} must be a sequence")
    return [_float(item, field) for item in cast(Sequence[object], value)]


def _bool_list(value: object, *, expected: int) -> list[bool]:
    """解析 bool mask。"""
    if value is None:
        return [True for _ in range(expected)]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError("action_mask must be a sequence")
    parsed: list[bool] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, bool):
            raise TypeError("action_mask must be bool-only")
        parsed.append(item)
    if len(parsed) != expected:
        raise ValueError("action_mask length must match action")
    return parsed


def _int_list(value: object, field: str) -> list[int]:
    """解析 int list。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{field} must be a sequence")
    return [_int(item, field) for item in cast(Sequence[object], value)]


def _bytes(value: object, field: str) -> bytes:
    """解析 bytes。"""
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    raise TypeError(f"{field} must be bytes")
