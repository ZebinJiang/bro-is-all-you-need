"""DataBackend probe 分发器和通用工具。"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

from autovla.dataloader.backends.contracts import DataProbeConfig, DataProbeResult


def shape_of(value: object) -> tuple[int, ...]:
    """从 JSON-like 对象推断轻量 shape。"""
    if isinstance(value, list):
        values = cast(list[object], value)
        if not values:
            return (0,)
        inner = shape_of(values[0])
        return (len(values), *inner)
    return ()


def sorted_tuple(values: Iterable[str]) -> tuple[str, ...]:
    """返回去重排序 tuple。"""
    return tuple(sorted(set(values)))


def read_json_limited(path: Path, *, max_bytes: int) -> tuple[object | None, int, str | None]:
    """按字节预算读取 JSON 文件。"""
    data = path.read_bytes()[:max_bytes]
    try:
        return json.loads(data.decode("utf-8")), len(data), None
    except Exception as exc:
        return None, len(data), str(exc)


def missing_root_result(config: DataProbeConfig) -> DataProbeResult:
    """构造缺失 input_root 的稳定 probe 结果。"""
    if not config.allow_missing_input_root:
        return DataProbeResult(
            backend=config.backend,
            status="ERROR",
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
            warnings=(),
            errors=(f"missing input_root: {config.input_root.as_posix()}",),
            missing_telemetry=("local_input_root",),
        )
    return DataProbeResult(
        backend=config.backend,
        status="MISSING_INPUT_ROOT",
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
        warnings=(f"missing input_root allowed: {config.input_root.as_posix()}",),
        errors=(),
        missing_telemetry=("local_input_root", "real_dataset", "media_decode"),
    )


def mapping_keys(payload: object) -> tuple[str, ...]:
    """提取 JSON mapping 键。"""
    if isinstance(payload, Mapping):
        typed = cast(Mapping[object, object], payload)
        return sorted_tuple(str(key) for key in typed)
    return ()
