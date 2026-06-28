"""AutoVLA 本地 runner checkpoint manifest。"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True, slots=True)
class ResumeSpec:
    """描述一次恢复所需匹配的最小兼容性字段。"""

    model_registry_key: str
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str


@dataclass(frozen=True, slots=True)
class CheckpointManifest:
    """记录 CPU-only smoke checkpoint 的可验证 manifest。"""

    run_id: str
    step: int
    epoch: int
    model_registry_key: str
    runner_config: Mapping[str, object]
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str
    action_horizon: tuple[int, ...]
    action_dim: tuple[int, ...]
    mask_shape: tuple[int, int, int]
    valid_action_elements: int
    sample_source: tuple[Mapping[str, object], ...]
    metrics: Mapping[str, float]
    schema_version: str = "m3-local-runner-smoke.v1"

    def validate_resume(self, expected: ResumeSpec) -> int:
        """校验恢复状态与当前 runner 配置兼容。"""
        checks = {
            "model_registry_key": expected.model_registry_key,
            "dataset_fingerprint": expected.dataset_fingerprint,
            "transform_fingerprint": expected.transform_fingerprint,
            "statistics_fingerprint": expected.statistics_fingerprint,
        }
        for name, expected_value in checks.items():
            current_value = getattr(self, name)
            if current_value != expected_value:
                raise ValueError(
                    f"{name} mismatch: checkpoint={current_value!r}, expected={expected_value!r}"
                )
        return self.step

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "step": self.step,
            "epoch": self.epoch,
            "model_registry_key": self.model_registry_key,
            "runner_config": dict(self.runner_config),
            "dataset_fingerprint": self.dataset_fingerprint,
            "transform_fingerprint": self.transform_fingerprint,
            "statistics_fingerprint": self.statistics_fingerprint,
            "action_horizon": list(self.action_horizon),
            "action_dim": list(self.action_dim),
            "mask_shape": list(self.mask_shape),
            "valid_action_elements": self.valid_action_elements,
            "sample_source": [dict(item) for item in self.sample_source],
            "metrics": dict(self.metrics),
        }

    @classmethod
    def from_json_dict(cls, data: Mapping[str, object]) -> "CheckpointManifest":
        """从 JSON 表示恢复 manifest。"""
        return cls(
            run_id=_required_str(data, "run_id"),
            step=_required_int(data, "step"),
            epoch=_required_int(data, "epoch"),
            model_registry_key=_required_str(data, "model_registry_key"),
            runner_config=_required_mapping(data, "runner_config"),
            dataset_fingerprint=_required_str(data, "dataset_fingerprint"),
            transform_fingerprint=_required_str(data, "transform_fingerprint"),
            statistics_fingerprint=_required_str(data, "statistics_fingerprint"),
            action_horizon=_required_int_tuple(data, "action_horizon"),
            action_dim=_required_int_tuple(data, "action_dim"),
            mask_shape=_required_fixed_int_tuple(data, "mask_shape", length=3),
            valid_action_elements=_required_int(data, "valid_action_elements"),
            sample_source=_required_mapping_tuple(data, "sample_source"),
            metrics=_required_float_mapping(data, "metrics"),
            schema_version=_optional_str(data, "schema_version", "m3-local-runner-smoke.v1"),
        )


def _required(data: Mapping[str, object], key: str) -> object:
    """读取必需 JSON 字段。"""
    if key not in data:
        raise ValueError(f"checkpoint manifest missing {key}")
    return data[key]


def _required_str(data: Mapping[str, object], key: str) -> str:
    """读取非空字符串字段。"""
    value = _required(data, key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _optional_str(data: Mapping[str, object], key: str, default: str) -> str:
    """读取可选字符串字段。"""
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_int(data: Mapping[str, object], key: str) -> int:
    """读取 int 字段并拒绝 bool。"""
    value = _required(data, key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an int")
    return value


def _required_int_tuple(data: Mapping[str, object], key: str) -> tuple[int, ...]:
    """读取 int 序列字段并拒绝 bool。"""
    value = _required(data, key)
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise TypeError(f"{key} must be a JSON integer sequence")
    sequence = cast(Sequence[object], value)
    output: list[int] = []
    for index, item in enumerate(sequence):
        if isinstance(item, bool) or not isinstance(item, int):
            raise TypeError(f"{key}[{index}] must be an int")
        output.append(item)
    return tuple(output)


def _required_fixed_int_tuple(
    data: Mapping[str, object],
    key: str,
    *,
    length: int,
) -> tuple[int, int, int]:
    """读取固定长度三元 int 字段。"""
    values = _required_int_tuple(data, key)
    if len(values) != length:
        raise ValueError(f"{key} must have {length} entries")
    return (values[0], values[1], values[2])


def _mapping_from_object(value: object, *, name: str) -> dict[str, object]:
    """校验 string-key mapping 并复制为普通 dict。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    mapping = cast(Mapping[object, object], value)
    output: dict[str, object] = {}
    for raw_key, raw_value in mapping.items():
        if not isinstance(raw_key, str):
            raise TypeError(f"{name} keys must be strings")
        output[raw_key] = raw_value
    return output


def _required_mapping(data: Mapping[str, object], key: str) -> dict[str, object]:
    """读取 string-key mapping 字段。"""
    return _mapping_from_object(_required(data, key), name=key)


def _required_mapping_tuple(
    data: Mapping[str, object],
    key: str,
) -> tuple[Mapping[str, object], ...]:
    """读取 sample_source mapping 序列。"""
    value = _required(data, key)
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise TypeError(f"{key} must be a sequence of mappings")
    sequence = cast(Sequence[object], value)
    return tuple(
        _mapping_from_object(item, name=f"{key}[{index}]") for index, item in enumerate(sequence)
    )


def _required_float_mapping(data: Mapping[str, object], key: str) -> dict[str, float]:
    """读取有限 float metric 映射。"""
    mapping = _required_mapping(data, key)
    output: dict[str, float] = {}
    for metric_name, metric_value in mapping.items():
        if isinstance(metric_value, bool) or not isinstance(metric_value, (int, float)):
            raise TypeError(f"{key}.{metric_name} must be numeric")
        value = float(metric_value)
        if not math.isfinite(value):
            raise ValueError(f"{key}.{metric_name} must be finite")
        output[metric_name] = value
    return output


def write_checkpoint_manifest(path: Path, manifest: CheckpointManifest) -> Path:
    """把 checkpoint manifest 写为稳定 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.to_json_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def read_checkpoint_manifest(path: Path) -> CheckpointManifest:
    """读取并校验 checkpoint manifest。"""
    data: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise TypeError("checkpoint manifest must be a JSON object")
    return CheckpointManifest.from_json_dict(cast(Mapping[str, object], data))
