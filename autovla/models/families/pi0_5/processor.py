"""Pi0.5 严格图像、token、mask 与 quantile 处理器。

设计参考: OpenPI@15a9616a00943ada6c20a0f158e3adb39df2ccac,Apache-2.0。
仅保留公开数据契约;tokenizer、统计资产和 checkpoint 必须另行收据。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from autovla.models.families.pi0_5.config import Pi05Config

_FloatArray: TypeAlias = NDArray[np.float32]
_BoolArray: TypeAlias = NDArray[np.bool_]


class Pi05Processor:
    """在 CPU 数组上关闭输入形状、严格 mask 和可逆 quantile 顺序。"""

    camera_order = ("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb")

    def __init__(self, config: Pi05Config, q01: object, q99: object) -> None:
        """复制并冻结动作 quantile,避免调用方后续修改统计身份。"""

        self.config = config
        lower = np.array(q01, dtype=np.float32, copy=True)
        upper = np.array(q99, dtype=np.float32, copy=True)
        expected = (config.action_dimension,)
        if lower.shape != expected or upper.shape != expected:
            raise ValueError("q01/q99 must exactly match action dimension")
        if not np.isfinite(lower).all() or not np.isfinite(upper).all():
            raise ValueError("quantile statistics must be finite")
        if np.any(upper <= lower):
            raise ValueError("active q99 values must be strictly greater than q01")
        lower.setflags(write=False)
        upper.setflags(write=False)
        self._q01 = lower
        self._q99 = upper

    def validate_images(
        self, images: Mapping[str, object], image_masks: Mapping[str, object]
    ) -> tuple[_FloatArray, _BoolArray]:
        """按固定三相机顺序返回 ``[B,3,3,224,224]`` 与严格 ``[B,3]`` mask。"""

        if tuple(images) != self.camera_order or tuple(image_masks) != self.camera_order:
            raise ValueError("images and masks must use the exact ordered Pi0.5 camera keys")
        tensors: list[_FloatArray] = []
        masks: list[_BoolArray] = []
        batch_size: int | None = None
        for camera in self.camera_order:
            image = np.asarray(images[camera])
            mask = np.asarray(image_masks[camera])
            if image.dtype != np.float32:
                raise TypeError("Pi0.5 images must use float32")
            if image.ndim != 4 or image.shape[1:] != (
                3,
                self.config.image_size,
                self.config.image_size,
            ):
                raise ValueError("each image must use explicit NCHW [B,3,224,224]")
            if not np.isfinite(image).all() or np.any(image < -1.0) or np.any(image > 1.0):
                raise ValueError("Pi0.5 image values must be finite in [-1,1]")
            if mask.dtype != np.bool_ or mask.shape != (image.shape[0],):
                raise TypeError("each image mask must use strict bool [B]")
            batch_size = image.shape[0] if batch_size is None else batch_size
            if image.shape[0] != batch_size:
                raise ValueError("all camera batches must have equal size")
            tensors.append(np.array(image, copy=True))
            masks.append(np.array(mask, copy=True))
        return np.stack(tensors, axis=1), np.stack(masks, axis=1)

    def validate_prompt_state_tokens(
        self, token_ids: object, token_mask: object
    ) -> tuple[NDArray[np.int64], _BoolArray]:
        """要求 prompt/state 已显式截断或 padding 到不超过 200 token。"""

        ids = np.asarray(token_ids)
        mask = np.asarray(token_mask)
        if ids.dtype != np.int64 or ids.ndim != 2:
            raise TypeError("token_ids must use int64 [B,L]")
        if not 1 <= ids.shape[1] <= self.config.max_prompt_state_tokens:
            raise ValueError("prompt/state token length exceeds the 200-token contract")
        if mask.dtype != np.bool_ or mask.shape != ids.shape:
            raise TypeError("token_mask must use strict bool and match token_ids")
        if np.any(ids < 0):
            raise ValueError("token ids must be non-negative")
        return np.array(ids, copy=True), np.array(mask, copy=True)

    def quantize_state(self, normalized_state: object, state_mask: object) -> NDArray[np.int64]:
        """把 ``[-1,1]`` 状态按 256 bins 离散化,非活动维度保持零。"""

        state = np.asarray(normalized_state)
        mask = np.asarray(state_mask)
        if state.dtype != np.float32 or state.ndim != 2:
            raise TypeError("normalized_state must use float32 [B,D]")
        if mask.dtype != np.bool_ or mask.shape != state.shape:
            raise TypeError("state_mask must use strict bool and match state")
        if state.shape[1] != self.config.state_dimension or not np.isfinite(state).all():
            raise ValueError("state must match the fixed finite 32-dimension contract")
        clipped = np.clip(state, -1.0, 1.0)
        bins = np.floor((clipped + 1.0) * 0.5 * self.config.state_quantization_bins)
        bins = np.minimum(bins, self.config.state_quantization_bins - 1).astype(np.int64)
        return np.where(mask, bins, 0)

    def normalize_actions(
        self,
        actions: object,
        action_mask: object,
        *,
        to_model_semantics: Callable[[_FloatArray], _FloatArray] | None = None,
    ) -> _FloatArray:
        """先执行动作语义变换,再按 q01/q99 映射到模型空间。"""

        values, mask = self._actions_and_mask(actions, action_mask)
        inactive_identity = np.array(values, copy=True)
        if to_model_semantics is not None:
            values = self._validated_callback(to_model_semantics(values), values.shape)
        scale = self._q99 - self._q01 + np.float32(1e-6)
        normalized = (values - self._q01) / scale * np.float32(2.0) - np.float32(1.0)
        return np.where(mask, normalized, inactive_identity).astype(np.float32, copy=False)

    def denormalize_actions(
        self,
        normalized_actions: object,
        action_mask: object,
        *,
        to_physical_semantics: Callable[[_FloatArray], _FloatArray] | None = None,
    ) -> _FloatArray:
        """先反 quantile,再执行动作语义逆变换,严格保持正向逆序。"""

        values, mask = self._actions_and_mask(normalized_actions, action_mask)
        inactive_identity = np.array(values, copy=True)
        scale = self._q99 - self._q01 + np.float32(1e-6)
        restored = (values + np.float32(1.0)) * np.float32(0.5) * scale + self._q01
        restored = np.where(mask, restored, values).astype(np.float32, copy=False)
        if to_physical_semantics is not None:
            restored = self._validated_callback(to_physical_semantics(restored), values.shape)
        return np.where(mask, restored, inactive_identity).astype(np.float32, copy=False)

    def _actions_and_mask(
        self, actions: object, action_mask: object
    ) -> tuple[_FloatArray, _BoolArray]:
        """复制严格 ``[B,H,32]`` 动作和同形 bool mask。"""

        values = np.asarray(actions)
        mask = np.asarray(action_mask)
        expected_tail = (self.config.action_horizon, self.config.action_dimension)
        if values.dtype != np.float32 or values.ndim != 3 or values.shape[1:] != expected_tail:
            raise TypeError("actions must use float32 [B,H,32] with configured H")
        if mask.dtype != np.bool_ or mask.shape != values.shape:
            raise TypeError("action mask must use strict bool and exactly match actions")
        if not np.isfinite(values).all():
            raise ValueError("actions must be finite")
        return np.array(values, copy=True), np.array(mask, copy=True)

    @staticmethod
    def _validated_callback(value: object, shape: tuple[int, ...]) -> _FloatArray:
        """拒绝语义回调改变 dtype、形状或有限性。"""

        output = np.asarray(value)
        if output.dtype != np.float32 or output.shape != shape or not np.isfinite(output).all():
            raise ValueError(
                "action semantic transform must preserve shape, float32 and finiteness"
            )
        return np.array(output, copy=True)
