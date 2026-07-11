"""通用流匹配训练和固定步长 Euler 积分契约。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import torch


@dataclass(frozen=True, slots=True)
class FlowMatchingSchedule:
    """描述 beta 时间分布和固定 Euler 离散化。"""

    beta_alpha: float = 1.5
    beta_beta: float = 1.0
    time_scale: float = 0.999
    timestep_buckets: int = 1000
    inference_steps: int = 4

    def __post_init__(self) -> None:
        """校验流匹配参数为有效正值。"""
        if self.beta_alpha <= 0 or self.beta_beta <= 0:
            raise ValueError("beta parameters must be positive")
        if not 0 < self.time_scale <= 1:
            raise ValueError("time_scale must be in (0, 1]")
        if self.timestep_buckets <= 0 or self.inference_steps <= 0:
            raise ValueError("timestep_buckets and inference_steps must be positive")


def sample_beta_time(
    batch_size: int,
    *,
    device: torch.device,
    dtype: torch.dtype,
    schedule: FlowMatchingSchedule,
) -> torch.Tensor:
    """采样 ``(1-Beta(alpha,beta))*scale`` 连续时间 ``[B]``。"""
    distribution = torch.distributions.Beta(schedule.beta_alpha, schedule.beta_beta)
    sample = distribution.sample((batch_size,)).to(device=device, dtype=dtype)
    return (1.0 - sample) * schedule.time_scale


def interpolate_flow(
    noise: torch.Tensor,
    target: torch.Tensor,
    time: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """执行线性插值并返回速度目标 ``target-noise``。"""
    if noise.shape != target.shape:
        raise ValueError("noise and target must share one shape")
    if time.shape != (target.shape[0],):
        raise ValueError("time must have shape [B]")
    expanded = time.reshape(target.shape[0], *((1,) * (target.ndim - 1)))
    trajectory = (1.0 - expanded) * noise + expanded * target
    return trajectory, target - noise


def masked_mean_squared_error(
    prediction: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    *,
    epsilon: float = 1e-6,
) -> tuple[torch.Tensor, torch.Tensor]:
    """按严格布尔有效元素数归约 MSE 并返回逐元素损失。"""
    if prediction.shape != target.shape or mask.shape != prediction.shape:
        raise ValueError("prediction, target, and mask must share one shape")
    if mask.dtype != torch.bool:
        raise TypeError("flow-matching mask must be strict torch.bool")
    squared = (prediction - target).square()
    elementwise = squared * mask.to(dtype=squared.dtype)
    denominator = mask.sum().to(dtype=squared.dtype) + epsilon
    return elementwise.sum() / denominator, elementwise


def euler_integrate(
    initial: torch.Tensor,
    velocity: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    *,
    schedule: FlowMatchingSchedule,
) -> torch.Tensor:
    """从 ``t=0`` 开始执行固定步数显式 Euler 积分。"""
    value = initial
    batch_size = initial.shape[0]
    dt = 1.0 / float(schedule.inference_steps)
    for step in range(schedule.inference_steps):
        continuous_time = step / float(schedule.inference_steps)
        discrete_time = int(continuous_time * schedule.timestep_buckets)
        timesteps = torch.full(
            (batch_size,),
            discrete_time,
            dtype=torch.long,
            device=initial.device,
        )
        predicted_velocity = velocity(value, timesteps)
        if predicted_velocity.shape != value.shape:
            raise ValueError("velocity function must preserve action shape")
        value = value + dt * predicted_velocity
    return value


__all__ = [
    "FlowMatchingSchedule",
    "euler_integrate",
    "interpolate_flow",
    "masked_mean_squared_error",
    "sample_beta_time",
]
