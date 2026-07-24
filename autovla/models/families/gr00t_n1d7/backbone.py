"""Cosmos Reason2 / Qwen3-VL 本地骨干。"""

from __future__ import annotations

from typing import Protocol, cast

import torch
from torch import nn

from autovla.models._torch_typing import initialize_torch_module
from autovla.models.assembly import ModelAssemblyRequest
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config
from autovla.models.interfaces.backbone import VisionLanguageBackbone
from autovla.models.outputs import BackboneOutput, ModelInputBatch


class _Qwen3VLOutput(Protocol):
    """描述 Transformers Qwen3-VL 返回值的最小边界。"""

    hidden_states: tuple[torch.Tensor, ...] | None
    last_hidden_state: torch.Tensor


class CosmosReason2VisionLanguageBackbone(VisionLanguageBackbone):
    """包装本地 Qwen3-VL 参数图并输出 ``[B,S,2048]`` 特征。

    ``pixel_values`` 与 ``image_grid_thw`` 由同一个家族 processor 生成并
    通过 ``ModelInputBatch.metadata`` 传递, 保持可变相机、历史和分辨率。
    """

    implementation = "qwen3_vl_cosmos_reason2"
    attention_backend_preference = ("flash_attention_2", "sdpa")
    dynamic_image_grid = True
    local_files_only = True
    trust_remote_code = False
    rotary_buffer_validation_required = True

    def __init__(self, config: Gr00tN1d7Config, model: nn.Module) -> None:
        """保存已在规范初始化上下文中构造的本地 Qwen3-VL。"""

        initialize_torch_module(super())
        if not isinstance(cast(object, config), Gr00tN1d7Config) or not isinstance(
            cast(object, model), nn.Module
        ):
            raise TypeError("backbone requires Gr00tN1d7Config and a torch module")
        self.config = config
        self.model = model
        self._apply_tune_policy()

    @classmethod
    def from_request(
        cls,
        request: ModelAssemblyRequest,
        model: nn.Module,
    ) -> "CosmosReason2VisionLanguageBackbone":
        """从同一共享请求与已构造 Qwen3-VL 生成骨干。"""

        if request.family_key != "gr00t_n1d7" or not isinstance(request.config, Gr00tN1d7Config):
            raise TypeError("request must carry a GR00T N1.7 config")
        return cls(request.config, model)

    def _apply_tune_policy(self) -> None:
        """先冻结全部, 再按 artifact 优先策略解冻视觉/语言参数。"""

        self.requires_grad_(False)
        language = getattr(self.model, "language_model", None)
        visual = getattr(self.model, "visual", getattr(self.model, "vision_model", None))
        if language is not None and isinstance(language, nn.Module):
            if self.config.tune_language:
                language.requires_grad_(True)
        if visual is not None and isinstance(visual, nn.Module):
            if self.config.tune_visual:
                visual.requires_grad_(True)
        if self.config.tune_top_language_layers:
            layers = _language_layers(language)
            count = self.config.tune_top_language_layers
            if count > len(layers):
                raise ValueError("tune_top_language_layers exceeds retained Qwen3-VL layers")
            for layer in layers[-count:]:
                layer.requires_grad_(True)

    def train(self, mode: bool = True) -> "CosmosReason2VisionLanguageBackbone":
        """切换模式并让未调优的重型分支保持 eval。"""

        super().train(mode)
        if mode:
            language = getattr(self.model, "language_model", None)
            visual = getattr(self.model, "visual", getattr(self.model, "vision_model", None))
            if (
                language is not None
                and isinstance(language, nn.Module)
                and not self.config.tune_language
            ):
                language.eval()
            if visual is not None and isinstance(visual, nn.Module) and not self.config.tune_visual:
                visual.eval()
        return self

    @property
    def tune_freeze_defaults(self) -> dict[str, object]:
        """返回 artifact 优先的参数调优策略。"""

        return {
            "language_trainable": self.config.tune_language,
            "visual_trainable": self.config.tune_visual,
            "top_language_layers": self.config.tune_top_language_layers,
            "remaining_language_frozen": not self.config.tune_language,
            "rotary_buffers_trainable": False,
        }

    def forward(self, batch: ModelInputBatch) -> BackboneOutput:
        """执行 Qwen3-VL flexible-resolution 前向并保留严格 token mask。"""

        pixel_values = batch.metadata.get("pixel_values")
        image_grid_thw = batch.metadata.get("image_grid_thw")
        if not isinstance(pixel_values, torch.Tensor) or not isinstance(
            image_grid_thw, torch.Tensor
        ):
            raise ValueError("processor must provide pixel_values and image_grid_thw tensors")
        raw_output = self.model(
            input_ids=batch.input_ids,
            attention_mask=batch.attention_mask,
            pixel_values=pixel_values,
            image_grid_thw=image_grid_thw,
            output_hidden_states=True,
            return_dict=True,
        )
        output = cast(_Qwen3VLOutput, raw_output)
        hidden_states = output.hidden_states
        features = hidden_states[-1] if hidden_states else output.last_hidden_state
        if features.shape[-1] != self.config.backbone_hidden_size:
            raise ValueError("Qwen3-VL hidden width must equal 2048")
        attention_mask = batch.attention_mask.bool()
        image_token_id = getattr(getattr(self.model, "config", None), "image_token_id", None)
        image_mask = (
            batch.input_ids.eq(image_token_id)
            if type(image_token_id) is int
            else torch.zeros_like(attention_mask)
        )
        return BackboneOutput(features, attention_mask, image_mask, tuple(hidden_states or ()))


def _language_layers(module: object) -> tuple[nn.Module, ...]:
    """兼容常见 Qwen3-VL 容器并返回语言层。"""

    if not isinstance(module, nn.Module):
        return ()
    candidate = getattr(module, "layers", None)
    if isinstance(candidate, (nn.ModuleList, list, tuple)):
        return tuple(item for item in candidate or () if isinstance(item, nn.Module))
    nested = getattr(module, "model", None)
    candidate = getattr(nested, "layers", None)
    if isinstance(candidate, (nn.ModuleList, list, tuple)):
        return tuple(item for item in candidate or () if isinstance(item, nn.Module))
    return ()


def _build_backbone(request: ModelAssemblyRequest) -> CosmosReason2VisionLanguageBackbone:
    """沿唯一 N1.7 工厂与请求初始化上下文构造骨干。"""

    from autovla.models.families.gr00t_n1d7.factory import Gr00tN1d7ModelFactory

    return Gr00tN1d7ModelFactory().build_backbone(request)


__all__ = ["CosmosReason2VisionLanguageBackbone", "_build_backbone"]
