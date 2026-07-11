"""单设备生产训练策略。"""

from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import nn

from autovla.training.precision import PrecisionPolicy
from autovla.training.strategy.base import TrainingStrategy


class SingleDeviceStrategy(TrainingStrategy):
    """在显式 CPU 或 CUDA 设备上执行无分布式包装的训练。"""

    def __init__(self, precision: PrecisionPolicy, device: str | torch.device = "cpu") -> None:
        """记录目标设备但不触发设备运行时。"""

        super().__init__(precision)
        self._requested_device = torch.device(device)

    @property
    def rank(self) -> int:
        """单设备 rank 固定为零。"""

        return 0

    @property
    def world_size(self) -> int:
        """单设备 world size 固定为一。"""

        return 1

    def setup(self) -> None:
        """绑定目标设备并初始化精度策略。"""

        if self._requested_device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("single-device CUDA target requires an available CUDA device")
        self._device = (
            torch.device("cuda", 0)
            if self._requested_device.type == "cuda" and str(self._requested_device) == "cuda"
            else self._requested_device
        )
        if self.device.type == "cuda":
            torch.cuda.set_device(self.device.index)
        self.precision.setup(self.device)

    def prepare_model(self, model: nn.Module) -> nn.Module:
        """把模型移动到目标设备。"""

        return model.to(self.device)

    def clip_gradients(self, model: nn.Module, max_norm: float) -> float:
        """裁剪全部可训练参数的梯度。"""

        return float(torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm).item())

    def all_finite(self, finite: bool) -> bool:
        """单设备直接返回有限性判断。"""

        return finite

    def reduce_mean(self, value: float) -> float:
        """单设备直接返回输入标量。"""

        return value

    def broadcast_text(self, value: str) -> str:
        """单设备直接返回控制面文本。"""

        return value

    def collect_rank_runtime_state(
        self, local_state: Mapping[str, object]
    ) -> Mapping[str, Mapping[str, object]] | None:
        """校验并返回单 rank 运行时状态。"""

        return self._validate_rank_runtime_states((local_state,))

    def model_state_dict(self, model: nn.Module) -> Mapping[str, torch.Tensor]:
        """返回普通模型状态字典。"""

        return model.state_dict()

    def load_model_state_dict(self, model: nn.Module, state: Mapping[str, torch.Tensor]) -> None:
        """严格加载普通模型状态字典。"""

        model.load_state_dict(dict(state), strict=True)

    def barrier(self) -> None:
        """单设备无需同步。"""

        return None

    def close(self) -> None:
        """清除设备绑定。"""

        self._device = None


__all__ = ["SingleDeviceStrategy"]
