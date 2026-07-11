"""无端点行为的本地推理策略契约。"""

from __future__ import annotations

from collections.abc import Callable

from autovla.core.types.training import TrainingBatch


class InferencePolicy:
    """包装本地模型预测函数,不拥有服务、端点或机器人循环。"""

    def __init__(self, predictor: Callable[[TrainingBatch], object]) -> None:
        """保存调用方提供的本地预测函数。"""
        self._predictor = predictor

    def predict(self, batch: TrainingBatch) -> object:
        """返回调用方拥有的本地动作预测值。"""
        return self._predictor(batch)


__all__ = ["InferencePolicy"]
