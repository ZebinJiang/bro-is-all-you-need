"""数据集统计量显式路径缓存。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

from genesisvla.dataloader.statistics.schema import (
    SCHEMA_VERSION,
    DatasetStatistics,
    FeatureStatistics,
)


def _feature_to_payload(statistics: FeatureStatistics | None) -> dict[str, Any] | None:
    """把特征统计量转换为 JSON 友好载荷。"""
    if statistics is None:
        return None
    return {
        "mean": statistics.mean.tolist(),
        "names": list(statistics.names),
        "std": statistics.std.tolist(),
    }


def _feature_from_payload(payload: object, field_name: str) -> FeatureStatistics | None:
    """从 JSON 载荷恢复特征统计量。"""
    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} statistics payload must be a mapping")
    mapping = cast(Mapping[str, object], payload)
    if "mean" not in mapping or "std" not in mapping:
        raise ValueError(f"{field_name} statistics require mean and std")
    names_value = mapping.get("names", ())
    if names_value is None:
        names: tuple[str, ...] = ()
    elif isinstance(names_value, list):
        names_sequence = cast(Sequence[object], names_value)
        names = tuple(str(name) for name in names_sequence)
    else:
        raise ValueError(f"{field_name} statistics names must be a list")
    return FeatureStatistics(
        mean=np.asarray(mapping["mean"], dtype=np.float32),
        std=np.asarray(mapping["std"], dtype=np.float32),
        names=names,
    )


def _statistics_to_payload(statistics: DatasetStatistics) -> dict[str, Any]:
    """把数据集统计量转换为稳定 JSON 载荷。"""
    return {
        "action": _feature_to_payload(statistics.action),
        "metadata": dict(statistics.metadata),
        "sample_count": statistics.sample_count,
        "schema_version": statistics.schema_version,
        "state": _feature_to_payload(statistics.state),
    }


def _statistics_from_payload(payload: object) -> DatasetStatistics:
    """从 JSON 载荷恢复数据集统计量并执行 schema 校验。"""
    if not isinstance(payload, Mapping):
        raise ValueError("statistics payload must be a mapping")
    mapping = cast(Mapping[str, object], payload)
    schema_version = mapping.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
    if "sample_count" not in mapping:
        raise ValueError("sample_count is required")
    sample_count = mapping["sample_count"]
    if not isinstance(sample_count, int):
        raise ValueError("sample_count must be an integer")
    metadata_value = mapping.get("metadata", {})
    if not isinstance(metadata_value, Mapping):
        raise ValueError("metadata must be a mapping")
    return DatasetStatistics(
        sample_count=sample_count,
        state=_feature_from_payload(mapping.get("state"), "state"),
        action=_feature_from_payload(mapping.get("action"), "action"),
        metadata=dict(cast(Mapping[str, Any], metadata_value)),
        schema_version=cast(str, schema_version),
    )


def save_statistics(path: str | Path, statistics: DatasetStatistics) -> None:
    """把统计量写入调用方显式指定的 JSON 路径。"""
    target = Path(path)
    payload = _statistics_to_payload(statistics)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_statistics(path: str | Path) -> DatasetStatistics:
    """从调用方显式指定的 JSON 路径读取统计量。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return _statistics_from_payload(payload)
