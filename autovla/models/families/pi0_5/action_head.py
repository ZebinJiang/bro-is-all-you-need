"""Pi0.5 AdaRMS 条件动作 expert 契约。

设计参考: OpenPI@15a9616a00943ada6c20a0f158e3adb39df2ccac,Apache-2.0。
公式为公开设计的清洁实现;未复制 Transformers patch,亦不修改全局实现。
"""

from __future__ import annotations

from importlib import import_module

from autovla.models.families.pi0_5.config import Pi05Config


class Pi05ActionExpert:
    """组合动作投影、时间 MLP 与逐层 AdaRMS 门控调用。"""

    def __init__(
        self,
        config: Pi05Config,
        *,
        action_in_projection: object,
        action_out_projection: object,
        time_mlp: object,
        expert_layers: tuple[object, ...],
    ) -> None:
        """绑定调用方显式构造的 PyTorch 模块,不隐式加载资产。"""

        if not expert_layers:
            raise ValueError("Pi0.5 action expert requires at least one owned expert layer")
        self.config = config
        self.action_in_projection = action_in_projection
        self.action_out_projection = action_out_projection
        self.time_mlp = time_mlp
        self.expert_layers = expert_layers

    @staticmethod
    def adaptive_rms(
        hidden: object,
        scale: object,
        shift: object,
        gate: object,
        *,
        epsilon: float = 1e-6,
    ) -> tuple[object, object]:
        """以 float32 计算 RMS,返回条件化激活和独立残差门。"""

        torch = import_module("torch")
        if not all(bool(torch.is_tensor(item)) for item in (hidden, scale, shift, gate)):
            raise TypeError("AdaRMS inputs must be torch.Tensor values")
        hidden_shape = tuple(hidden.shape)
        for name, value in (("scale", scale), ("shift", shift), ("gate", gate)):
            if tuple(torch.broadcast_shapes(hidden_shape, tuple(value.shape))) != hidden_shape:
                raise ValueError(f"AdaRMS {name} must broadcast exactly to hidden shape")
        rms = hidden.float().pow(2).mean(dim=-1, keepdim=True).add(epsilon).rsqrt()
        normalized = (hidden.float() * rms).to(dtype=hidden.dtype)
        return normalized * (1 + scale) + shift, gate

    def embed_actions(self, noisy_actions: object, time: object) -> tuple[object, object]:
        """投影 ``[B,H,32]`` 噪声动作并生成每层 AdaRMS 条件。"""

        if tuple(noisy_actions.shape)[-2:] != (
            self.config.action_horizon,
            self.config.action_dimension,
        ):
            raise ValueError("noisy actions must match configured [H,32]")
        suffix = self.action_in_projection(noisy_actions)
        condition = self.time_mlp(time)
        return suffix, condition

    def project_velocity(self, hidden: object) -> object:
        """把 expert 隐状态投影回规范动作速度 ``[B,H,32]``。"""

        output = self.action_out_projection(hidden)
        if tuple(output.shape)[-2:] != (
            self.config.action_horizon,
            self.config.action_dimension,
        ):
            raise ValueError("action expert output must match configured [H,32]")
        return output
