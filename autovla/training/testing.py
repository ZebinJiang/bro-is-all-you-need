"""训练 smoke 使用的确定性 FrameworkProtocol test double。"""

from __future__ import annotations

import math
from typing import cast

import numpy as np

from autovla.core.types import ActionChunk, ActionMask, FrameworkOutput, ModelInput, NumericArray
from autovla.training.losses import masked_action_mse, validate_action_mask


def _actions_from_input(model_input: ModelInput) -> NumericArray:
    """从 ModelInput 读取动作目标。"""
    if "actions" not in model_input.tensors:
        raise ValueError("ModelInput tensors must contain actions")
    actions = np.asarray(model_input.tensors["actions"])
    if actions.ndim != 3 or not np.issubdtype(actions.dtype, np.number):
        raise ValueError("actions must be numeric [B,H,D]")
    owned: NumericArray = np.array(actions, copy=True)
    owned.setflags(write=False)
    return owned


def _mask_from_input(model_input: ModelInput, action_shape: tuple[int, ...]) -> ActionMask:
    """从 ModelInput metadata 读取严格 bool action mask。"""
    if "action_mask" not in model_input.metadata:
        raise ValueError("ModelInput metadata must contain action_mask")
    return validate_action_mask(model_input.metadata["action_mask"], action_shape)


class DeterministicActionFramework:
    """返回常量动作预测的 CPU-only 测试框架。"""

    def __init__(self, *, prediction_value: float = 0.0) -> None:
        """初始化固定预测值。"""
        if not math.isfinite(prediction_value):
            raise ValueError("prediction_value must be finite")
        self._prediction_value = float(prediction_value)

    def forward(self, batch: ModelInput) -> FrameworkOutput:
        """执行确定性前向, 并返回 masked action loss。"""
        actions = _actions_from_input(batch)
        mask = _mask_from_input(batch, actions.shape)
        prediction = cast(
            NumericArray,
            np.full(actions.shape, self._prediction_value, dtype=np.float32),
        )
        prediction.setflags(write=False)
        loss = masked_action_mse(prediction, actions, mask)
        first_mask: ActionMask = np.array(mask[0], dtype=np.bool_, copy=True)
        first_mask.setflags(write=False)
        action_pred = ActionChunk(
            values=cast(NumericArray, prediction[0]),
            mask=first_mask,
            horizon=int(actions.shape[1]),
            action_dim=int(actions.shape[2]),
            normalized=True,
        )
        return FrameworkOutput(
            loss=loss.value,
            losses={"action": loss.value},
            metrics={
                "batch_size": float(actions.shape[0]),
                "valid_action_elements": float(loss.valid_count),
                "masked_action_mse": loss.value,
            },
            action_pred=action_pred,
        )

    def predict_action(self, observation: ModelInput) -> ActionChunk:
        """返回第一条样本的确定性动作预测。"""
        output = self.forward(observation)
        if output.action_pred is None:
            raise ValueError("deterministic framework must produce action_pred")
        return output.action_pred
