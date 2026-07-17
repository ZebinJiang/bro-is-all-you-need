"""Pi0.5 严格图像、token、mask 与 quantile 处理器。

设计参考: OpenPI@15a9616a00943ada6c20a0f158e3adb39df2ccac,Apache-2.0。
仅保留公开数据契约;tokenizer、统计资产和 checkpoint 必须另行收据。
"""

# ruff: noqa: RUF002

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TypeAlias

import numpy as np
import torch
from numpy.typing import NDArray
from torch.nn import functional as F

from autovla.core.types.training import TrainingBatch
from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.interfaces.processor import ModelProcessor
from autovla.models.outputs import ActionPrediction, ModelInputBatch

_FloatArray: TypeAlias = NDArray[np.float32]
_BoolArray: TypeAlias = NDArray[np.bool_]


class _Tokenizer(Protocol):
    """描述 Pi0.5 本地 tokenizer 的最小调用面。"""

    def encode(self, text: str, *, add_special_tokens: bool) -> Sequence[int]:
        """把文本编码为 token ID 序列。"""


class Pi05Processor(ModelProcessor):
    """投影 canonical ``TrainingBatch`` 并保留严格 mask/可逆 quantile。"""

    camera_order = ("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb")

    def __init__(
        self,
        config: Pi05Config,
        q01: object,
        q99: object,
        *,
        tokenizer: _Tokenizer | None = None,
    ) -> None:
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
        self.tokenizer = tokenizer

    def prepare_batch(
        self,
        batch: TrainingBatch,
        *,
        device: torch.device,
        dtype: torch.dtype | None,
        training: bool,
    ) -> ModelInputBatch:
        """把三相机、语言、离散状态和动作投影到唯一 Pi0.5 输入。"""

        if self.tokenizer is None:
            raise RuntimeError("Pi0.5 production processor requires a verified local tokenizer")
        if tuple(batch.images) != self.camera_order:
            raise ValueError("TrainingBatch cameras must use the exact Pi0.5 order")
        if batch.state is None:
            raise ValueError("Pi0.5 requires normalized state")
        state_array = np.asarray(batch.state)
        if state_array.ndim == 3:
            state_array = state_array[:, -1]
        if state_array.shape != (batch.batch_size, self.config.state_dimension):
            raise ValueError("Pi0.5 state must resolve to [B,32]")
        state = np.asarray(state_array, dtype=np.float32)
        state_mask_value = batch.metadata.get("state_mask")
        state_mask = (
            np.ones_like(state, dtype=np.bool_)
            if state_mask_value is None
            else np.asarray(state_mask_value)
        )
        if state_mask.dtype != np.bool_ or state_mask.shape != state.shape:
            raise TypeError("Pi0.5 state_mask must use strict bool[B,32]")
        quantized_state = self.quantize_state(state, state_mask)
        input_ids, token_mask, routing_mask, loss_mask = self._tokenize(
            batch.language, quantized_state, state_mask
        )
        image_masks = self._image_masks(batch)
        images = {
            name: self._prepare_image(
                np.asarray(batch.images[name]),
                device=device,
                dtype=dtype or torch.float32,
                training=training,
            )
            for name in self.camera_order
        }
        if batch.action_horizon > self.config.action_horizon:
            raise ValueError("batch action horizon exceeds Pi0.5 configuration")
        if batch.action_dim > self.config.action_dimension:
            raise ValueError("batch action dimension exceeds Pi0.5 configuration")
        actions = np.zeros(
            (batch.batch_size, self.config.action_horizon, self.config.action_dimension),
            dtype=np.float32,
        )
        action_mask = np.zeros_like(actions, dtype=np.bool_)
        actions[:, : batch.action_horizon, : batch.action_dim] = np.asarray(
            batch.actions, dtype=np.float32
        )
        action_mask[:, : batch.action_horizon, : batch.action_dim] = batch.action_mask
        normalized_actions = self.normalize_actions(actions, action_mask)
        torch_actions = torch.as_tensor(
            np.array(normalized_actions, copy=True), device=device, dtype=dtype or torch.float32
        )
        torch_action_mask = torch.as_tensor(
            np.array(action_mask, copy=True), device=device, dtype=torch.bool
        )
        torch_state = torch.as_tensor(
            np.array(state[:, None, :], copy=True),
            device=device,
            dtype=dtype or torch.float32,
        )
        metadata = {
            "image_masks": torch.as_tensor(image_masks, device=device, dtype=torch.bool),
            "prompt_routing_mask": torch.as_tensor(routing_mask, device=device, dtype=torch.bool),
            "prompt_loss_mask": torch.as_tensor(loss_mask, device=device, dtype=torch.bool),
            "state_token_mask": torch.as_tensor(
                np.concatenate(
                    (
                        np.zeros(
                            (batch.batch_size, input_ids.shape[1] - state.shape[1]), dtype=np.bool_
                        ),
                        state_mask,
                    ),
                    axis=1,
                ),
                device=device,
                dtype=torch.bool,
            ),
            "training_augmentation": {
                "name": "random_resize_then_pad",
                "scale": self.config.training_resize_scale,
                "enabled": training,
            },
        }
        for hook in ("fixed_noise", "fixed_time"):
            if hook in batch.metadata:
                metadata[hook] = torch.as_tensor(
                    np.array(batch.metadata[hook], copy=True),
                    device=device,
                    dtype=dtype or torch.float32,
                )
        return ModelInputBatch(
            images=images,
            input_ids=torch.as_tensor(input_ids, device=device, dtype=torch.long),
            attention_mask=torch.as_tensor(token_mask, device=device, dtype=torch.bool),
            state=torch_state,
            embodiment_ids=torch.zeros(batch.batch_size, device=device, dtype=torch.long),
            actions=torch_actions,
            action_mask=torch_action_mask,
            raw_state=torch_state.clone(),
            physical_action_shapes=tuple(
                (batch.action_horizon, batch.action_dim) for _ in range(batch.batch_size)
            ),
            embodiments=tuple(batch.embodiment or ("pi0_5",) * batch.batch_size),
            camera_order=self.camera_order,
            sample_source=batch.sample_source,
            metadata=metadata,
        )

    def decode_actions(
        self,
        actions: torch.Tensor,
        *,
        batch: ModelInputBatch,
    ) -> ActionPrediction:
        """反 quantile 并按原物理 ``[H,D]`` 范围屏蔽 padding。"""

        if actions.shape != (
            batch.batch_size,
            self.config.action_horizon,
            self.config.action_dimension,
        ):
            raise ValueError("Pi0.5 decoded action tensor must use [B,H,32]")
        mask = (
            batch.action_mask.clone()
            if batch.action_mask is not None
            else torch.ones_like(actions, dtype=torch.bool)
        )
        lower = torch.as_tensor(self._q01, device=actions.device, dtype=actions.dtype)
        upper = torch.as_tensor(self._q99, device=actions.device, dtype=actions.dtype)
        decoded = (actions + 1.0) * 0.5 * (upper - lower + 1e-6) + lower
        decoded = torch.where(mask, decoded, torch.zeros_like(decoded))
        return ActionPrediction(actions, mask, decoded)

    def _tokenize(
        self,
        language: tuple[str, ...],
        quantized_state: NDArray[np.int64],
        state_mask: _BoolArray,
    ) -> tuple[NDArray[np.int64], _BoolArray, _BoolArray, _BoolArray]:
        """把 prompt 和 32 个离散状态 token 串联后右侧 padding 到批内最大长度。"""

        assert self.tokenizer is not None
        state_width = self.config.state_dimension
        prompt_budget = self.config.max_prompt_state_tokens - state_width
        sequences: list[list[int]] = []
        routing: list[list[bool]] = []
        valid_tokens: list[list[bool]] = []
        for text, bins, valid in zip(language, quantized_state, state_mask, strict=True):
            prompt = [int(item) for item in self.tokenizer.encode(text, add_special_tokens=True)]
            if any(item < 0 or item >= self.config.vocab_size for item in prompt):
                raise ValueError("tokenizer emitted IDs outside Pi0.5 vocabulary")
            prompt = prompt[:prompt_budget]
            state_tokens = [
                self.config.state_token_offset + int(value) if is_valid else 0
                for value, is_valid in zip(bins, valid, strict=True)
            ]
            sequences.append(prompt + state_tokens)
            routing.append([False] * len(prompt) + [bool(item) for item in valid])
            valid_tokens.append([True] * len(prompt) + [bool(item) for item in valid])
        length = max(len(item) for item in sequences)
        ids = np.zeros((len(sequences), length), dtype=np.int64)
        mask = np.zeros_like(ids, dtype=np.bool_)
        route = np.zeros_like(ids, dtype=np.bool_)
        for index, (sequence, route_values, valid_values) in enumerate(
            zip(sequences, routing, valid_tokens, strict=True)
        ):
            ids[index, : len(sequence)] = sequence
            mask[index, : len(sequence)] = valid_values
            route[index, : len(sequence)] = route_values
        loss_mask = np.zeros_like(mask, dtype=np.bool_)
        return ids, mask, route, loss_mask

    def _image_masks(self, batch: TrainingBatch) -> _BoolArray:
        """从 canonical metadata 读取三相机逐样本有效 mask。"""

        value = batch.metadata.get("image_masks")
        if not isinstance(value, Mapping) or tuple(value) != self.camera_order:
            raise ValueError("Pi0.5 metadata image_masks must use the ordered camera mapping")
        masks = []
        for name in self.camera_order:
            mask = np.asarray(value[name])
            if mask.dtype != np.bool_ or mask.shape != (batch.batch_size,):
                raise TypeError("each Pi0.5 image mask must use strict bool[B]")
            masks.append(mask)
        return np.stack(masks, axis=1)

    def _prepare_image(
        self,
        value: NDArray[np.generic],
        *,
        device: torch.device,
        dtype: torch.dtype,
        training: bool,
    ) -> torch.Tensor:
        """把 BCHW/BHWC 图像按宽高比 resize/pad 到 224，并映射到 ``[-1,1]``。"""

        tensor = torch.as_tensor(np.array(value, copy=True), device=device)
        if tensor.ndim != 4:
            raise ValueError("Pi0.5 images must have rank 4")
        if tensor.shape[1] == 3:
            pass
        elif tensor.shape[-1] == 3:
            tensor = tensor.permute(0, 3, 1, 2).contiguous()
        else:
            raise ValueError("Pi0.5 images must contain exactly three channels")
        tensor = tensor.float()
        if float(tensor.max()) > 1.0:
            tensor = tensor / 255.0
        height, width = tensor.shape[-2:]
        scale = self.config.image_size / max(height, width)
        if training:
            jitter = torch.empty((), device=device).uniform_(
                self.config.training_resize_scale[0],
                self.config.training_resize_scale[1],
            )
            scale *= float(jitter)
        resized_height = max(1, min(self.config.image_size, round(height * scale)))
        resized_width = max(1, min(self.config.image_size, round(width * scale)))
        tensor = F.interpolate(
            tensor,
            size=(resized_height, resized_width),
            mode="bilinear",
            align_corners=False,
            antialias=True,
        )
        pad_height = self.config.image_size - resized_height
        pad_width = self.config.image_size - resized_width
        tensor = F.pad(
            tensor,
            (
                pad_width // 2,
                pad_width - pad_width // 2,
                pad_height // 2,
                pad_height - pad_height // 2,
            ),
            value=0.5,
        )
        return (tensor * 2.0 - 1.0).to(dtype=dtype)

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
