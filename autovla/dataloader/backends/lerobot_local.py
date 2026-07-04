"""LeRobot local metadata-only probe。"""

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


def _dict_payload(value: object) -> dict[str, object]:
    """把 JSON object 收窄成字符串键 mapping。"""
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, object], value)


def _shape_from_feature(value: object) -> tuple[int, ...]:
    """从 feature metadata 中读取 shape。"""
    feature = _dict_payload(value)
    return shape_of(feature.get("shape"))


def _info_path(root: Path) -> Path:
    """返回 LeRobot 常见 info metadata 路径。"""
    return root / "meta" / "info.json"


def probe_lerobot_local(config: DataProbeConfig) -> DataProbeResult:
    """读取本地 LeRobot metadata, 不导入 LeRobot runtime。"""
    if not config.input_root.exists():
        return missing_root_result(config)
    info = _info_path(config.input_root)
    if not info.is_file():
        return DataProbeResult(
            backend="lerobot_local",
            status="NO_METADATA",
            samples_observed=0,
            files_observed=0,
            bytes_read=0,
            bytes_written=0,
            file_open_count=0,
            schema_fields_observed=(),
            action_fields_observed=(),
            language_fields_observed=(),
            image_fields_observed=(),
            state_fields_observed=(),
            warnings=("missing meta/info.json",),
            errors=(),
            missing_telemetry=("REQUIRES_LEROBOT_RUNTIME_FUTURE", "media_decode", "gpu"),
        )
    payload, bytes_read, error = read_json_limited(info, max_bytes=config.max_bytes_read)
    if error or not isinstance(payload, dict):
        return DataProbeResult(
            backend="lerobot_local",
            status="ERROR",
            samples_observed=0,
            files_observed=1,
            bytes_read=bytes_read,
            bytes_written=0,
            file_open_count=1,
            schema_fields_observed=(),
            action_fields_observed=(),
            language_fields_observed=(),
            image_fields_observed=(),
            state_fields_observed=(),
            warnings=(),
            errors=(error or "meta/info.json must be a JSON object",),
            missing_telemetry=("REQUIRES_LEROBOT_RUNTIME_FUTURE",),
        )
    typed_payload = cast(dict[str, object], payload)
    feature_map = _dict_payload(typed_payload.get("features"))
    feature_keys = sorted_tuple(str(key) for key in feature_map)
    action_fields = tuple(key for key in feature_keys if "action" in key)
    language_fields = tuple(key for key in feature_keys if key in {"task", "language", "text"})
    image_fields = tuple(key for key in feature_keys if "image" in key or "video" in key)
    state_fields = tuple(key for key in feature_keys if "state" in key)
    total_frames = typed_payload.get("total_frames", 0)
    samples = (
        int(total_frames)
        if isinstance(total_frames, int) and not isinstance(total_frames, bool)
        else 0
    )
    action_feature = feature_map.get(action_fields[0]) if action_fields else None
    state_feature = feature_map.get(state_fields[0]) if state_fields else None
    row = DatasetPreviewRow(
        sample_id="lerobot-local-preview",
        episode_id="lerobot-local-episode",
        source_path=info,
        media_refs_count=len(image_fields),
        action_shape=_shape_from_feature(action_feature),
        state_shape=_shape_from_feature(state_feature),
        language_present=bool(language_fields),
        timestamp_present="timestamp" in feature_keys,
        metadata_keys=mapping_keys(typed_payload),
        status="PASS",
    )
    return DataProbeResult(
        backend="lerobot_local",
        status="PASS",
        samples_observed=min(samples, config.max_samples),
        files_observed=1,
        bytes_read=bytes_read,
        bytes_written=0,
        file_open_count=1,
        schema_fields_observed=feature_keys,
        action_fields_observed=action_fields,
        language_fields_observed=language_fields,
        image_fields_observed=image_fields,
        state_fields_observed=state_fields,
        warnings=(),
        errors=(),
        missing_telemetry=("REQUIRES_LEROBOT_RUNTIME_FUTURE", "media_decode", "gpu", "slurm"),
        preview_rows=(row,),
    )
