"""GR00T N1.7 纯合成、确定性的后续运行机械 fixture。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from autovla.core.types.training import TrainingBatch
from autovla.models.components.flow_matching import FlowMatchingSchedule
from autovla.models.outputs import BackboneOutput, ModelInputBatch

_SYNTHETIC_FINGERPRINT = "synthetic-gr00t-n1d7-contract-fixture-v1"


@dataclass(frozen=True, slots=True)
class Gr00tN1d7ContractFixture:
    """保存 processor 与模型机械检查共享的确定性纯合成输入。

    该对象不代表真实数据、官方 checkpoint、数值 oracle 或可执行 runtime。
    ``training_batch`` 保留 12 维物理输入, ``model_batch`` 显式 pad 到
    ``[B,40,132]``, 供后续 loss/backward/prediction/DDP/ZeRO 机械验证复用。
    """

    training_batch: TrainingBatch
    model_batch: ModelInputBatch
    backbone_output: BackboneOutput
    fixed_noise: torch.Tensor
    fixed_flow_time: torch.Tensor
    synthetic_only: bool = True

    def noise_hook(self, actions: torch.Tensor) -> torch.Tensor:
        """按调用方 device/dtype 返回固定形状噪声。"""

        if actions.shape != self.fixed_noise.shape:
            raise ValueError(
                "synthetic N1.7 noise hook requires the fixture action shape"
            )
        return self.fixed_noise.to(device=actions.device, dtype=actions.dtype)

    def time_hook(
        self,
        batch_size: int,
        device: torch.device,
        dtype: torch.dtype,
        schedule: FlowMatchingSchedule,
    ) -> torch.Tensor:
        """返回固定 flow time, 并验证官方 timestep schedule 身份。"""

        if batch_size != self.fixed_flow_time.shape[0]:
            raise ValueError("synthetic N1.7 time hook requires the fixture batch size")
        if schedule.timestep_buckets != 1000 or schedule.inference_steps != 4:
            raise ValueError(
                "synthetic N1.7 fixture requires the official flow schedule"
            )
        return self.fixed_flow_time.to(device=device, dtype=dtype)


def build_synthetic_contract_fixture(
    *,
    batch_size: int = 2,
    physical_width: int = 12,
) -> Gr00tN1d7ContractFixture:
    """构造可重复的 N1D7 processor 与训练机械契约, 不读取任何资产。

    Args:
        batch_size: 合成 batch 大小, 必须为正整数。
        physical_width: pad 前物理 state/action 宽度, 范围为 ``[1,132]``。

    Returns:
        包含物理 ``TrainingBatch``、132 维模型 batch、骨干输出和固定 hook。
    """

    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    if type(physical_width) is not int or not 1 <= physical_width <= 132:
        raise ValueError("physical_width must be in [1,132]")

    image = np.arange(batch_size * 8 * 8 * 3, dtype=np.float32).reshape(
        batch_size,
        8,
        8,
        3,
    )
    physical_state = np.linspace(
        -0.5,
        0.5,
        num=batch_size * physical_width,
        dtype=np.float32,
    ).reshape(batch_size, 1, physical_width)
    physical_actions = np.linspace(
        -0.75,
        0.75,
        num=batch_size * 40 * physical_width,
        dtype=np.float32,
    ).reshape(batch_size, 40, physical_width)
    physical_mask = np.ones_like(physical_actions, dtype=np.bool_)
    languages = tuple(f"synthetic task {index}" for index in range(batch_size))
    embodiments = ("new_embodiment",) * batch_size
    sources = tuple(
        {"fixture": _SYNTHETIC_FINGERPRINT, "sample_index": index}
        for index in range(batch_size)
    )
    training_batch = TrainingBatch(
        images={"camera.rgb_0": image},
        language=languages,
        actions=physical_actions,
        action_mask=physical_mask,
        sample_source=sources,
        dataset_fingerprint=_SYNTHETIC_FINGERPRINT,
        transform_fingerprint=_SYNTHETIC_FINGERPRINT,
        statistics_fingerprint=_SYNTHETIC_FINGERPRINT,
        state=physical_state,
        embodiment=embodiments,
    )

    state = torch.zeros((batch_size, 1, 132), dtype=torch.float32)
    state[:, :, :physical_width] = torch.from_numpy(physical_state)
    actions = torch.zeros((batch_size, 40, 132), dtype=torch.float32)
    actions[:, :, :physical_width] = torch.from_numpy(physical_actions)
    action_mask = torch.zeros_like(actions, dtype=torch.bool)
    action_mask[:, :, :physical_width] = True
    input_ids = torch.arange(batch_size * 6, dtype=torch.long).reshape(batch_size, 6)
    attention_mask = torch.ones_like(input_ids, dtype=torch.bool)
    pixel_values = torch.from_numpy(image).permute(0, 3, 1, 2).contiguous()
    image_grid_thw = torch.tensor([(1, 8, 8)] * batch_size, dtype=torch.long)
    model_batch = ModelInputBatch(
        images={"camera.rgb_0": pixel_values},
        input_ids=input_ids,
        attention_mask=attention_mask,
        state=state,
        embodiment_ids=torch.full((batch_size,), 10, dtype=torch.long),
        actions=actions,
        action_mask=action_mask,
        raw_state=torch.from_numpy(physical_state),
        physical_action_shapes=((40, physical_width),) * batch_size,
        embodiments=embodiments,
        camera_order=("camera.rgb_0",),
        sample_source=sources,
        metadata={
            "pixel_values": pixel_values,
            "image_grid_thw": image_grid_thw,
            "synthetic_only": True,
        },
    )
    features = torch.linspace(
        -0.25,
        0.25,
        steps=batch_size * 6 * 2048,
        dtype=torch.float32,
    ).reshape(batch_size, 6, 2048)
    token_mask = torch.ones((batch_size, 6), dtype=torch.bool)
    image_mask = torch.zeros_like(token_mask)
    image_mask[:, :2] = True
    backbone_output = BackboneOutput(features, token_mask, image_mask)
    fixed_noise = torch.linspace(
        -1.0,
        1.0,
        steps=batch_size * 40 * 132,
        dtype=torch.float32,
    ).reshape(batch_size, 40, 132)
    fixed_flow_time = torch.linspace(0.2, 0.8, steps=batch_size, dtype=torch.float32)
    return Gr00tN1d7ContractFixture(
        training_batch,
        model_batch,
        backbone_output,
        fixed_noise,
        fixed_flow_time,
    )


__all__ = ["Gr00tN1d7ContractFixture", "build_synthetic_contract_fixture"]
