"""AutoVLA 训练主干的轻量公共契约。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from autovla.core.types import FrameworkOutput, ModelInput, TrainingBatch


@runtime_checkable
class BatchAdapter(Protocol):
    """模型族把通用 ``TrainingBatch`` 转成 ``ModelInput`` 的协议。"""

    def to_model_input(self, batch: TrainingBatch) -> ModelInput:
        """执行无 IO 的 batch 转换。"""
        ...


@runtime_checkable
class TrainablePolicy(Protocol):
    """训练主干所需的最小策略协议。"""

    def setup(self) -> None:
        """初始化轻量状态, 不得隐藏下载或模型加载。"""
        ...

    def forward_loss(self, batch: ModelInput) -> FrameworkOutput:
        """执行一次可测试的前向损失计算。"""
        ...


@runtime_checkable
class LossAdapter(Protocol):
    """训练损失适配器协议。"""

    def compute(self, prediction: object, target: object, action_mask: object) -> object:
        """根据预测、目标和严格 action mask 返回损失对象。"""
        ...


@runtime_checkable
class CheckpointAdapter(Protocol):
    """checkpoint manifest 适配器协议。"""

    def write_manifest(self, path: object, manifest: object) -> object:
        """写出 JSON manifest, 不得写模型权重。"""
        ...

    def validate_resume(self, manifest: object, expected: object) -> int:
        """校验恢复兼容性并返回 step。"""
        ...
