"""AutoVLA 测试命名空间中的确定性训练组件。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from autovla.core.types import BatchSample, ModelInput, NumericArray, RawSample, TrainingBatch
from autovla.training.checkpointing import (
    CheckpointCompatibilitySpec,
    TrainingCheckpointManifest,
)
from autovla.training.losses import MaskedActionLoss, masked_action_mse
from autovla.training.metrics import write_stable_json

TEST_DOUBLE_CAMERAS = ("camera.rgb_0", "camera.rgb_1", "camera.rgb_2")


@dataclass(frozen=True, slots=True)
class DisabledDeploymentHook:
    """返回运行时未激活的部署边界证据。"""

    def to_json_dict(self) -> dict[str, object]:
        """返回无端点、无动作发射的稳定元数据。"""
        return {"status": "disabled", "endpoint_used": False, "actions_emitted": 0}


class TestDoubleBatchAdapter:
    """严格校验 test-double 输入并转换为 numpy-only ModelInput。"""

    def __init__(self, *, action_horizon: int, action_dim: int) -> None:
        """记录配置声明的动作形状。"""
        if action_horizon <= 0 or action_dim <= 0:
            raise ValueError("test_double action shape must be positive")
        self._action_horizon = action_horizon
        self._action_dim = action_dim

    def to_model_input(self, batch: TrainingBatch) -> ModelInput:
        """在策略执行前校验三相机、状态、动作、mask 和归一化边界。"""
        if tuple(sorted(batch.images)) != TEST_DOUBLE_CAMERAS:
            raise ValueError(f"test_double cameras must be exactly {TEST_DOUBLE_CAMERAS}")
        if batch.state is None:
            raise ValueError("test_double state is required")
        if batch.actions.shape != (
            batch.batch_size,
            self._action_horizon,
            self._action_dim,
        ):
            raise ValueError(
                "test_double actions must match configured [B,H,D] "
                f"shape ({batch.batch_size}, {self._action_horizon}, {self._action_dim})"
            )
        if batch.action_mask.dtype != np.dtype(np.bool_):
            raise TypeError("test_double action_mask must be strict bool")
        if batch.action_mask.shape != batch.actions.shape:
            raise ValueError("test_double action_mask must match actions shape")

        samples = tuple(
            RawSample(
                images={name: value[index] for name, value in batch.images.items()},
                language=batch.language[index],
                actions=batch.actions[index],
                state=batch.state[index],
                robot_tag="autovla-test-double",
                metadata={"action_mask": batch.action_mask[index]},
            )
            for index in range(batch.batch_size)
        )
        tensors: dict[str, NumericArray] = {
            "actions": batch.actions,
            "state": batch.state,
            **{f"image.{name}": value for name, value in batch.images.items()},
        }
        metadata: dict[str, object] = {
            "action_dim": batch.action_dim,
            "action_horizon": batch.action_horizon,
            "action_mask": batch.action_mask,
            "model_metadata_key": "test_double",
            "normalization_mode": "identity",
            "statistics_fingerprint": batch.statistics_fingerprint,
        }
        fingerprint = batch.metadata.get("logical_batch_fingerprint")
        if fingerprint is not None:
            if not isinstance(fingerprint, str) or not fingerprint.strip():
                raise ValueError(
                    "logical_batch_fingerprint must be a non-empty string when present"
                )
            metadata["logical_batch_fingerprint"] = fingerprint
        return ModelInput(
            batch=BatchSample(samples=samples, metadata={"model_metadata_key": "test_double"}),
            tensors=tensors,
            metadata=metadata,
        )


class DeterministicTestPolicy:
    """不含梯度或模型参数的唯一确定性批量动作实现。"""

    def __init__(self, *, seed: int, prediction_value: float | None = None) -> None:
        """记录 seed 和可选兼容固定预测值。"""
        if prediction_value is not None and not math.isfinite(prediction_value):
            raise ValueError("prediction_value must be finite")
        self.seed = seed
        self._prediction_value = prediction_value
        self._ready = False

    def setup(self) -> None:
        """标记本地策略可用,不加载任何资产。"""
        self._ready = True

    def predict_actions(self, batch: ModelInput) -> NumericArray:
        """返回固定值或目标动作加 0.1 的只读预测。"""
        if not self._ready:
            raise RuntimeError("policy setup must run before prediction")
        target = np.asarray(batch.tensors["actions"], dtype=np.float32)
        if target.ndim != 3:
            raise ValueError("policy actions must have [B,H,D] shape")
        if self._prediction_value is None:
            prediction = np.array(target + np.float32(0.1), dtype=np.float32)
        else:
            prediction = np.full(target.shape, self._prediction_value, dtype=np.float32)
        prediction.setflags(write=False)
        return prediction


class MaskedActionMseAdapter:
    """复用现有 numpy masked action MSE 的唯一适配器。"""

    def compute(self, prediction: object, target: object, action_mask: object) -> MaskedActionLoss:
        """计算严格 bool action mask 下的 MSE。"""
        return masked_action_mse(prediction, target, action_mask)


class ManifestOnlyCheckpointAdapter:
    """实现规范 metadata-only checkpoint 写入和恢复校验。"""

    def write_manifest(self, path: Path, manifest: TrainingCheckpointManifest) -> Path:
        """写出稳定 JSON manifest。"""
        return write_stable_json(path, manifest.to_json_dict())

    def read_manifest(self, path: Path) -> TrainingCheckpointManifest:
        """从磁盘严格读取 metadata-only manifest。"""
        return TrainingCheckpointManifest.read(path)

    def validate_resume(
        self,
        manifest: TrainingCheckpointManifest,
        expected: CheckpointCompatibilitySpec,
    ) -> int:
        """使用规范兼容性元数据校验恢复。"""
        return manifest.validate_resume(expected)

    def write(self, path: Path, manifest: TrainingCheckpointManifest) -> Path:
        """兼容旧名称并转发到规范写入方法。"""
        return self.write_manifest(path, manifest)


__all__ = [
    "TEST_DOUBLE_CAMERAS",
    "DeterministicTestPolicy",
    "DisabledDeploymentHook",
    "ManifestOnlyCheckpointAdapter",
    "MaskedActionMseAdapter",
    "TestDoubleBatchAdapter",
]
