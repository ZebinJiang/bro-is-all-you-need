"""M2 动作模式薄适配器, 数值语义委托给规范变换阶段。"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

import numpy as np

from autovla.core.types import RawSample
from autovla.data.transforms import RelativeActionStage
from autovla.dataloader.contracts import TransformSpec

ActionMode = Literal["absolute", "delta", "relative"]
ReferenceFrame = Literal["world", "previous_action", "state"]
FirstStepPolicy = Literal["absolute", "zero"]


class ActionModeTransform:
    """把旧 RawSample 调用边界适配到规范 relative-action 阶段。"""

    def __init__(
        self,
        *,
        mode: ActionMode,
        reference_frame: ReferenceFrame,
        first_step_policy: FirstStepPolicy = "absolute",
        state_to_action_indices: tuple[int, ...] = (),
        first_action_reference: tuple[float, ...] | None = None,
        inverse_mode: bool = False,
    ) -> None:
        """保存旧配置并在边界处验证其可逆含义。"""
        expected = {"absolute": "world", "delta": "previous_action", "relative": "state"}
        if mode not in expected or expected[mode] != reference_frame:
            raise ValueError("unsupported action mode or reference frame")
        if mode == "relative" and not state_to_action_indices:
            raise ValueError("relative mode requires state_to_action_indices")
        if first_step_policy not in {"absolute", "zero"}:
            raise ValueError("first_step_policy must be absolute or zero")
        if any(index < 0 for index in state_to_action_indices) or len(
            set(state_to_action_indices)
        ) != len(state_to_action_indices):
            raise ValueError("state_to_action_indices must be unique and non-negative")
        self.mode: ActionMode = mode
        self.reference_frame: ReferenceFrame = reference_frame
        self.first_step_policy: FirstStepPolicy = first_step_policy
        self.state_to_action_indices = state_to_action_indices
        self.first_action_reference = first_action_reference
        self.inverse_mode = inverse_mode

    def inverse(self) -> "ActionModeTransform":
        """返回共享配置的逆向适配器。"""
        return ActionModeTransform(
            mode=self.mode,
            reference_frame=self.reference_frame,
            first_step_policy=self.first_step_policy,
            state_to_action_indices=self.state_to_action_indices,
            first_action_reference=self.first_action_reference,
            inverse_mode=not self.inverse_mode,
        )

    def __call__(self, sample: RawSample) -> RawSample:
        """转换旧样本动作并保留其余字段。"""
        if sample.actions is None:
            raise ValueError("actions are required for action mode transform")
        actions = np.asarray(sample.actions, dtype=np.float32)
        if actions.ndim != 2 or actions.shape[0] == 0:
            raise ValueError("actions horizon must be non-empty")
        if self.mode == "absolute":
            return replace(sample, actions=np.array(actions, copy=True))
        if self.mode == "delta" and self.first_step_policy == "zero":
            if self.inverse_mode:
                if self.first_action_reference is None:
                    raise ValueError(
                        "zero first_step_policy is non-invertible without first_action_reference"
                    )
                restored = np.empty_like(actions)
                reference = np.asarray(self.first_action_reference, dtype=np.float32)
                if reference.shape != actions[0].shape:
                    raise ValueError("first_action_reference dimension must match action_dim")
                restored[0] = reference
                for index in range(1, actions.shape[0]):
                    restored[index] = restored[index - 1] + actions[index]
                return replace(sample, actions=restored)
            stage = RelativeActionStage(mode="previous_delta")
            output = stage.forward({"actions": actions})["actions"]
            converted = np.asarray(output).copy()
            converted[0] = 0.0
            return replace(sample, actions=converted)
        if self.mode == "delta":
            stage = RelativeActionStage(mode="previous_delta")
            method = stage.inverse if self.inverse_mode else stage.forward
            return replace(sample, actions=method({"actions": actions})["actions"])
        if sample.state is None:
            raise ValueError("state is required for relative action mode")
        if np.asarray(sample.state).ndim != 1:
            raise ValueError("relative action mode requires one-dimensional state")
        if len(self.state_to_action_indices) != actions.shape[1]:
            raise ValueError("state_to_action_indices length must match action_dim")
        stage = RelativeActionStage(
            mode="state_relative",
            action_dimensions=tuple(range(actions.shape[1])),
            state_indices=self.state_to_action_indices,
        )
        method = stage.inverse if self.inverse_mode else stage.forward
        return replace(
            sample,
            actions=method({"actions": actions, "state": sample.state})["actions"],
        )

    def to_spec(self) -> TransformSpec:
        """返回旧注册表可重建配置。"""
        params: dict[str, object] = {
            "mode": self.mode,
            "reference_frame": self.reference_frame,
            "first_step_policy": self.first_step_policy,
            "state_to_action_indices": self.state_to_action_indices,
            "inverse_mode": self.inverse_mode,
        }
        if self.first_action_reference is not None:
            params["first_action_reference"] = self.first_action_reference
        return TransformSpec(name="action_mode", params=params)


__all__ = ["ActionModeTransform"]
