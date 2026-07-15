"""Pi0.5 联合前缀缓存与 flow-matching 模型协调器。

设计参考: OpenPI@15a9616a00943ada6c20a0f158e3adb39df2ccac,Apache-2.0。
不包含 Pi0、Pi0-FAST、隐式下载、全局补丁或任意 pickle 路径。
"""

from __future__ import annotations

from importlib import import_module

from autovla.models.families.pi0_5.action_head import Pi05ActionExpert
from autovla.models.families.pi0_5.backbone import Pi05VisionLanguageBackbone
from autovla.models.families.pi0_5.config import Pi05Config


class Pi05Model:
    """保留 prefix 构建一次、每个 Euler 步骤只读 cache 的执行边界。"""

    def __init__(
        self,
        config: Pi05Config,
        backbone: Pi05VisionLanguageBackbone,
        action_expert: Pi05ActionExpert,
    ) -> None:
        """组合 AutoVLA 自有组件,不在构造时执行前向或加载 checkpoint。"""

        if backbone.config != config or action_expert.config != config:
            raise ValueError("Pi0.5 components must share one exact config")
        self.config = config
        self.backbone = backbone
        self.action_expert = action_expert

    @staticmethod
    def flow_training_sample(actions: object, noise: object, time: object) -> tuple[object, object]:
        """返回 ``x_t=t*noise+(1-t)*actions`` 与目标 ``noise-actions``。"""

        torch = import_module("torch")
        if not all(bool(torch.is_tensor(item)) for item in (actions, noise, time)):
            raise TypeError("flow matching inputs must be torch.Tensor values")
        if tuple(actions.shape) != tuple(noise.shape) or actions.ndim != 3:
            raise ValueError("actions and noise must share [B,H,D]")
        if tuple(time.shape) not in {(actions.shape[0],), (actions.shape[0], 1, 1)}:
            raise ValueError("time must use [B] or [B,1,1]")
        expanded = time.reshape(actions.shape[0], 1, 1)
        return expanded * noise + (1 - expanded) * actions, noise - actions

    def euler_denoise(self, noise: object, prefix_cache: object, velocity_fn: object) -> object:
        """以固定 10 步显式 Euler 读取同一 cache;回调不得返回新 cache。"""

        torch = import_module("torch")
        if not bool(torch.is_tensor(noise)):
            raise TypeError("Euler noise must be a torch.Tensor")
        if tuple(noise.shape)[-2:] != (
            self.config.action_horizon,
            self.config.action_dimension,
        ):
            raise ValueError("Euler noise must match configured [H,32]")
        if not callable(velocity_fn):
            raise TypeError("velocity_fn must be callable")
        value = noise
        step = -1.0 / self.config.num_inference_steps
        for index in range(self.config.num_inference_steps):
            time = 1.0 + index * step
            velocity = velocity_fn(value, time, prefix_cache)
            if isinstance(velocity, tuple):
                raise TypeError("velocity_fn must not return or replace prefix cache")
            if tuple(velocity.shape) != tuple(value.shape):
                raise ValueError("velocity must preserve action shape")
            value = value + step * velocity
        return value
