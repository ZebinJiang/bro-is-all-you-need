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
        if self.prefix_hidden_size <= 0 or self.expert_hidden_size <= 0:
            raise ValueError("hidden dimensions must be positive")
        for name in (
            "tune_vision_encoder",
            "tune_language_prefix",
            "tune_action_expert",
            "tune_input_output_projections",
            "local_files_only",
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
