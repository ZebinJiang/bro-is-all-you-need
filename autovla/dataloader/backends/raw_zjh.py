"""Raw ZJH metadata-only probe。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from autovla.dataloader.backends.contracts import (
    DataProbeConfig,
    DataProbeResult,
    DatasetPreviewRow,
)
from autovla.dataloader.backends.probe import (
    mapping_keys,
    missing_root_result,
    read_json_limited,
    shape_of,
    sorted_tuple,
)

METADATA_SUFFIXES = frozenset({".json", ".jsonl", ".txt"})


def _iter_metadata_files(root: Path, *, max_files: int) -> tuple[Path, ...]:
    """枚举有界 metadata 文件。"""
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if len(files) >= max_files:
            break
        if path.is_file() and path.suffix.lower() in METADATA_SUFFIXES:
            files.append(path)
    return tuple(files)


def _preview_from_payload(path: Path, payload: object, index: int) -> DatasetPreviewRow:
    """从 JSON-like payload 生成 preview 行。"""
    mapping = cast(dict[str, object], payload) if isinstance(payload, dict) else {}
    action = mapping.get("action")
    state = mapping.get("state", mapping.get("observation.state"))
    image_refs = [key for key in ("image", "images", "camera", "cameras") if key in mapping]
    language_present = any(key in mapping for key in ("language", "text", "task", "instruction"))
    return DatasetPreviewRow(
        sample_id=str(mapping.get("sample_id", f"sample-{index:04d}")),
        episode_id=str(mapping.get("episode_id", f"episode-{index:04d}")),
        source_path=path,
        media_refs_count=len(image_refs),
        action_shape=shape_of(action),
        state_shape=shape_of(state),
        language_present=language_present,
        timestamp_present="timestamp" in mapping,
        metadata_keys=mapping_keys(mapping),
        status="PASS",
    )


def probe_raw_zjh(config: DataProbeConfig) -> DataProbeResult:
    """有界读取 raw_zjh 本地 metadata, 不读取或解码媒体。"""
    if not config.input_root.exists():
        return missing_root_result(config)
    files = _iter_metadata_files(config.input_root, max_files=config.max_files)
    bytes_read = 0
    opened = 0
    previews: list[DatasetPreviewRow] = []
    schema_fields: list[str] = []
    action_fields: list[str] = []
    language_fields: list[str] = []
    image_fields: list[str] = []
    state_fields: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    for index, path in enumerate(files, start=1):
        if len(previews) >= config.max_samples or bytes_read >= config.max_bytes_read:
            break
        payload, read_count, error = read_json_limited(
            path,
            max_bytes=max(config.max_bytes_read - bytes_read, 1),
        )
        bytes_read += read_count
        opened += 1
        if error:
            warnings.append(f"{path.name}: {error}")
            continue
        if isinstance(payload, dict):
            typed_payload = cast(dict[str, object], payload)
            keys = mapping_keys(typed_payload)
            schema_fields.extend(keys)
            action_fields.extend(key for key in keys if "action" in key)
            language_fields.extend(
                key for key in keys if key in {"instruction", "language", "task", "text"}
            )
            image_fields.extend(
                key for key in keys if key in {"camera", "cameras", "image", "images"}
            )
            state_fields.extend(key for key in keys if "state" in key)
            previews.append(_preview_from_payload(path, typed_payload, index))
    status = "PASS" if previews else "NO_METADATA"
    return DataProbeResult(
        backend="raw_zjh",
        status=status,
        samples_observed=len(previews),
        files_observed=len(files),
        bytes_read=bytes_read,
        bytes_written=0,
        file_open_count=opened,
        schema_fields_observed=sorted_tuple(schema_fields),
        action_fields_observed=sorted_tuple(action_fields),
        language_fields_observed=sorted_tuple(language_fields),
        image_fields_observed=sorted_tuple(image_fields),
        state_fields_observed=sorted_tuple(state_fields),
        warnings=tuple(warnings),
        errors=tuple(errors),
        missing_telemetry=("media_decode", "gpu", "slurm"),
        preview_rows=tuple(previews),
    )
