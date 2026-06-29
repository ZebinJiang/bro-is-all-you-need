"""ZJH LeRobot-v2 元数据预览适配器。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from autovla.dataloader.contracts import (
    JsonObject,
    TransformSpec,
    canonical_json_object,
    json_object_to_plain,
)
from autovla.dataloader.dataset_artifact import (
    DatasetArtifactV1,
    StatisticsScope,
    build_fingerprint_set,
    normalize_dataset_root,
    validate_statistics_scope,
    write_dataset_artifact_preview,
)

ZJH_ADAPTER_NAME = "zjh-adapter"
ZJH_ADAPTER_VERSION = "1"
ZJH_SOURCE_FORMAT = "lerobot-v2-compatible"
SUPPORTED_CODEBASE_VERSION = "v2.1"

TargetMode = Literal["policy", "dialogue"]

_INFO_CANDIDATES: tuple[str, ...] = ("metadata.json", "meta/info.json")
_TASKS_RELATIVE_PATH = "meta/tasks.jsonl"
_CAMERA_KEYS: tuple[str, ...] = (
    "observation.images.left_wrist_rgb",
    "observation.images.head_rgb",
    "observation.images.right_wrist_rgb",
)
_INDEX_KEYS: tuple[str, ...] = ("timestamp", "frame_index", "episode_index", "index", "task_index")
_EPISODE_FLAG_KEYS: tuple[str, ...] = ("is_first", "is_last", "is_terminal")


@dataclass(frozen=True, slots=True)
class ZjhMetadataPreview:
    """保存 ZJH 数据集的小型元数据预览。"""

    dataset_root: Path
    normalized_dataset_root: str
    info: JsonObject
    info_sha256: str
    info_sources: tuple[str, ...]
    tasks: tuple[JsonObject, ...]
    tasks_sha256: str


@dataclass(frozen=True, slots=True)
class ZjhAdapter:
    """ZJH metadata-only Artifact v1 适配器。"""

    adapter_name: str = ZJH_ADAPTER_NAME
    adapter_version: str = ZJH_ADAPTER_VERSION
    source_format: str = ZJH_SOURCE_FORMAT

    def inspect(
        self,
        source: str | Path,
        *,
        project_root: str | Path | None = None,
    ) -> ZjhMetadataPreview:
        """只读取小型 metadata/info/tasks 文件。"""
        root = Path(source)
        info, info_sha256, sources = _read_info_metadata(root)
        tasks, tasks_sha256 = _read_tasks(root / _TASKS_RELATIVE_PATH)
        _validate_info(info)
        return ZjhMetadataPreview(
            dataset_root=root,
            normalized_dataset_root=normalize_dataset_root(root, project_root=project_root),
            info=info,
            info_sha256=info_sha256,
            info_sources=sources,
            tasks=tasks,
            tasks_sha256=tasks_sha256,
        )

    def validate(
        self,
        source: str | Path,
        *,
        project_root: str | Path | None = None,
    ) -> ZjhMetadataPreview:
        """校验 source 是否满足 ZJH metadata preview 契约。"""
        return self.inspect(source, project_root=project_root)

    def plan_conversion(
        self,
        source: str | Path,
        output: str | Path,
        *,
        project_root: str | Path | None = None,
        statistics_scope: StatisticsScope = "mixed",
        action_statistics_subset: Mapping[str, object] | None = None,
        target_mode: TargetMode = "policy",
    ) -> dict[str, object]:
        """生成不执行转换的 dry-run 计划。"""
        metadata = self.inspect(source, project_root=project_root)
        statistics = self.emit_statistics_plan(
            metadata,
            statistics_scope=statistics_scope,
            action_statistics_subset=action_statistics_subset,
            target_mode=target_mode,
        )
        return {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "artifact_filename": "dataset_artifact.json",
            "conversion": "dry_run_metadata_preview_only",
            "output_dir": Path(output).as_posix(),
            "source": metadata.normalized_dataset_root,
            "source_format": self.source_format,
            "statistics": statistics,
        }

    def convert_dry_run(
        self,
        source: str | Path,
        output: str | Path,
        *,
        project_root: str | Path | None = None,
        statistics_scope: StatisticsScope = "mixed",
        action_statistics_subset: Mapping[str, object] | None = None,
        target_mode: TargetMode = "policy",
        filename: str = "dataset_artifact.json",
    ) -> Path:
        """写出小型 Artifact JSON, 不复制媒体/parquet 样本。"""
        source_root = Path(source).absolute()
        output_path = Path(output).absolute()
        if _is_relative_to(output_path, source_root):
            raise ValueError("ZJH artifact preview must not be written inside dataset_root")
        artifact = self.emit_artifact(
            self.inspect(source_root, project_root=project_root),
            statistics_scope=statistics_scope,
            action_statistics_subset=action_statistics_subset,
            target_mode=target_mode,
        )
        return write_dataset_artifact_preview(artifact, output_path, filename=filename)

    def emit_artifact(
        self,
        metadata: ZjhMetadataPreview,
        *,
        statistics_scope: StatisticsScope = "mixed",
        action_statistics_subset: Mapping[str, object] | None = None,
        target_mode: TargetMode = "policy",
    ) -> DatasetArtifactV1:
        """从已读取元数据构造完整 Artifact v1。"""
        modality = self.emit_modality(metadata)
        transforms = _transform_preview()
        statistics = self.emit_statistics_plan(
            metadata,
            statistics_scope=statistics_scope,
            action_statistics_subset=action_statistics_subset,
            target_mode=target_mode,
        )
        sample_index = self.emit_sample_index(metadata)
        episode_index = self.emit_episode_index(metadata)
        checksums = self._emit_checksums(metadata)
        base_manifest = self.emit_manifest(
            metadata,
            statistics_scope=statistics_scope,
            modality=modality,
            statistics=statistics,
        )
        fingerprints = build_fingerprint_set(
            dataset_payload={
                "checksums": checksums,
                "dataset_manifest": base_manifest,
                "episode_index": episode_index,
                "modality": modality,
                "sample_index": sample_index,
            },
            transform_payload=transforms,
            statistics_payload=statistics,
        )
        manifest = {
            **base_manifest,
            "dataset_fingerprint": fingerprints.dataset_fingerprint,
            "statistics_fingerprint": fingerprints.statistics_fingerprint,
            "transform_fingerprint": fingerprints.transform_fingerprint,
        }

        return DatasetArtifactV1(
            adapter_name=self.adapter_name,
            dataset_manifest=manifest,
            modality=modality,
            transforms=transforms,
            statistics=statistics,
            sample_index=sample_index,
            episode_index=episode_index,
            checksums=checksums,
            fingerprints=fingerprints,
        )

    def emit_manifest(
        self,
        metadata: ZjhMetadataPreview,
        *,
        statistics_scope: StatisticsScope,
        modality: Mapping[str, object],
        statistics: Mapping[str, object],
    ) -> dict[str, object]:
        """构造 Dataset Artifact v1 manifest 子结构。"""
        info = json_object_to_plain(metadata.info)
        features = _mapping_value(info, "features")
        action_space = _numeric_feature("action", _feature_mapping(features, "action"))
        state_space = _numeric_feature(
            "observation.state",
            _feature_mapping(features, "observation.state"),
        )
        dataset_id = metadata.normalized_dataset_root.replace("/", ":")
        return {
            "action_space": action_space,
            "checksum": {
                "info_json_sha256": metadata.info_sha256,
                "tasks_jsonl_sha256": metadata.tasks_sha256,
            },
            "conversion_command": "metadata-only dry run; no conversion executed",
            "converter_version": self.adapter_version,
            "created_by": "autovla.dataloader.adapters.zjh.ZjhAdapter",
            "dataset_fingerprint_ref": "fingerprints.dataset_fingerprint",
            "dataset_id": dataset_id,
            "dataset_name": Path(metadata.normalized_dataset_root).name,
            "episode_count": _positive_int_value(info, "total_episodes"),
            "language_fields": {
                "source": _TASKS_RELATIVE_PATH,
                "task_index_field": "task_index",
                "text_field": "task",
            },
            "modalities": sorted(str(key) for key in modality.keys()),
            "provenance": {
                "codebase_version": _string_value(info, "codebase_version"),
                "info_sources": list(metadata.info_sources),
                "metadata_only": True,
            },
            "robot_tags": [_string_value(info, "robot_type")],
            "sample_count": _positive_int_value(info, "total_frames"),
            "shard_index": {
                "data_path_template": _string_value(info, "data_path"),
                "mode": "metadata_templates_only",
                "total_chunks": _positive_int_value(info, "total_chunks"),
                "video_path_template": _string_value(info, "video_path"),
            },
            "source_format": self.source_format,
            "source_uri": metadata.normalized_dataset_root,
            "schema_version": "autovla.dataset_manifest.v1",
            "splits": dict(_mapping_value(info, "splits")),
            "state_space": state_space,
            "statistics_fingerprint_ref": "fingerprints.statistics_fingerprint",
            "statistics_scope": statistics_scope,
            "statistics_scope_ref": statistics["statistics_scope"],
            "transform_fingerprint_ref": "fingerprints.transform_fingerprint",
        }

    def emit_modality(self, metadata: ZjhMetadataPreview) -> dict[str, object]:
        """把 LeRobot metadata 映射为 AutoVLA 模态描述。"""
        info = json_object_to_plain(metadata.info)
        features = _mapping_value(info, "features")
        tasks = tuple(json_object_to_plain(task) for task in metadata.tasks)
        action_feature = _feature_mapping(features, "action")
        state_feature = _feature_mapping(features, "observation.state")
        action = _numeric_feature("action", action_feature)
        state = _numeric_feature("observation.state", state_feature)
        cameras = [
            _camera_feature(
                key,
                _feature_mapping(features, key),
                _string_value(info, "video_path"),
            )
            for key in _CAMERA_KEYS
        ]
        action_keys = list(
            _names_value(
                action_feature,
                "names",
                expected_length=_shape_value(action_feature, "shape")[0],
            )
        )
        state_keys = list(
            _names_value(
                state_feature,
                "names",
                expected_length=_shape_value(state_feature, "shape")[0],
            )
        )
        return {
            "action": action,
            "action_keys": action_keys,
            "action_semantics": {
                "action_dim": len(action_keys),
                "action_horizon": "not_materialized_in_metadata",
                "action_mask": "deferred_to_training_view",
                "semantics": "ZJH absolute command/state-aligned vector",
            },
            "cameras": cameras,
            "dtype": {
                "action": action["dtype"],
                "camera": "video",
                "state": state["dtype"],
            },
            "episode_semantics": {
                "episode_index_key": "episode_index",
                "terminal_key": "is_terminal",
                "time_key": "timestamp",
            },
            "index": {
                "episode_flags": list(_EPISODE_FLAG_KEYS),
                "fields": list(_INDEX_KEYS),
                "mode": "placeholder_from_metadata",
            },
            "language": {
                "source": _TASKS_RELATIVE_PATH,
                "tasks": tasks,
            },
            "language_keys": ["task"],
            "normalization_policy": {
                "fit": "not_performed",
                "statistics_scope": "declared_by_statistics_plan",
            },
            "rate_hz": _positive_int_value(info, "fps"),
            "robot_embodiment": _string_value(info, "robot_type"),
            "schema_version": "autovla.modality.v1",
            "shape": {
                "action": action["shape"],
                "cameras": [camera["shape"] for camera in cameras],
                "state": state["shape"],
            },
            "state": state,
            "state_keys": state_keys,
            "time_alignment": {
                "fps": _positive_int_value(info, "fps"),
                "mode": "metadata_declared",
            },
        }

    def emit_sample_index(self, metadata: ZjhMetadataPreview) -> dict[str, object]:
        """构造不读取 parquet 的样本索引占位说明。"""
        info = json_object_to_plain(metadata.info)
        return {
            "fallback": "episode_index/frame_index/timestamp/task_index templates",
            "fields": list(_INDEX_KEYS),
            "mode": "placeholder_from_metadata",
            "row_level_validation": "not_performed",
            "sample_count_from_metadata": _positive_int_value(info, "total_frames"),
        }

    def emit_episode_index(self, metadata: ZjhMetadataPreview) -> dict[str, object]:
        """构造不读取 parquet 的 episode 索引占位说明。"""
        info = json_object_to_plain(metadata.info)
        return {
            "data_path_template": _string_value(info, "data_path"),
            "episode_count_from_metadata": _positive_int_value(info, "total_episodes"),
            "fields": ["episode_index", "frame_index", "timestamp", "task_index"],
            "mode": "placeholder_from_metadata",
            "splits": dict(_mapping_value(info, "splits")),
            "validation": "metadata_only_no_row_scan",
        }

    def emit_statistics_plan(
        self,
        metadata: ZjhMetadataPreview,
        *,
        statistics_scope: StatisticsScope,
        action_statistics_subset: Mapping[str, object] | None = None,
        target_mode: TargetMode = "policy",
    ) -> dict[str, object]:
        """构造未拟合统计量计划并校验 action 归一化边界。"""
        scope = validate_statistics_scope(statistics_scope)
        info = json_object_to_plain(metadata.info)
        features = _mapping_value(info, "features")
        has_action = "action" in features
        if target_mode == "dialogue" and scope != "vision_language_only":
            raise ValueError("dialogue data must use vision_language_only statistics_scope")
        if scope == "vision_language_only":
            if action_statistics_subset is not None:
                raise ValueError("vision_language_only data must not declare action statistics")
            include_action_statistics = False
            subset: Mapping[str, object] | None = None
        elif scope == "action_only":
            if not has_action:
                raise ValueError("action_only statistics require action data")
            include_action_statistics = True
            subset = action_statistics_subset or {
                "feature_key": "action",
                "selection": "all_action_rows",
            }
        else:
            if not has_action:
                raise ValueError("mixed statistics_scope requires action data")
            if action_statistics_subset is None:
                raise ValueError("mixed statistics_scope requires action_statistics_subset")
            include_action_statistics = True
            subset = action_statistics_subset

        output: dict[str, object] = {
            "action": "not_fit",
            "include_action_statistics": include_action_statistics,
            "state": "not_fit",
            "statistics_scope": scope,
            "target_mode": target_mode,
        }
        if subset is not None:
            output["action_statistics_subset"] = dict(subset)
        return output

    def _emit_checksums(self, metadata: ZjhMetadataPreview) -> dict[str, object]:
        """构造小型 metadata checksum 记录。"""
        return {
            "info_json_sha256": metadata.info_sha256,
            "info_sources": list(metadata.info_sources),
            "metadata_json_sha256": (
                metadata.info_sha256 if "metadata.json" in metadata.info_sources else None
            ),
            "tasks_jsonl_sha256": metadata.tasks_sha256,
        }


DEFAULT_ZJH_ADAPTER = ZjhAdapter()


def read_zjh_metadata(
    dataset_root: str | Path,
    *,
    project_root: str | Path | None = None,
) -> ZjhMetadataPreview:
    """通过默认 adapter 读取 ZJH 小型元数据。"""
    return DEFAULT_ZJH_ADAPTER.inspect(dataset_root, project_root=project_root)


def validate_zjh_statistics_request(
    statistics_scope: str,
    *,
    action_statistics_subset: Mapping[str, object] | None = None,
    has_action: bool = True,
    target_mode: TargetMode = "policy",
) -> StatisticsScope:
    """校验 ZJH 统计范围请求。"""
    scope = validate_statistics_scope(statistics_scope)
    if target_mode == "dialogue" and scope != "vision_language_only":
        raise ValueError("dialogue data must use vision_language_only statistics_scope")
    if scope == "vision_language_only" and action_statistics_subset is not None:
        raise ValueError("vision_language_only data must not declare action statistics")
    if scope == "action_only" and not has_action:
        raise ValueError("action_only statistics require action data")
    if scope == "mixed" and not action_statistics_subset:
        raise ValueError("mixed statistics_scope requires action_statistics_subset")
    return scope


def build_zjh_artifact_preview(
    metadata: ZjhMetadataPreview,
    *,
    statistics_scope: StatisticsScope = "mixed",
    action_statistics_subset: Mapping[str, object] | None = None,
    target_mode: TargetMode = "policy",
) -> DatasetArtifactV1:
    """通过默认 adapter 构造 Artifact v1 预览。"""
    return DEFAULT_ZJH_ADAPTER.emit_artifact(
        metadata,
        statistics_scope=statistics_scope,
        action_statistics_subset=action_statistics_subset,
        target_mode=target_mode,
    )


def build_zjh_artifact_from_root(
    dataset_root: str | Path,
    *,
    project_root: str | Path | None = None,
    statistics_scope: StatisticsScope = "mixed",
    action_statistics_subset: Mapping[str, object] | None = None,
    target_mode: TargetMode = "policy",
) -> DatasetArtifactV1:
    """读取 ZJH 小型元数据并构造 Artifact v1 预览。"""
    metadata = DEFAULT_ZJH_ADAPTER.inspect(dataset_root, project_root=project_root)
    return DEFAULT_ZJH_ADAPTER.emit_artifact(
        metadata,
        statistics_scope=statistics_scope,
        action_statistics_subset=action_statistics_subset,
        target_mode=target_mode,
    )


def write_zjh_artifact_preview(
    dataset_root: str | Path,
    output_dir: str | Path,
    *,
    project_root: str | Path | None = None,
    statistics_scope: StatisticsScope = "mixed",
    action_statistics_subset: Mapping[str, object] | None = None,
    target_mode: TargetMode = "policy",
    filename: str = "dataset_artifact.json",
) -> Path:
    """通过默认 adapter 写出 ZJH metadata-only 预览。"""
    return DEFAULT_ZJH_ADAPTER.convert_dry_run(
        dataset_root,
        output_dir,
        project_root=project_root,
        statistics_scope=statistics_scope,
        action_statistics_subset=action_statistics_subset,
        target_mode=target_mode,
        filename=filename,
    )


def _read_info_metadata(root: Path) -> tuple[JsonObject, str, tuple[str, ...]]:
    """读取 metadata.json/meta/info.json 并校验重复副本一致。"""
    payloads: list[tuple[str, bytes, str]] = []
    for relative in _INFO_CANDIDATES:
        path = root / relative
        if path.is_file():
            raw = path.read_bytes()
            payloads.append((relative, raw, hashlib.sha256(raw).hexdigest()))

    if not payloads:
        raise FileNotFoundError("metadata.json or meta/info.json is required")

    expected_sha = payloads[0][2]
    for relative, _raw, digest in payloads:
        if digest != expected_sha:
            raise ValueError(f"duplicate metadata checksum mismatch: {relative}")

    return (
        _json_object_from_bytes(payloads[0][1], name=payloads[0][0]),
        expected_sha,
        tuple(relative for relative, _raw, _digest in payloads),
    )


def _read_tasks(path: Path) -> tuple[tuple[JsonObject, ...], str]:
    """读取小型 tasks.jsonl 文件。"""
    if not path.is_file():
        raise FileNotFoundError("meta/tasks.jsonl is required")
    raw = path.read_bytes()
    tasks: list[JsonObject] = []
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        loaded = cast(object, json.loads(line))
        if not isinstance(loaded, Mapping):
            raise TypeError(f"task line {line_number} must be a JSON object")
        task = canonical_json_object(cast(Mapping[str, object], loaded))
        plain = json_object_to_plain(task)
        _int_value(plain, "task_index")
        _string_value(plain, "task")
        tasks.append(task)
    if not tasks:
        raise ValueError("meta/tasks.jsonl must contain at least one task")
    return tuple(tasks), hashlib.sha256(raw).hexdigest()


def _json_object_from_bytes(raw: bytes, *, name: str) -> JsonObject:
    """解析 JSON object 并返回 canonical 表示。"""
    loaded = cast(object, json.loads(raw.decode("utf-8")))
    if not isinstance(loaded, Mapping):
        raise TypeError(f"{name} must contain a JSON object")
    return canonical_json_object(cast(Mapping[str, object], loaded))


def _validate_info(info: JsonObject) -> None:
    """校验 ZJH 标准预览所需的 metadata 字段。"""
    plain = json_object_to_plain(info)
    codebase_version = _string_value(plain, "codebase_version")
    if codebase_version != SUPPORTED_CODEBASE_VERSION:
        raise ValueError(f"unsupported codebase_version: {codebase_version}")
    _string_value(plain, "robot_type")
    _positive_int_value(plain, "total_episodes")
    _positive_int_value(plain, "total_frames")
    _positive_int_value(plain, "total_tasks")
    _positive_int_value(plain, "total_chunks")
    _positive_int_value(plain, "fps")
    _string_value(plain, "data_path")
    _string_value(plain, "video_path")
    features = _mapping_value(plain, "features")

    for key in _CAMERA_KEYS:
        feature = _feature_mapping(features, key)
        if _string_value(feature, "dtype") != "video":
            raise ValueError(f"{key} must be a video feature")
        shape = _shape_value(feature, "shape")
        if len(shape) != 3:
            raise ValueError(f"{key} shape must be [height,width,channels]")

    state = _feature_mapping(features, "observation.state")
    action = _feature_mapping(features, "action")
    _validate_vector_feature(state, key="observation.state", dtype="float32")
    _validate_vector_feature(action, key="action", dtype="float32")

    for key in _INDEX_KEYS + _EPISODE_FLAG_KEYS:
        _feature_mapping(features, key)


def _transform_preview() -> dict[str, object]:
    """构造 metadata-only 转换声明。"""
    transform = TransformSpec(
        name="zjh.metadata_preview",
        params={
            "image_decode": "deferred",
            "state_action_transform": "identity_metadata_mapping",
        },
    )
    return {
        "preview_only": True,
        "steps": [transform.canonical()],
    }


def _camera_feature(
    key: str,
    feature: Mapping[str, object],
    video_path_template: str,
) -> dict[str, object]:
    """构造单个相机 metadata 描述。"""
    info = _mapping_value(feature, "info")
    video_info = _optional_mapping_value(feature, "video_info")
    return {
        "decode": "deferred",
        "dtype": _string_value(feature, "dtype"),
        "feature_key": key,
        "fps": _positive_int_value(info, "video.fps"),
        "shape": list(_shape_value(feature, "shape")),
        "video_codec": _string_value(video_info or info, "video.codec"),
        "video_path_template": video_path_template,
        "video_pixel_format": _string_value(video_info or info, "video.pix_fmt"),
    }


def _numeric_feature(key: str, feature: Mapping[str, object]) -> dict[str, object]:
    """构造 state/action 向量 metadata 描述。"""
    names = _names_value(feature, "names", expected_length=_shape_value(feature, "shape")[0])
    return {
        "dtype": _string_value(feature, "dtype"),
        "feature_key": key,
        "names": list(names),
        "shape": list(_shape_value(feature, "shape")),
    }


def _validate_vector_feature(feature: Mapping[str, object], *, key: str, dtype: str) -> None:
    """校验一维 state/action 特征。"""
    if _string_value(feature, "dtype") != dtype:
        raise ValueError(f"{key} must have dtype {dtype}")
    shape = _shape_value(feature, "shape")
    if len(shape) != 1:
        raise ValueError(f"{key} must be a 1-D vector")
    _names_value(feature, "names", expected_length=shape[0])


def _mapping_value(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    """取出必需 mapping 字段。"""
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise TypeError(f"{key} must be a mapping")
    return cast(Mapping[str, object], value)


def _optional_mapping_value(
    payload: Mapping[str, object],
    key: str,
) -> Mapping[str, object] | None:
    """取出可选 mapping 字段。"""
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError(f"{key} must be a mapping")
    return cast(Mapping[str, object], value)


def _feature_mapping(features: Mapping[str, object], key: str) -> Mapping[str, object]:
    """取出必需 feature 描述。"""
    value = features.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"required feature missing: {key}")
    return cast(Mapping[str, object], value)


def _shape_value(payload: Mapping[str, object], key: str) -> tuple[int, ...]:
    """取出正整数 shape。"""
    value = payload.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{key} must be a sequence")
    sequence = cast(Sequence[object], value)
    output: list[int] = []
    for index, item in enumerate(sequence):
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ValueError(f"{key}[{index}] must be a positive int")
        output.append(item)
    if not output:
        raise ValueError(f"{key} must not be empty")
    return tuple(output)


def _names_value(
    payload: Mapping[str, object],
    key: str,
    *,
    expected_length: int,
) -> tuple[str, ...]:
    """取出并校验 feature names。"""
    value = payload.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{key} must be a sequence")
    sequence = cast(Sequence[object], value)
    output: list[str] = []
    for index, item in enumerate(sequence):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{key}[{index}] must be a non-empty string")
        output.append(item)
    if len(output) != expected_length:
        raise ValueError(f"{key} length must match feature dimension")
    return tuple(output)


def _string_value(payload: Mapping[str, object], key: str) -> str:
    """取出非空字符串字段。"""
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _int_value(payload: Mapping[str, object], key: str) -> int:
    """取出 int 字段并拒绝 bool。"""
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an int")
    return value


def _positive_int_value(payload: Mapping[str, object], key: str) -> int:
    """取出正整数字段。"""
    value = _int_value(payload, key)
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _is_relative_to(child: Path, parent: Path) -> bool:
    """Python 3.10 兼容的路径包含判断。"""
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
