"""M4 训练组件的通用 Registry 工厂命名空间。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import numpy as np

from autovla.core.registry import Registry
from autovla.core.runtime import RuntimePlan
from autovla.core.types import BatchSample, ModelInput, NumericArray, RawSample, TrainingBatch
from autovla.models.family import ModelFamilySpec
from autovla.models.registry import get_model_family_spec
from autovla.training.checkpointing import TrainingCheckpointManifest
from autovla.training.losses import MaskedActionLoss, masked_action_mse
from autovla.training.metrics import write_stable_json


class PolicyFactoryProduct(Protocol):
    """定义 M4 确定性测试策略的最小执行接口。"""

    def setup(self) -> None:
        """执行无 IO 初始化。"""
        ...

    def predict_actions(self, batch: ModelInput) -> NumericArray:
        """返回与目标动作同形状的确定性预测。"""
        ...


class LossFactoryProduct(Protocol):
    """定义严格 bool mask 损失接口。"""

    def compute(self, prediction: object, target: object, action_mask: object) -> MaskedActionLoss:
        """返回 masked action loss。"""
        ...


class CheckpointFactoryProduct(Protocol):
    """定义 metadata-only checkpoint 写入接口。"""

    def write(self, path: Path, manifest: TrainingCheckpointManifest) -> Path:
        """只写 JSON manifest。"""
        ...


@dataclass(frozen=True, slots=True)
class DisabledDeploymentHook:
    """返回运行时未激活的部署边界证据。"""

    def to_json_dict(self) -> dict[str, object]:
        """返回无端点、无动作发射的稳定元数据。"""
        return {"status": "disabled", "endpoint_used": False, "actions_emitted": 0}


class TestDoubleBatchAdapter:
    """把规范 TrainingBatch 转为 numpy-only ModelInput。"""

    def to_model_input(self, batch: TrainingBatch) -> ModelInput:
        """执行无模型、无 IO 的逐样本适配。"""
        samples = tuple(
            RawSample(
                images={name: value[index] for name, value in batch.images.items()},
                language=batch.language[index],
                actions=batch.actions[index],
                state=batch.state[index] if batch.state is not None else None,
                robot_tag="autovla-test-double",
                metadata={"action_mask": batch.action_mask[index]},
            )
            for index in range(batch.batch_size)
        )
        tensors: dict[str, NumericArray] = {
            "actions": batch.actions,
            **{f"image.{name}": value for name, value in batch.images.items()},
        }
        if batch.state is not None:
            tensors["state"] = batch.state
        return ModelInput(
            batch=BatchSample(samples=samples, metadata={"model_metadata_key": "test_double"}),
            tensors=tensors,
            metadata={
                "action_mask": batch.action_mask,
                "model_metadata_key": "test_double",
                "logical_batch_fingerprint": batch.metadata["logical_batch_fingerprint"],
            },
        )


class DeterministicTestPolicy:
    """不含梯度或模型参数的确定性测试策略。"""

    def __init__(self, *, seed: int) -> None:
        """记录固定 seed。"""
        self.seed = seed
        self._ready = False

    def setup(self) -> None:
        """标记本地策略可用,不加载任何资产。"""
        self._ready = True

    def predict_actions(self, batch: ModelInput) -> NumericArray:
        """返回目标动作加固定偏移的只读预测。"""
        if not self._ready:
            raise RuntimeError("policy setup must run before prediction")
        target = np.asarray(batch.tensors["actions"], dtype=np.float32)
        prediction: NumericArray = np.array(target + np.float32(0.1), copy=True)
        prediction.setflags(write=False)
        return prediction


class MaskedActionMseAdapter:
    """复用现有 numpy masked action MSE。"""

    def compute(self, prediction: object, target: object, action_mask: object) -> MaskedActionLoss:
        """计算严格 bool action mask 下的 MSE。"""
        return masked_action_mse(prediction, target, action_mask)


class ManifestOnlyCheckpointAdapter:
    """只写 TrainingCheckpointManifest JSON,不写权重。"""

    def write(self, path: Path, manifest: TrainingCheckpointManifest) -> Path:
        """写出稳定 JSON manifest。"""
        return write_stable_json(path, manifest.to_json_dict())


BatchAdapterFactory = Callable[[], TestDoubleBatchAdapter]
PolicyFactory = Callable[[int], PolicyFactoryProduct]
LossFactory = Callable[[], LossFactoryProduct]
CheckpointFactory = Callable[[], CheckpointFactoryProduct]
RuntimePlanFactory = Callable[[], RuntimePlan]
DeploymentHookFactory = Callable[[], DisabledDeploymentHook]
ModelFamilyFactory = Callable[[], ModelFamilySpec]

BATCH_ADAPTER_FACTORIES: Registry[BatchAdapterFactory] = Registry("batch-adapter-factories")
POLICY_FACTORIES: Registry[PolicyFactory] = Registry("policy-factories")
LOSS_FACTORIES: Registry[LossFactory] = Registry("loss-factories")
CHECKPOINT_FACTORIES: Registry[CheckpointFactory] = Registry("checkpoint-factories")
RUNTIME_PLAN_FACTORIES: Registry[RuntimePlanFactory] = Registry("runtime-plan-factories")
DEPLOYMENT_HOOK_FACTORIES: Registry[DeploymentHookFactory] = Registry("deployment-hook-factories")
MODEL_FAMILY_FACTORIES: Registry[ModelFamilyFactory] = Registry("model-family-factories")

BATCH_ADAPTER_FACTORIES.register("test_double_batch_v1", TestDoubleBatchAdapter)
POLICY_FACTORIES.register(
    "deterministic_test_policy_v1", lambda seed: DeterministicTestPolicy(seed=seed)
)
LOSS_FACTORIES.register("masked_action_mse_v1", MaskedActionMseAdapter)
CHECKPOINT_FACTORIES.register("manifest_only_v1", ManifestOnlyCheckpointAdapter)
RUNTIME_PLAN_FACTORIES.register(
    "local_cpu_dry_run_v1",
    lambda: RuntimePlan(mode="local_cpu_smoke"),
)
DEPLOYMENT_HOOK_FACTORIES.register("disabled_deployment_v1", DisabledDeploymentHook)
for _model_key in ("test_double", "gr00t_n1d6_metadata", "pi0_metadata", "pi05_metadata"):
    MODEL_FAMILY_FACTORIES.register(
        _model_key,
        cast(ModelFamilyFactory, lambda key=_model_key: get_model_family_spec(key)),
    )


__all__ = [
    "BATCH_ADAPTER_FACTORIES",
    "CHECKPOINT_FACTORIES",
    "DEPLOYMENT_HOOK_FACTORIES",
    "LOSS_FACTORIES",
    "MODEL_FAMILY_FACTORIES",
    "POLICY_FACTORIES",
    "RUNTIME_PLAN_FACTORIES",
    "DisabledDeploymentHook",
]
