"""GR00T N1.6.1 模型族处理器。"""

from __future__ import annotations

import re
from collections.abc import Mapping

import numpy as np
import torch
from numpy.typing import NDArray
from torch.nn import functional as F

from autovla.core.types.training import TrainingBatch
from autovla.models.components.relative_actions import RelativeActionPolicy
from autovla.models.families.gr00t_n1d6._nvidia.eagle.processing import LocalEagleProcessor
from autovla.models.families.gr00t_n1d6.config import (
    EmbodimentStatistics,
    FeatureStatistics,
    Gr00tN1d6Config,
)
from autovla.models.interfaces.processor import ModelProcessor
from autovla.models.outputs import ActionPrediction, ModelInputBatch


class Gr00tN1d6Processor(ModelProcessor):
    """执行相机、语言、归一化、相对动作、padding 和 embodiment 映射。"""

    def __init__(self, config: Gr00tN1d6Config, eagle_processor: LocalEagleProcessor) -> None:
        """保存不可变族配置和仅本地 Eagle processor。"""
        self.config = config
        self.eagle_processor = eagle_processor

    def prepare_batch(
        self,
        batch: TrainingBatch,
        *,
        device: torch.device,
        dtype: torch.dtype | None,
        training: bool,
    ) -> ModelInputBatch:
        """把 canonical batch 转为严格 N1.6.1 torch 输入。"""
        if batch.action_horizon > self.config.action_horizon:
            raise ValueError("batch action horizon exceeds pinned N1.6.1 horizon 16")
        if batch.action_dim > self.config.max_action_dim:
            raise ValueError("batch action dimension exceeds pinned maximum 29")
        if batch.state is None:
            raise ValueError("GR00T N1.6.1 requires state")
        embodiments = self._embodiments(batch)
        state = np.asarray(batch.state)
        if state.ndim == 2:
            state = state[:, None, :]
        if state.ndim != 3 or state.shape[-1] > self.config.max_state_dim:
            raise ValueError("state must have shape [B,T,D<=29]")
        raw_last_state = np.array(state[:, -1, :], dtype=np.float32, copy=True)
        normalized_state = np.zeros(
            (batch.batch_size, state.shape[1], self.config.max_state_dim),
            dtype=np.float32,
        )
        normalized_actions = np.zeros(
            (batch.batch_size, self.config.action_horizon, self.config.max_action_dim),
            dtype=np.float32,
        )
        strict_mask = np.zeros(normalized_actions.shape, dtype=np.bool_)
        offsets = np.zeros((batch.batch_size, self.config.max_action_dim), dtype=np.float32)
        scales = np.ones((batch.batch_size, self.config.max_action_dim), dtype=np.float32)
        relative_mask = np.zeros((batch.batch_size, self.config.max_action_dim), dtype=np.bool_)
        relative_policies: list[tuple[RelativeActionPolicy, ...]] = []
        embodiment_ids = np.empty((batch.batch_size,), dtype=np.int64)
        for index, embodiment in enumerate(embodiments):
            statistics = self._statistics(embodiment)
            state_dim = state.shape[-1]
            action_dim = batch.action_dim
            _require_statistics_dimension(statistics.state, state_dim, "state")
            _require_statistics_dimension(statistics.action, action_dim, "action")
            state_value = _normalize(state[index], statistics.state)
            normalized_state[index, :, :state_dim] = state_value
            action_value = np.array(batch.actions[index], dtype=np.float32, copy=True)
            if self.config.use_relative_actions:
                action_tensor = torch.from_numpy(action_value)
                reference_tensor = torch.from_numpy(raw_last_state[index])
                for policy in statistics.relative_action_policies:
                    action_tensor = policy.to_relative(action_tensor, reference_tensor)
                    relative_mask[index, policy.action_start : policy.action_stop] = True
                action_value = action_tensor.numpy()
                relative_policies.append(statistics.relative_action_policies)
            else:
                relative_policies.append(())
            action_value = _normalize(action_value, statistics.action)
            normalized_actions[index, : batch.action_horizon, :action_dim] = action_value
            strict_mask[index, : batch.action_horizon, :action_dim] = batch.action_mask[index]
            offsets[index, :action_dim] = statistics.action.offset
            scales[index, :action_dim] = statistics.action.scale
            embodiment_ids[index] = self.config.embodiment_ids[embodiment]
        images = self._prepare_images(batch.images, device=device, training=training)
        vision_tokens_per_view = (self.config.image_size // 14 // 2) ** 2
        texts = tuple(self._formalize(text) for text in batch.language)
        input_ids, attention_mask = self.eagle_processor.encode(
            texts,
            image_count_per_sample=sum(image.shape[1] for image in images.values()),
            visual_tokens_per_image=vision_tokens_per_view,
            device=device,
        )
        tensor_dtype = dtype or torch.float32
        return ModelInputBatch(
            images=images,
            input_ids=input_ids,
            attention_mask=attention_mask,
            state=torch.as_tensor(normalized_state, device=device, dtype=tensor_dtype),
            embodiment_ids=torch.as_tensor(embodiment_ids, device=device, dtype=torch.long),
            actions=torch.as_tensor(normalized_actions, device=device, dtype=tensor_dtype),
            action_mask=torch.as_tensor(strict_mask, device=device, dtype=torch.bool),
            raw_state=torch.as_tensor(raw_last_state, device=device, dtype=tensor_dtype),
            action_offset=torch.as_tensor(offsets, device=device, dtype=tensor_dtype),
            action_scale=torch.as_tensor(scales, device=device, dtype=tensor_dtype),
            relative_action_mask=torch.as_tensor(relative_mask, device=device, dtype=torch.bool),
            relative_action_policies=tuple(relative_policies),
            camera_order=self.config.camera_order,
            sample_source=batch.sample_source,
            metadata={
                "family": self.config.family_key,
                "statistics_fingerprint": batch.statistics_fingerprint,
                "normalization": "configured_per_embodiment",
            },
        )

    def decode_actions(
        self,
        actions: torch.Tensor,
        *,
        batch: ModelInputBatch,
    ) -> ActionPrediction:
        """反归一化并使用 raw last-state 重建相对动作。"""
        if actions.ndim != 3 or actions.shape[:2] != (
            batch.batch_size,
            self.config.action_horizon,
        ):
            raise ValueError("actions must have shape [B,16,D]")
        if actions.shape[-1] != self.config.max_action_dim:
            raise ValueError("actions final dimension must be 29")
        if batch.action_offset is None or batch.action_scale is None:
            raise ValueError("batch lacks action normalization parameters")
        decoded = actions * batch.action_scale.unsqueeze(1) + batch.action_offset.unsqueeze(1)
        if batch.relative_action_policies:
            if batch.raw_state is None:
                raise ValueError("relative action decode requires raw_state")
            reconstructed: list[torch.Tensor] = []
            for index, policies in enumerate(batch.relative_action_policies):
                sample = decoded[index : index + 1]
                reference = batch.raw_state[index : index + 1]
                for policy in policies:
                    sample = policy.to_absolute(sample, reference)
                reconstructed.append(sample)
            decoded = torch.cat(reconstructed, dim=0)
        if batch.action_mask is None:
            mask = torch.ones_like(actions, dtype=torch.bool)
        else:
            mask = batch.action_mask
        decoded = torch.where(mask, decoded, torch.zeros_like(decoded))
        return ActionPrediction(
            normalized_actions=actions,
            action_mask=mask,
            decoded_actions=decoded,
        )

    def _embodiments(self, batch: TrainingBatch) -> tuple[str, ...]:
        """解析并校验每个样本的 embodiment。"""
        if batch.embodiment is None:
            raise ValueError("GR00T N1.6.1 requires embodiment names")
        for name in batch.embodiment:
            if name not in self.config.embodiment_ids:
                raise ValueError(f"unknown GR00T embodiment: {name!r}")
        return batch.embodiment

    def _statistics(self, embodiment: str) -> EmbodimentStatistics:
        """返回该 embodiment 的显式统计量,禁止静默 identity 回退。"""
        try:
            return self.config.statistics[embodiment]
        except KeyError as exc:
            raise ValueError(f"normalization statistics missing for {embodiment!r}") from exc

    def _prepare_images(
        self,
        images: Mapping[str, NDArray[np.generic]],
        *,
        device: torch.device,
        training: bool,
    ) -> Mapping[str, torch.Tensor]:
        """按配置顺序转换图像为 ``[B,T,C,448,448]``。"""
        if tuple(images) != self.config.camera_order:
            raise ValueError("input camera mapping must exactly match configured order")
        output: dict[str, torch.Tensor] = {}
        for name in self.config.camera_order:
            values = torch.as_tensor(np.asarray(images[name]), device=device)
            values = _to_btchw(values)
            values = values.float()
            if float(values.max()) > 1.0:
                values = values / 255.0
            flat = values.flatten(0, 1)
            if training:
                flat = _random_square_crop(flat, self.config.random_crop_scale)
            flat = F.interpolate(
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
        normalized = re.sub(r"[^\w\s]", " ", text.lower())
        return " ".join(normalized.split())


def _require_statistics_dimension(
    statistics: FeatureStatistics,
    dimension: int,
    name: str,
) -> None:
    """要求统计维度与当前 modality 完全一致。"""
    if len(statistics.offset) != dimension:
        raise ValueError(f"{name} statistics dimension must be {dimension}")


def _normalize(
    values: NDArray[np.generic],
    statistics: FeatureStatistics,
) -> NDArray[np.generic]:
    """应用 ``(x-offset)/scale`` 并可选裁剪到 ``[-1,1]``。"""
    offset = np.asarray(statistics.offset, dtype=np.float32)
    scale = np.asarray(statistics.scale, dtype=np.float32)
    result = (np.asarray(values, dtype=np.float32) - offset) / scale
    return np.clip(result, -1.0, 1.0) if statistics.clip else result


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


def _random_square_crop(
    values: torch.Tensor,
    scale: tuple[float, float],
) -> torch.Tensor:
    """对 batch 图像执行同尺寸随机方形裁剪。"""
    if not 0 < scale[0] <= scale[1] <= 1:
        raise ValueError("random_crop_scale must lie in (0,1]")
    height, width = values.shape[-2:]
    side = min(height, width)
    ratio = float(torch.empty((), device=values.device).uniform_(scale[0], scale[1]))
    crop = max(1, int(side * ratio))
    top_limit = height - crop
    left_limit = width - crop
    top = int(torch.randint(top_limit + 1, (), device=values.device)) if top_limit else 0
    left = int(torch.randint(left_limit + 1, (), device=values.device)) if left_limit else 0
    return values[..., top : top + crop, left : left + crop]


def _color_jitter(
    values: torch.Tensor,
    parameters: tuple[float, float, float, float],
) -> torch.Tensor:
    """执行 brightness/contrast/saturation;拒绝未实现的 hue 偏移。"""
    brightness, contrast, saturation, hue = parameters
    if hue != 0:
        raise ValueError("local GR00T processor requires hue jitter to remain zero")
    result = values
    if brightness > 0:
        factor = 1.0 + float(
            torch.empty((), device=values.device).uniform_(-brightness, brightness)
        )
        result = result * factor
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
