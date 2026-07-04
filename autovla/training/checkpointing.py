"""AutoVLA 训练主干 checkpoint manifest 兼容性模型。"""

from __future__ import annotations

from dataclasses import dataclass


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

    def __post_init__(self) -> None:
        """校验 manifest 非空且 step 合法。"""
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty")
        if self.step < 0:
            raise ValueError("step must be non-negative")
        if self.schema_version != "autovla.training_checkpoint_manifest.v1":
            raise ValueError("unsupported checkpoint manifest schema_version")

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
