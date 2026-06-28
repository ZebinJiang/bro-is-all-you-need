"""M2 动作模式转换。"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from autovla.core.types import RawSample
from autovla.dataloader.contracts import TransformSpec

ActionMode = Literal["absolute", "delta", "relative"]
ReferenceFrame = Literal["world", "previous_action", "state"]
FirstStepPolicy = Literal["absolute", "zero"]
FloatArray = NDArray[np.float32]


class ActionModeTransform:
    """在 absolute/delta/relative 动作表示之间转换。"""

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
        if mode not in {"absolute", "delta", "relative"}:
            raise ValueError("unsupported action mode")
        if mode == "absolute" and reference_frame != "world":
            raise ValueError("absolute mode reference_frame must be world")
        if mode == "delta" and reference_frame != "previous_action":
            raise ValueError("delta mode reference_frame must be previous_action")
        if mode == "relative" and reference_frame != "state":
            raise ValueError("relative mode reference_frame must be state")
        if mode == "relative" and not state_to_action_indices:
            raise ValueError("relative mode requires state_to_action_indices")
        if first_step_policy not in {"absolute", "zero"}:
            raise ValueError("first_step_policy must be absolute or zero")
        if any(index < 0 for index in state_to_action_indices):
            raise ValueError("state_to_action_indices must be non-negative")
        if len(set(state_to_action_indices)) != len(state_to_action_indices):
            raise ValueError("state_to_action_indices must not contain duplicates")
        self.mode: ActionMode = mode
        self.reference_frame: ReferenceFrame = reference_frame
        self.first_step_policy: FirstStepPolicy = first_step_policy
        self.state_to_action_indices: tuple[int, ...] = state_to_action_indices
        self.first_action_reference: tuple[float, ...] | None = (
            tuple(float(value) for value in first_action_reference)
            if first_action_reference is not None
            else None
        )
        self.inverse_mode: bool = inverse_mode

    def inverse(self) -> "ActionModeTransform":
        """返回逆转换。"""
        return ActionModeTransform(
            mode=self.mode,
            reference_frame=self.reference_frame,
            first_step_policy=self.first_step_policy,
            state_to_action_indices=self.state_to_action_indices,
            first_action_reference=self.first_action_reference,
            inverse_mode=not self.inverse_mode,
        )

    def __call__(self, sample: RawSample) -> RawSample:
        """转换样本动作表示。"""
        if sample.actions is None:
            raise ValueError("actions are required for action mode transform")
        actions: FloatArray = np.asarray(sample.actions, dtype=np.float32)
        if actions.ndim != 2 or actions.shape[0] == 0:
            raise ValueError("actions horizon must be non-empty")
        if self.mode == "absolute":
            return replace(sample, actions=actions)
        if self.mode == "delta":
            output = (
                self._delta_to_absolute(actions)
                if self.inverse_mode
                else self._absolute_to_delta(actions)
            )
            return replace(sample, actions=output)
        output = (
            self._relative_to_absolute(sample, actions)
            if self.inverse_mode
            else self._absolute_to_relative(sample, actions)
        )
        return replace(sample, actions=output)

    def _absolute_to_delta(self, actions: FloatArray) -> FloatArray:
        """absolute -> delta。"""
        output: FloatArray = np.empty_like(actions)
        if self.first_step_policy == "absolute":
            output[0] = actions[0]
        else:
            output[0] = 0.0
        output[1:] = actions[1:] - actions[:-1]
        return output

    def _delta_to_absolute(self, actions: FloatArray) -> FloatArray:
        """delta -> absolute。"""
        output: FloatArray = np.empty_like(actions)
        if self.first_step_policy == "absolute":
            output[0] = actions[0]
        else:
            if self.first_action_reference is None:
                raise ValueError(
                    "zero first_step_policy is non-invertible without first_action_reference"
                )
            reference = np.asarray(self.first_action_reference, dtype=np.float32)
            if reference.shape != actions[0].shape:
                raise ValueError("first_action_reference dimension must match action_dim")
            output[0] = reference
        for index in range(1, actions.shape[0]):
            output[index] = output[index - 1] + actions[index]
        return output

    def _state_reference(self, sample: RawSample, action_dim: int) -> FloatArray:
        """按显式映射取 state 参考向量。"""
        if sample.state is None:
            raise ValueError("state is required for relative action mode")
        if len(self.state_to_action_indices) != action_dim:
            raise ValueError("state_to_action_indices length must match action_dim")
        state: FloatArray = np.asarray(sample.state, dtype=np.float32)
        if state.ndim != 1:
            raise ValueError("relative action mode requires one-dimensional state")
        try:
            return state[np.asarray(self.state_to_action_indices, dtype=np.int64)]
        except IndexError as exc:
            raise ValueError("state_to_action_indices out of bounds") from exc

    def _absolute_to_relative(self, sample: RawSample, actions: FloatArray) -> FloatArray:
        """absolute -> relative。"""
        reference = self._state_reference(sample, actions.shape[1])
        return actions - reference

    def _relative_to_absolute(self, sample: RawSample, actions: FloatArray) -> FloatArray:
        """relative -> absolute。"""
        reference = self._state_reference(sample, actions.shape[1])
        return actions + reference

    def to_spec(self) -> TransformSpec:
        """返回可重建的动作模式配置。"""
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
