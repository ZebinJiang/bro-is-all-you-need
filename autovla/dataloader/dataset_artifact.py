"""AutoVLA 数据集 Artifact v1 元数据契约。"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias, cast

from autovla.dataloader.contracts import (
    JsonObject,
    canonical_json_object,
    json_object_to_plain,
)

DATASET_ARTIFACT_SCHEMA_VERSION = "autovla.dataset_artifact.v1"

StatisticsScope: TypeAlias = Literal["action_only", "vision_language_only", "mixed"]

ALLOWED_STATISTICS_SCOPES: frozenset[str] = frozenset(
    {
        "action_only",
        "vision_language_only",
        "mixed",
    }
)


def _empty_mapping() -> dict[str, object]:
    """返回类型明确的空 mapping。"""
    return {}


def _nonempty_string(value: object, *, name: str) -> str:
    """校验非空字符串并返回去空白后的值。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value.strip()


def _canonical_mapping(value: Mapping[str, object], *, name: str) -> JsonObject:
    """拥有并冻结 JSON-safe mapping。"""
    try:
        return canonical_json_object(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be JSON safe") from exc
    except ValueError as exc:
        raise ValueError(f"{name} must be JSON safe") from exc


def canonical_json_payload(value: Mapping[str, object]) -> dict[str, object]:
    """返回稳定排序、JSON-safe 的普通 dict。"""
    return json_object_to_plain(_canonical_mapping(value, name="payload"))


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    """返回稳定 JSON 字节, 用于指纹和磁盘预览。"""
    return json.dumps(
        canonical_json_payload(value),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def fingerprint_payload(domain: str, payload: Mapping[str, object]) -> str:
    """按指纹域计算稳定 SHA256。"""
    scoped_payload: dict[str, object] = {
        "domain": _nonempty_string(domain, name="domain"),
        "payload": payload,
        "schema_version": DATASET_ARTIFACT_SCHEMA_VERSION,
    }
    return hashlib.sha256(canonical_json_bytes(scoped_payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class FingerprintSet:
    """保存数据集、转换和统计量三个独立指纹。"""

    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str

    def __post_init__(self) -> None:
        """校验三个指纹字段均非空。"""
        _nonempty_string(self.dataset_fingerprint, name="dataset_fingerprint")
        _nonempty_string(self.transform_fingerprint, name="transform_fingerprint")
        _nonempty_string(self.statistics_fingerprint, name="statistics_fingerprint")

    def to_json_dict(self) -> dict[str, str]:
        """返回 JSON-safe 指纹记录。"""
        return {
            "dataset_fingerprint": self.dataset_fingerprint,
            "transform_fingerprint": self.transform_fingerprint,
            "statistics_fingerprint": self.statistics_fingerprint,
        }


def build_fingerprint_set(
    *,
    dataset_payload: Mapping[str, object],
    transform_payload: Mapping[str, object],
    statistics_payload: Mapping[str, object],
) -> FingerprintSet:
    """基于三个 canonical payload 构造独立且互相绑定的指纹。"""
    dataset_fingerprint = fingerprint_payload("dataset", dataset_payload)
    transform_fingerprint = fingerprint_payload("transform", transform_payload)
    statistics_with_refs: dict[str, object] = dict(statistics_payload)
    statistics_with_refs["dataset_fingerprint"] = dataset_fingerprint
    statistics_with_refs["transform_fingerprint"] = transform_fingerprint
    return FingerprintSet(
        dataset_fingerprint=dataset_fingerprint,
        transform_fingerprint=transform_fingerprint,
        statistics_fingerprint=fingerprint_payload("statistics", statistics_with_refs),
    )


def normalize_dataset_root(
    dataset_root: str | Path,
    *,
    project_root: str | Path | None = None,
) -> str:
    """把数据集根目录规范化为稳定、非主机绑定的引用。"""
    root_path = Path(dataset_root)
    if project_root is not None:
        project_path = Path(project_root).absolute()
        absolute_root = root_path.absolute()
        try:
            return absolute_root.relative_to(project_path).as_posix()
        except ValueError:
            pass

    parts = root_path.parts
    for index, part in enumerate(parts[:-1]):
        if part == "datasets" and parts[index + 1] == "readonly":
            return Path(*parts[index:]).as_posix()
    return root_path.name


def validate_statistics_scope(scope: str) -> StatisticsScope:
    """校验 Artifact v1 支持的统计范围。"""
    if scope not in ALLOWED_STATISTICS_SCOPES:
        raise ValueError(f"unsupported statistics_scope: {scope}")
    return cast(StatisticsScope, scope)


def _fingerprints_mapping(value: FingerprintSet | Mapping[str, object]) -> JsonObject:
    """拥有并校验指纹 mapping。"""
    raw = value.to_json_dict() if isinstance(value, FingerprintSet) else value
    owned = _canonical_mapping(raw, name="fingerprints")
    plain = json_object_to_plain(owned)
    for key in ("dataset_fingerprint", "transform_fingerprint", "statistics_fingerprint"):
        _nonempty_string(plain.get(key), name=key)
    return owned


@dataclass(frozen=True, slots=True)
class DatasetArtifactV1:
    """描述 metadata-only 数据集 Artifact 预览。

    该对象只表达数据集元数据、模态映射、转换声明、统计范围和确定性指纹。
    它不读取样本行、不解码媒体、不拟合统计量, 也不代表真实训练可用性。
    """

    adapter_name: str
    dataset_manifest: Mapping[str, object] = field(default_factory=_empty_mapping)
    modality: Mapping[str, object] = field(default_factory=_empty_mapping)
    transforms: Mapping[str, object] = field(default_factory=_empty_mapping)
    statistics: Mapping[str, object] = field(default_factory=_empty_mapping)
    sample_index: Mapping[str, object] = field(default_factory=_empty_mapping)
    episode_index: Mapping[str, object] = field(default_factory=_empty_mapping)
    checksums: Mapping[str, object] = field(default_factory=_empty_mapping)
    fingerprints: FingerprintSet | Mapping[str, object] = field(default_factory=_empty_mapping)
    schema_version: str = DATASET_ARTIFACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """校验并拥有所有 JSON-safe 子结构。"""
        if self.schema_version != DATASET_ARTIFACT_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        adapter_name = _nonempty_string(self.adapter_name, name="adapter_name")
        object.__setattr__(self, "adapter_name", adapter_name)

        owned_manifest = _canonical_mapping(self.dataset_manifest, name="dataset_manifest")
        owned_modality = _canonical_mapping(self.modality, name="modality")
        owned_transforms = _canonical_mapping(self.transforms, name="transforms")
        owned_statistics = _canonical_mapping(self.statistics, name="statistics")
        owned_sample_index = _canonical_mapping(self.sample_index, name="sample_index")
        owned_episode_index = _canonical_mapping(self.episode_index, name="episode_index")
        owned_checksums = _canonical_mapping(self.checksums, name="checksums")
        owned_fingerprints = _fingerprints_mapping(self.fingerprints)

        scope = _validate_statistics_contract(owned_statistics, owned_modality)
        _validate_manifest_scope(owned_manifest, scope)

        object.__setattr__(self, "dataset_manifest", owned_manifest)
        object.__setattr__(self, "modality", owned_modality)
        object.__setattr__(self, "transforms", owned_transforms)
        object.__setattr__(self, "statistics", owned_statistics)
        object.__setattr__(self, "sample_index", owned_sample_index)
        object.__setattr__(self, "episode_index", owned_episode_index)
        object.__setattr__(self, "checksums", owned_checksums)
        object.__setattr__(self, "fingerprints", owned_fingerprints)

    def to_json_dict(self) -> dict[str, object]:
        """返回 Artifact v1 的稳定 JSON 字典。"""
        return {
            "adapter_name": self.adapter_name,
            "checksums": json_object_to_plain(cast(JsonObject, self.checksums)),
            "dataset_manifest": json_object_to_plain(cast(JsonObject, self.dataset_manifest)),
            "episode_index": json_object_to_plain(cast(JsonObject, self.episode_index)),
            "fingerprints": json_object_to_plain(cast(JsonObject, self.fingerprints)),
            "modality": json_object_to_plain(cast(JsonObject, self.modality)),
            "sample_index": json_object_to_plain(cast(JsonObject, self.sample_index)),
            "schema_version": self.schema_version,
            "statistics": json_object_to_plain(cast(JsonObject, self.statistics)),
            "transforms": json_object_to_plain(cast(JsonObject, self.transforms)),
        }

    def to_json_bytes(self) -> bytes:
        """返回带换行的 pretty JSON 预览字节。"""
        return (
            json.dumps(self.to_json_dict(), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, object]) -> "DatasetArtifactV1":
        """从 JSON 字典恢复 Artifact v1。"""
        return cls(
            adapter_name=_string_field(payload, "adapter_name"),
            checksums=_mapping_field(payload, "checksums"),
            dataset_manifest=_mapping_field(payload, "dataset_manifest"),
            episode_index=_mapping_field(payload, "episode_index"),
            fingerprints=_mapping_field(payload, "fingerprints"),
            modality=_mapping_field(payload, "modality"),
            sample_index=_mapping_field(payload, "sample_index"),
            schema_version=_string_field(payload, "schema_version"),
            statistics=_mapping_field(payload, "statistics"),
            transforms=_mapping_field(payload, "transforms"),
        )


def _validate_statistics_contract(statistics: JsonObject, modality: JsonObject) -> StatisticsScope:
    """校验 scope 与模态/统计子集的一致性。"""
    statistics_plain = json_object_to_plain(statistics)
    modality_plain = json_object_to_plain(modality)
    scope = validate_statistics_scope(_string_field(statistics_plain, "statistics_scope"))
    action_feature = modality_plain.get("action")
    has_action = isinstance(action_feature, Mapping) and bool(action_feature)
    action_subset = statistics_plain.get("action_statistics_subset")
    include_action = statistics_plain.get("include_action_statistics", False)

    if scope == "vision_language_only":
        if include_action is True or action_subset is not None:
            raise ValueError("vision_language_only data must not contribute action statistics")
    elif scope == "action_only":
        if not has_action:
            raise ValueError("action_only statistics require action data")
    elif scope == "mixed":
        if not isinstance(action_subset, Mapping) or not action_subset:
            raise ValueError("mixed statistics_scope requires action_statistics_subset")
        if not has_action:
            raise ValueError("mixed statistics_scope requires action data")
    return scope


def _validate_manifest_scope(manifest: JsonObject, scope: StatisticsScope) -> None:
    """校验 manifest 中的 statistics_scope 与统计计划一致。"""
    manifest_plain = json_object_to_plain(manifest)
    manifest_scope = manifest_plain.get("statistics_scope")
    if manifest_scope is not None and manifest_scope != scope:
        raise ValueError("dataset_manifest.statistics_scope must match statistics.statistics_scope")


def _string_field(payload: Mapping[str, object], key: str) -> str:
    """从 payload 中取出必需字符串字段。"""
    return _nonempty_string(payload.get(key), name=key)


def _mapping_field(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    """从 payload 中取出必需 mapping 字段。"""
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise TypeError(f"{key} must be a mapping")
    return cast(Mapping[str, object], value)


def _is_under_readonly_dataset(path: Path) -> bool:
    """判断输出路径是否落入 datasets/readonly。"""
    parts = path.parts
    return any(
        part == "datasets" and index + 1 < len(parts) and parts[index + 1] == "readonly"
        for index, part in enumerate(parts)
    )


def write_dataset_artifact_preview(
    artifact: DatasetArtifactV1,
    output_dir: str | Path,
    *,
    filename: str = "dataset_artifact.json",
) -> Path:
    """把小型 Artifact JSON 写入调用方提供的输出目录。"""
    filename_path = Path(filename)
    if filename_path.name != filename or filename_path.is_absolute():
        raise ValueError("filename must be a simple relative file name")

    directory = Path(output_dir)
    if _is_under_readonly_dataset(directory):
        raise ValueError("artifact preview must not be written under datasets/readonly")

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(artifact.to_json_bytes())
    os.replace(temporary, target)
    return target
