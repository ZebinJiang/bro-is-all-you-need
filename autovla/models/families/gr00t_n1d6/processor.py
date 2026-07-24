"""GR00T N1.6.1 family processor,通用数值逻辑委托给 R3 计划。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Protocol, cast

import numpy as np
import torch
from numpy.typing import NDArray
from torch.nn import functional as F

from autovla.core.semantics import MaskKind, MaskSemantics, TensorLayout
from autovla.core.types.training import TrainingBatch
from autovla.data.transforms import SemanticMask, TransformPlan
from autovla.models.families.gr00t_n1d6._nvidia.eagle.processing import LocalEagleProcessor
from autovla.models.families.gr00t_n1d6.config import EmbodimentStatistics, Gr00tN1d6Config
from autovla.models.interfaces.processor import ModelProcessor
from autovla.models.outputs import ActionPrediction, ModelInputBatch


class _Interpolate(Protocol):
    """描述本处理器使用的 Torch 插值调用。"""

    def __call__(
        self,
        tensor: torch.Tensor,
        *,
        size: tuple[int, int],
        mode: str,
        align_corners: bool,
        antialias: bool,
    ) -> torch.Tensor:
        """调整批图像空间尺寸。"""
        ...


def _module_member(module: object, name: str) -> object:
    """读取已导入第三方模块的受控成员。"""

    namespace = cast(Mapping[str, object], vars(module))
    try:
        return namespace[name]
    except KeyError as exc:
        raise RuntimeError(f"required module member is missing: {name}") from exc


class Gr00tN1d6Processor(ModelProcessor):
    """仅保留 family 图像/语言/embodiment/模型输入和逆解码职责。"""

    def __init__(
        self,
        config: Gr00tN1d6Config,
        eagle_processor: LocalEagleProcessor,
        *,
        visual_tokens_per_image: int,
    ) -> None:
        """保存配置和仅本地 Eagle processor。"""

        if type(visual_tokens_per_image) is not int or visual_tokens_per_image <= 0:
            raise ValueError("visual_tokens_per_image must be a positive integer")
        self.config = config
        self.eagle_processor = eagle_processor
        self.visual_tokens_per_image = visual_tokens_per_image

    def prepare_batch(
        self,
        batch: TrainingBatch,
        *,
        device: torch.device,
        dtype: torch.dtype | None,
        training: bool,
    ) -> ModelInputBatch:
        """把物理量 canonical batch 经 R3 计划变为严格模型输入。"""

        if batch.action_horizon > self.config.action_horizon:
            raise ValueError("batch action horizon exceeds configured horizon")
        if batch.action_dim > self.config.max_action_dim or batch.state is None:
            raise ValueError("GR00T action/state dimensions exceed the canonical contract")
        state = np.asarray(batch.state)
        if state.ndim == 2:
            state = state[:, None, :]
        if state.ndim != 3 or state.shape[-1] > self.config.max_state_dim:
            raise ValueError("state must have shape [B,T,D] within the configured dimension")
        embodiments = self._embodiments(batch)
        normalized_states: list[NDArray[np.float32]] = []
        normalized_actions: list[NDArray[np.float32]] = []
        action_masks: list[NDArray[np.bool_]] = []
        plans: list[TransformPlan] = []
        raw_last_states: list[NDArray[np.float32]] = []
        embodiment_ids: list[int] = []
        physical_shapes: list[tuple[int, int]] = []
        for index, embodiment in enumerate(embodiments):
            statistics = self._statistics(embodiment)
            state_value = np.array(state[index], dtype=np.float32, copy=True)
            action_value = np.array(batch.actions[index], dtype=np.float32, copy=True)
            reference = np.array(state_value[-1], dtype=np.float32, copy=True)
            state_value = self._encode_sin_cos_state(state_value, statistics)
            observed = np.zeros(
                (self.config.action_horizon, self.config.max_action_dim), dtype=np.bool_
            )
            observed[: batch.action_horizon, : batch.action_dim] = batch.action_mask[index]
            state_shape = (int(state_value.shape[0]), int(state_value.shape[1]))
            action_shape = (int(action_value.shape[0]), int(action_value.shape[1]))
            plan = self.config.transform_plan(
                embodiment,
                state_shape=state_shape,
                action_shape=action_shape,
            )
            transformed = plan.forward(
                {
                    "state": state_value,
                    "actions": action_value,
                    "reference_state": reference,
                    "action_observed_mask": SemanticMask(
                        observed,
                        MaskSemantics(
                            MaskKind.ACTION_DIMENSION,
                            # 与 PaddingStage 生成的 mask 共用基础轴布局,具体形状由 bool 值承载。
                            TensorLayout.time_feature(),
                        ),
                    ),
                }
            )
            state_output = np.asarray(transformed["state"], dtype=np.float32)
            action_output = np.asarray(transformed["actions"], dtype=np.float32)
            if statistics.state_clip:
                state_output = np.clip(state_output, -1.0, 1.0)
            clip_actions = (
                statistics.relative_action_clip
                if self.config.use_relative_actions and statistics.relative_action is not None
                else statistics.action_clip
            )
            if clip_actions:
                action_output = np.clip(action_output, -1.0, 1.0)
            semantic_mask = transformed["action_mask"]
            if not isinstance(semantic_mask, SemanticMask):
                raise TypeError("R3 transform plan must emit a semantic action mask")
            normalized_states.append(np.array(state_output, copy=True))
            normalized_actions.append(np.array(action_output, copy=True))
            action_masks.append(np.array(semantic_mask.values, copy=True))
            plans.append(plan)
            raw_last_states.append(reference)
            embodiment_ids.append(self.config.embodiment_ids[embodiment])
            physical_shapes.append(action_shape)
        camera_orders = tuple(self._camera_order(name) for name in embodiments)
        if len(set(camera_orders)) != 1:
            raise ValueError("one batch cannot mix embodiments with different camera schemas")
        camera_order = camera_orders[0]
        images = self._prepare_images(
            batch.images,
            camera_order=camera_order,
            device=device,
            training=training,
        )
        input_ids, attention_mask = self.eagle_processor.encode(
            tuple(self._formalize(text) for text in batch.language),
            image_count_per_sample=sum(image.shape[1] for image in images.values()),
            visual_tokens_per_image=self.visual_tokens_per_image,
            device=device,
        )
        tensor_dtype = dtype or torch.float32
        return ModelInputBatch(
            images=images,
            input_ids=input_ids,
            attention_mask=attention_mask,
            state=torch.as_tensor(np.stack(normalized_states), device=device, dtype=tensor_dtype),
            embodiment_ids=torch.as_tensor(embodiment_ids, device=device, dtype=torch.long),
            actions=torch.as_tensor(
                np.stack(normalized_actions), device=device, dtype=tensor_dtype
            ),
            action_mask=torch.as_tensor(np.stack(action_masks), device=device, dtype=torch.bool),
            raw_state=torch.as_tensor(np.stack(raw_last_states), device=device, dtype=tensor_dtype),
            transform_plans=tuple(plans),
            physical_action_shapes=tuple(physical_shapes),
            embodiments=embodiments,
            camera_order=camera_order,
            sample_source=batch.sample_source,
            metadata={
                "family": self.config.family_key,
                "statistics_fingerprint": tuple(
                    self._statistics(name).fingerprint for name in embodiments
                ),
                "transform_plan_fingerprint": tuple(plan.fingerprint for plan in plans),
                "normalization": "r3_axis_aware_per_embodiment",
            },
        )

    def decode_actions(self, actions: torch.Tensor, *, batch: ModelInputBatch) -> ActionPrediction:
        """按每个样本的同一 R3 计划逆序恢复物理动作。"""

        expected = (batch.batch_size, self.config.action_horizon, self.config.max_action_dim)
        if tuple(actions.shape) != expected:
            raise ValueError(f"actions must have shape {expected}")
        if not batch.transform_plans or batch.raw_state is None:
            raise ValueError("decode requires transform plans and raw reference states")
        decoded: list[torch.Tensor] = []
        for index, (plan, shape) in enumerate(
            zip(
                batch.transform_plans,
                batch.physical_action_shapes,
                strict=True,
            )
        ):
            transformed = plan.inverse(
                {
                    "actions": actions[index].detach().float().cpu().numpy(),
                    "state": batch.state[index].detach().float().cpu().numpy(),
                    "reference_state": batch.raw_state[index].detach().float().cpu().numpy(),
                }
            )
            physical = np.asarray(transformed["actions"], dtype=np.float32)
            if physical.shape != shape:
                raise RuntimeError("inverse TransformPlan changed the physical action shape")
            padded = torch.zeros_like(actions[index])
            padded[: shape[0], : shape[1]] = torch.as_tensor(
                physical, device=actions.device, dtype=actions.dtype
            )
            decoded.append(padded)
        decoded_tensor = torch.stack(decoded)
        mask = (
            batch.action_mask
            if batch.action_mask is not None
            else torch.ones_like(actions, dtype=torch.bool)
        )
        decoded_tensor = torch.where(mask, decoded_tensor, torch.zeros_like(decoded_tensor))
        return ActionPrediction(actions, mask, decoded_tensor)

    @staticmethod
    def _encode_sin_cos_state(
        state: NDArray[np.float32],
        statistics: EmbodimentStatistics,
    ) -> NDArray[np.float32]:
        """按官方模态切片把角度替换为连续的 sin/cos 特征。"""

        if not statistics.sin_cos_state_slices:
            return state
        parts: list[NDArray[np.float32]] = []
        cursor = 0
        for start, stop in statistics.sin_cos_state_slices:
            if start < cursor or stop > state.shape[-1]:
                raise ValueError("sin/cos state slice exceeds or overlaps the raw state")
            parts.append(state[..., cursor:start])
            values = state[..., start:stop]
            parts.extend((np.sin(values), np.cos(values)))
            cursor = stop
        parts.append(state[..., cursor:])
        return np.asarray(np.concatenate(parts, axis=-1), dtype=np.float32)

    def _camera_order(self, embodiment: str) -> tuple[str, ...]:
        """优先使用官方 per-embodiment 相机顺序。"""

        order = self._statistics(embodiment).camera_order
        return order or self.config.camera_order

    def _embodiments(self, batch: TrainingBatch) -> tuple[str, ...]:
        """解析并校验每个样本的 embodiment。"""

        if batch.embodiment is None:
            raise ValueError("GR00T N1.6.1 requires embodiment names")
        if any(name not in self.config.embodiment_ids for name in batch.embodiment):
            raise ValueError("unknown GR00T embodiment")
        return batch.embodiment

    def _statistics(self, embodiment: str) -> EmbodimentStatistics:
        """返回显式统计量,禁止 identity 回退。"""

        try:
            return self.config.statistics[embodiment]
        except KeyError as exc:
            raise ValueError(f"normalization statistics missing for {embodiment!r}") from exc

    def _prepare_images(
        self,
        images: Mapping[str, NDArray[np.generic]],
        *,
        camera_order: tuple[str, ...],
        device: torch.device,
        training: bool,
    ) -> Mapping[str, torch.Tensor]:
        """按配置顺序转换图像为 ``[B,T,C,H,W]``。"""

        if tuple(images) != camera_order:
            raise ValueError("input camera mapping must exactly match configured order")
        output: dict[str, torch.Tensor] = {}
        for name in camera_order:
            values = _to_btchw(
                torch.as_tensor(np.array(images[name], copy=True), device=device)
            ).float()
            if float(values.max()) > 1.0:
                values = values / 255.0
            flat = values.flatten(0, 1)
            if training:
                flat = _random_square_crop(flat, self.config.random_crop_scale)
            interpolate = cast(_Interpolate, _module_member(F, "interpolate"))
            flat = interpolate(
                flat,
                size=(self.config.image_size, self.config.image_size),
                mode="bilinear",
                align_corners=False,
                antialias=True,
            )
            if training and self.config.color_jitter is not None:
                flat = _color_jitter(flat, self.config.color_jitter)
            flat = (flat - 0.5) / 0.5
            output[name] = flat.reshape(
                values.shape[0], values.shape[1], 3, self.config.image_size, self.config.image_size
            )
        return output

    def _formalize(self, text: str) -> str:
        """按 N1.6.1 规则小写并移除标点。"""

        if not self.config.formalize_language:
            return text
        return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _to_btchw(values: torch.Tensor) -> torch.Tensor:
    """把常见 batch 图像布局规范化为 ``[B,T,C,H,W]``。"""

    if values.ndim == 4:
        values = values.unsqueeze(1)
    if values.ndim != 5:
        raise ValueError("camera images must have shape [B,C,H,W] or [B,T,C,H,W]")
    if values.shape[2] == 3:
        return values
    if values.shape[-1] == 3:
        return values.permute(0, 1, 4, 2, 3).contiguous()
    raise ValueError("camera images must contain exactly three channels")


def _random_square_crop(values: torch.Tensor, scale: tuple[float, float]) -> torch.Tensor:
    """对 batch 图像执行同尺寸随机方形裁剪。"""

    if not 0 < scale[0] <= scale[1] <= 1:
        raise ValueError("random_crop_scale must lie in (0,1]")
    height, width = values.shape[-2:]
    crop = max(
        1,
        int(
            min(height, width)
            * float(torch.empty((), device=values.device).uniform_(scale[0], scale[1]))
        ),
    )
    top = int(torch.randint(height - crop + 1, (), device=values.device)) if height > crop else 0
    left = int(torch.randint(width - crop + 1, (), device=values.device)) if width > crop else 0
    return values[..., top : top + crop, left : left + crop]


def _color_jitter(
    values: torch.Tensor, parameters: tuple[float, float, float, float]
) -> torch.Tensor:
    """执行 brightness/contrast/saturation;拒绝 hue 偏移。"""

    brightness, contrast, saturation, hue = parameters
    if hue != 0:
        raise ValueError("local GR00T processor requires hue jitter to remain zero")
    result = values
    if brightness > 0:
        result = result * (
            1.0 + float(torch.empty((), device=values.device).uniform_(-brightness, brightness))
        )
    if contrast > 0:
        mean = result.mean(dim=(-3, -2, -1), keepdim=True)
        factor = 1.0 + float(torch.empty((), device=values.device).uniform_(-contrast, contrast))
        result = (result - mean) * factor + mean
    if saturation > 0:
        gray = result.mean(dim=-3, keepdim=True)
        factor = 1.0 + float(
            torch.empty((), device=values.device).uniform_(-saturation, saturation)
        )
        result = (result - gray) * factor + gray
    return result.clamp(0.0, 1.0)


__all__ = ["Gr00tN1d6Processor"]
