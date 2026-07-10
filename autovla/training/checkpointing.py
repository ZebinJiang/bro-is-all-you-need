"""AutoVLA 训练主干 checkpoint manifest 兼容性模型。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast


def _require_exact_keys(payload: Mapping[str, object], expected: set[str], name: str) -> None:
    """校验 JSON object 只包含规范字段。"""
    actual = set(payload)
    if actual != expected:
        raise ValueError(f"{name} fields must be {sorted(expected)}, got {sorted(actual)}")


def _require_json_object(value: object, name: str) -> Mapping[str, object]:
    """校验值为字符串键 JSON object。"""
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a JSON object")
    raw = cast(Mapping[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{name} must be a JSON object")
    return cast(Mapping[str, object], raw)


def _require_json_int(value: object, name: str) -> int:
    """校验 JSON 整数并拒绝 bool。"""
    if type(value) is not int:
        raise ValueError(f"{name} must be an int")
    return value


def _require_json_text(value: object, name: str) -> str:
    """校验 JSON 非空字符串。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


@dataclass(frozen=True, slots=True)
class CheckpointCompatibilitySpec:
    """描述恢复 checkpoint 必须匹配的稳定字段。"""

    model_family_key: str
    model_registry_key: str
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str
    action_horizon: int
    action_dim: int

    def __post_init__(self) -> None:
        """校验兼容性字段完整。"""
        for name in (
            "model_family_key",
            "model_registry_key",
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.action_horizon <= 0:
            raise ValueError("action_horizon must be positive")
        if self.action_dim <= 0:
            raise ValueError("action_dim must be positive")


@dataclass(frozen=True, slots=True)
class TrainingCheckpointManifest:
    """只记录 JSON manifest 的 checkpoint 元数据, 不包含模型权重。"""

    run_id: str
    step: int
    compatibility: CheckpointCompatibilitySpec
    schema_version: str = "autovla.training_checkpoint_manifest.v1"
    weights_written: bool = False
    optimizer_state_written: bool = False

    def __post_init__(self) -> None:
        """校验 manifest 非空且 step 合法。"""
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty")
        if self.step < 0:
            raise ValueError("step must be non-negative")
        if self.schema_version != "autovla.training_checkpoint_manifest.v1":
            raise ValueError("unsupported checkpoint manifest schema_version")
        if self.weights_written or self.optimizer_state_written:
            raise ValueError("M4 checkpoint manifest must not write weights or optimizer state")

    def validate_resume(self, expected: CheckpointCompatibilitySpec) -> int:
        """校验恢复兼容性并返回 checkpoint step。"""
        if self.compatibility != expected:
            raise ValueError("checkpoint compatibility mismatch")
        return self.step

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "step": self.step,
            "weights_written": self.weights_written,
            "optimizer_state_written": self.optimizer_state_written,
            "compatibility": {
                "model_family_key": self.compatibility.model_family_key,
                "model_registry_key": self.compatibility.model_registry_key,
                "dataset_fingerprint": self.compatibility.dataset_fingerprint,
                "transform_fingerprint": self.compatibility.transform_fingerprint,
                "statistics_fingerprint": self.compatibility.statistics_fingerprint,
                "action_horizon": self.compatibility.action_horizon,
                "action_dim": self.compatibility.action_dim,
            },
        }

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, object]) -> TrainingCheckpointManifest:
        """从严格 schema JSON object 解码 metadata-only manifest。"""
        _require_exact_keys(
            payload,
            {
                "schema_version",
                "run_id",
                "step",
                "weights_written",
                "optimizer_state_written",
                "compatibility",
            },
            "checkpoint manifest",
        )
        if type(payload["weights_written"]) is not bool:
            raise ValueError("weights_written must be a bool")
        if type(payload["optimizer_state_written"]) is not bool:
            raise ValueError("optimizer_state_written must be a bool")
        compatibility = _require_json_object(payload["compatibility"], "compatibility")
        compatibility_fields = {
            "model_family_key",
            "model_registry_key",
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
            "action_horizon",
            "action_dim",
        }
        _require_exact_keys(compatibility, compatibility_fields, "compatibility")
        spec = CheckpointCompatibilitySpec(
            model_family_key=_require_json_text(
                compatibility["model_family_key"], "model_family_key"
            ),
            model_registry_key=_require_json_text(
                compatibility["model_registry_key"], "model_registry_key"
            ),
            dataset_fingerprint=_require_json_text(
                compatibility["dataset_fingerprint"], "dataset_fingerprint"
            ),
            transform_fingerprint=_require_json_text(
                compatibility["transform_fingerprint"], "transform_fingerprint"
            ),
            statistics_fingerprint=_require_json_text(
                compatibility["statistics_fingerprint"], "statistics_fingerprint"
            ),
            action_horizon=_require_json_int(compatibility["action_horizon"], "action_horizon"),
            action_dim=_require_json_int(compatibility["action_dim"], "action_dim"),
        )
        return cls(
            run_id=_require_json_text(payload["run_id"], "run_id"),
            step=_require_json_int(payload["step"], "step"),
            compatibility=spec,
            schema_version=_require_json_text(payload["schema_version"], "schema_version"),
            weights_written=payload["weights_written"],
            optimizer_state_written=payload["optimizer_state_written"],
        )

    @classmethod
    def read(cls, path: Path) -> TrainingCheckpointManifest:
        """从磁盘读取并严格解码 manifest。"""
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_json_dict(_require_json_object(payload, "checkpoint manifest"))
