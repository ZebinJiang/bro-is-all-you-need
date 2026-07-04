"""AutoVLA DataBackend metadata-only probe 契约。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_TABLE_FORMATS = frozenset({"json", "csv", "md"})


def _require_non_empty(value: str, *, field: str) -> None:
    """校验非空字符串字段。"""
    if not value.strip():
        raise ValueError(f"{field} must not be empty")


def _require_positive_int(value: int, *, field: str) -> None:
    """校验正整数并拒绝 bool。"""
    if type(value) is not int:
        raise ValueError(f"{field} must be a positive int")
    if value <= 0:
        raise ValueError(f"{field} must be positive")


@dataclass(frozen=True, slots=True)
class DataBackendSpec:
    """描述一个 DataBackend 候选项的静态审查契约。"""

    backend_key: str
    display_name: str
    input_root_policy: str
    supports_local_probe: bool
    supports_streaming_future: bool
    supports_random_access_future: bool
    license_reference_id: str
    dependency_status: str
    implementation_status: str

    def __post_init__(self) -> None:
        """拒绝空字段, 保证报告行可追溯。"""
        for field in (
            "backend_key",
            "display_name",
            "input_root_policy",
            "license_reference_id",
            "dependency_status",
            "implementation_status",
        ):
            _require_non_empty(str(getattr(self, field)), field=field)

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 结构。"""
        return {
            "backend_key": self.backend_key,
            "dependency_status": self.dependency_status,
            "display_name": self.display_name,
            "implementation_status": self.implementation_status,
            "input_root_policy": self.input_root_policy,
            "license_reference_id": self.license_reference_id,
            "supports_local_probe": self.supports_local_probe,
            "supports_random_access_future": self.supports_random_access_future,
            "supports_streaming_future": self.supports_streaming_future,
        }


@dataclass(frozen=True, slots=True)
class DataProbeConfig:
    """配置一次有界、metadata-only 的 DataBackend probe。"""

    backend: str
    input_root: Path
    max_samples: int
    max_files: int
    max_bytes_read: int
    read_media: bool
    decode_media: bool
    output_dir: Path
    table_format: tuple[str, ...]
    allow_missing_input_root: bool

    def __post_init__(self) -> None:
        """校验本 tranche 不允许真实媒体读取或解码。"""
        _require_non_empty(self.backend, field="backend")
        _require_positive_int(self.max_samples, field="max_samples")
        _require_positive_int(self.max_files, field="max_files")
        _require_positive_int(self.max_bytes_read, field="max_bytes_read")
        if self.read_media:
            raise ValueError("read_media is not authorized for DataBackend foundation")
        if self.decode_media:
            raise ValueError("decode_media is not authorized for DataBackend foundation")
        if not self.table_format:
            raise ValueError("table_format must not be empty")
        invalid = [item for item in self.table_format if item not in SUPPORTED_TABLE_FORMATS]
        if invalid:
            raise ValueError(f"unsupported table format: {invalid[0]}")
        object.__setattr__(self, "input_root", Path(self.input_root))
        object.__setattr__(self, "output_dir", Path(self.output_dir))


@dataclass(frozen=True, slots=True)
class DatasetPreviewRow:
    """描述一个可审查数据样本的轻量 preview 行。"""

    sample_id: str
    episode_id: str
    source_path: Path
    media_refs_count: int
    action_shape: tuple[int, ...]
    state_shape: tuple[int, ...]
    language_present: bool
    timestamp_present: bool
    metadata_keys: tuple[str, ...]
    status: str

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON preview 行。"""
        return {
            "action_shape": list(self.action_shape),
            "episode_id": self.episode_id,
            "language_present": self.language_present,
            "media_refs_count": self.media_refs_count,
            "metadata_keys": list(self.metadata_keys),
            "sample_id": self.sample_id,
            "source_path": self.source_path.as_posix(),
            "state_shape": list(self.state_shape),
            "status": self.status,
            "timestamp_present": self.timestamp_present,
        }


@dataclass(frozen=True, slots=True)
class DataProbeResult:
    """一次 backend probe 的稳定结果。"""

    backend: str
    status: str
    samples_observed: int
    files_observed: int
    bytes_read: int
    bytes_written: int
    file_open_count: int
    schema_fields_observed: tuple[str, ...]
    action_fields_observed: tuple[str, ...]
    language_fields_observed: tuple[str, ...]
    image_fields_observed: tuple[str, ...]
    state_fields_observed: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    missing_telemetry: tuple[str, ...]
    preview_rows: tuple[DatasetPreviewRow, ...] = ()

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 结构。"""
        return {
            "action_fields_observed": list(self.action_fields_observed),
            "backend": self.backend,
            "bytes_read": self.bytes_read,
            "bytes_written": self.bytes_written,
            "errors": list(self.errors),
            "file_open_count": self.file_open_count,
            "files_observed": self.files_observed,
            "image_fields_observed": list(self.image_fields_observed),
            "language_fields_observed": list(self.language_fields_observed),
            "missing_telemetry": list(self.missing_telemetry),
            "preview_rows": [row.to_json_dict() for row in self.preview_rows],
            "samples_observed": self.samples_observed,
            "schema_fields_observed": list(self.schema_fields_observed),
            "state_fields_observed": list(self.state_fields_observed),
            "status": self.status,
            "warnings": list(self.warnings),
        }
