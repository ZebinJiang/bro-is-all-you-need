"""Pi0.5 的类型化架构、输入和调优配置。

设计参考: OpenPI 固定提交 15a9616a00943ada6c20a0f158e3adb39df2ccac,Apache-2.0。
本文件是契约级清洁实现;Gemma 和 checkpoint 权利不由源码许可覆盖。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Pi05Config:
    """关闭 Pi0.5 张量形状、token 上限、推理步数与默认冻结策略。"""

    family_key: str = "pi0_5"
    action_dimension: int = 32
    state_dimension: int = 32
    action_horizon: int = 50
    image_size: int = 224
    max_prompt_state_tokens: int = 200
    state_quantization_bins: int = 256
    num_inference_steps: int = 10
    prefix_hidden_size: int = 2048
    expert_hidden_size: int = 1024
    vision_hidden_size: int = 1152
    vision_intermediate_size: int = 4304
    vision_num_layers: int = 27
    vision_num_heads: int = 16
    vision_patch_size: int = 14
    prefix_intermediate_size: int = 16384
    prefix_num_layers: int = 18
    prefix_num_heads: int = 8
    prefix_num_key_value_heads: int = 1
    expert_intermediate_size: int = 4096
    expert_num_layers: int = 18
    expert_num_heads: int = 8
    expert_num_key_value_heads: int = 1
    vocab_size: int = 257152
    state_token_offset: int = 256896
    rms_norm_epsilon: float = 1e-6
    rope_theta: float = 10000.0
    beta_alpha: float = 1.5
    beta_beta: float = 1.0
    minimum_time: float = 0.001
    training_resize_scale: tuple[float, float] = (0.95, 1.0)
    gradient_checkpointing: bool = False
    tune_vision_encoder: bool = False
    tune_language_prefix: bool = False
    tune_action_expert: bool = True
    tune_input_output_projections: bool = True
    local_files_only: bool = True

    def __post_init__(self) -> None:
        """拒绝路径推断、远程资产和偏离固定源契约的关键参数。"""

        expected = (
            self.family_key,
            self.action_dimension,
            self.state_dimension,
            self.image_size,
            self.max_prompt_state_tokens,
            self.state_quantization_bins,
            self.num_inference_steps,
        )
        if expected != ("pi0_5", 32, 32, 224, 200, 256, 10):
            raise ValueError("Pi0.5 fixed contract must remain pi0_5/32/32/224/200/256/10")
        if type(self.action_horizon) is not int or not 1 <= self.action_horizon <= 50:
            raise ValueError("action_horizon must be an explicit dataset value in [1, 50]")
        positive_integers = (
            self.prefix_hidden_size,
            self.expert_hidden_size,
            self.vision_hidden_size,
            self.vision_intermediate_size,
            self.vision_num_layers,
            self.vision_num_heads,
            self.vision_patch_size,
            self.prefix_intermediate_size,
            self.prefix_num_layers,
            self.prefix_num_heads,
            self.prefix_num_key_value_heads,
            self.expert_intermediate_size,
            self.expert_num_layers,
            self.expert_num_heads,
            self.expert_num_key_value_heads,
            self.vocab_size,
        )
        if any(type(value) is not int or value <= 0 for value in positive_integers):
            raise ValueError("Pi0.5 architecture dimensions must be positive integers")
        if self.image_size % self.vision_patch_size:
            raise ValueError("image_size must be divisible by vision_patch_size")
        if self.vision_hidden_size % self.vision_num_heads:
            raise ValueError("vision hidden width must be divisible by its head count")
        for hidden, heads, kv_heads, label in (
            (
                self.prefix_hidden_size,
                self.prefix_num_heads,
                self.prefix_num_key_value_heads,
                "prefix",
            ),
            (
                self.expert_hidden_size,
                self.expert_num_heads,
                self.expert_num_key_value_heads,
                "expert",
            ),
        ):
            if hidden % heads or heads % kv_heads:
                raise ValueError(f"{label} attention width/head contract is invalid")
        if self.state_token_offset < 0 or (
            self.state_token_offset + self.state_quantization_bins > self.vocab_size
        ):
            raise ValueError("discrete state token range must fit inside vocabulary")
        if self.rms_norm_epsilon <= 0 or self.rope_theta <= 0:
            raise ValueError("normalization epsilon and RoPE theta must be positive")
        if self.beta_alpha <= 0 or self.beta_beta <= 0:
            raise ValueError("Beta distribution parameters must be positive")
        if not 0 < self.minimum_time < 1:
            raise ValueError("minimum_time must lie in (0,1)")
        if (
            type(self.training_resize_scale) is not tuple
            or len(self.training_resize_scale) != 2
            or not 0 < self.training_resize_scale[0] <= self.training_resize_scale[1] <= 1
        ):
            raise ValueError("training_resize_scale must be an ordered tuple in (0,1]")
        for name in (
            "tune_vision_encoder",
            "tune_language_prefix",
            "tune_action_expert",
            "tune_input_output_projections",
            "local_files_only",
            "gradient_checkpointing",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be an exact bool")
        if not self.local_files_only:
            raise ValueError("Pi0.5 runtime must remain local_files_only")

    @property
    def fingerprint(self) -> str:
        """返回不会包含路径或资产字节的稳定配置身份。"""

        payload = {name: getattr(self, name) for name in self.__dataclass_fields__}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @property
    def trainable_components(self) -> tuple[str, ...]:
        """返回默认允许调优的组件,不执行参数遍历。"""

        values = []
        if self.tune_action_expert:
            values.append("action_expert")
        if self.tune_input_output_projections:
            values.append("input_output_projections")
        if self.tune_vision_encoder:
            values.append("vision_encoder")
        if self.tune_language_prefix:
            values.append("language_prefix")
        return tuple(values)

    @property
    def frozen_components(self) -> tuple[str, ...]:
        """返回默认冻结组件,不改变任何模型参数。"""

        all_components = (
            "vision_encoder",
            "language_prefix",
            "action_expert",
            "input_output_projections",
        )
        return tuple(item for item in all_components if item not in self.trainable_components)
