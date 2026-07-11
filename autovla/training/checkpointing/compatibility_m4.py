"""M4 metadata-only checkpoint manifest 的只读兼容叶。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast


def _object(value: object, name: str) -> Mapping[str, object]:
    """校验字符串键 JSON object。"""

    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a JSON object")
    raw = cast(Mapping[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{name} must be a JSON object")
    return cast(Mapping[str, object], raw)


def _text(value: object, name: str) -> str:
    """校验非空 JSON 字符串。"""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _integer(value: object, name: str) -> int:
    """校验 JSON 整数并拒绝 bool。"""

    if type(value) is not int:
        raise ValueError(f"{name} must be an int")
    return value


@dataclass(frozen=True, slots=True)
class CheckpointCompatibilitySpec:
    """保留 M4 恢复匹配字段,不用于生产 checkpoint 写入。"""

    model_family_key: str
    model_registry_key: str
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str
    action_horizon: int
    action_dim: int

    def __post_init__(self) -> None:
        """校验旧 manifest 兼容字段。"""

        for name in (
            "model_family_key",
            "model_registry_key",
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
        ):
            _text(getattr(self, name), name)
        if self.action_horizon <= 0 or self.action_dim <= 0:
            raise ValueError("action_horizon and action_dim must be positive")


@dataclass(frozen=True, slots=True)
class TrainingCheckpointManifest:
    """读取和表示 M4 metadata-only manifest,禁止权重写入语义。"""

    run_id: str
    step: int
    compatibility: CheckpointCompatibilitySpec
    schema_version: str = "autovla.training_checkpoint_manifest.v1"
    weights_written: bool = False
    optimizer_state_written: bool = False

    def __post_init__(self) -> None:
        """校验旧 schema 和 metadata-only 不变量。"""

        _text(self.run_id, "run_id")
        if self.step < 0:
            raise ValueError("step must be non-negative")
        if self.schema_version != "autovla.training_checkpoint_manifest.v1":
            raise ValueError("unsupported checkpoint manifest schema_version")
        if self.weights_written or self.optimizer_state_written:
            raise ValueError("M4 checkpoint manifest must remain metadata-only")

    def validate_resume(self, expected: CheckpointCompatibilitySpec) -> int:
        """校验旧兼容字段并返回旧 checkpoint 步数。"""

        if self.compatibility != expected:
            raise ValueError("checkpoint compatibility mismatch")
        return self.step

    def to_json_dict(self) -> dict[str, object]:
        """返回与旧 schema 完全一致的 JSON 表示。"""

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
    def from_json_dict(cls, payload: Mapping[str, object]) -> "TrainingCheckpointManifest":
        """严格解码旧 metadata-only manifest。"""

        expected = {
            "schema_version",
            "run_id",
            "step",
            "weights_written",
            "optimizer_state_written",
            "compatibility",
        }
        if set(payload) != expected:
            raise ValueError("legacy checkpoint manifest fields do not match schema")
        if (
            type(payload["weights_written"]) is not bool
            or type(payload["optimizer_state_written"]) is not bool
        ):
            raise ValueError("legacy checkpoint write flags must be bool")
        compatibility = _object(payload["compatibility"], "compatibility")
        fields = {
            "model_family_key",
            "model_registry_key",
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
            "action_horizon",
            "action_dim",
        }
        if set(compatibility) != fields:
            raise ValueError("legacy compatibility fields do not match schema")
        return cls(
            run_id=_text(payload["run_id"], "run_id"),
            step=_integer(payload["step"], "step"),
            compatibility=CheckpointCompatibilitySpec(
                model_family_key=_text(compatibility["model_family_key"], "model_family_key"),
                model_registry_key=_text(compatibility["model_registry_key"], "model_registry_key"),
                dataset_fingerprint=_text(
                    compatibility["dataset_fingerprint"], "dataset_fingerprint"
                ),
                transform_fingerprint=_text(
                    compatibility["transform_fingerprint"], "transform_fingerprint"
                ),
                statistics_fingerprint=_text(
                    compatibility["statistics_fingerprint"], "statistics_fingerprint"
                ),
                action_horizon=_integer(compatibility["action_horizon"], "action_horizon"),
                action_dim=_integer(compatibility["action_dim"], "action_dim"),
            ),
            schema_version=_text(payload["schema_version"], "schema_version"),
            weights_written=payload["weights_written"],
            optimizer_state_written=payload["optimizer_state_written"],
        )

    @classmethod
    def read(cls, path: Path) -> "TrainingCheckpointManifest":
        """从本地文件读取旧 manifest,不加载任何权重。"""

        return cls.from_json_dict(_object(json.loads(path.read_text(encoding="utf-8")), "manifest"))


__all__ = ["CheckpointCompatibilitySpec", "TrainingCheckpointManifest"]
