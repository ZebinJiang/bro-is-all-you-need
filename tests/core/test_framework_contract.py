"""GenesisVLA 框架输入输出契约测试。"""

from __future__ import annotations

from typing import Any

import numpy as np

from genesisvla.core.types import (
    ActionChunk,
    BatchSample,
    FrameworkOutput,
    LossValue,
    ModelInput,
    RawSample,
)


def _raw_sample(**overrides: Any) -> RawSample:
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.zeros((2, 7), dtype=np.float32),
        "state": np.zeros((7,), dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"episode_id": "ep-framework"},
    }
    payload.update(overrides)
    return RawSample(**payload)


def _batch_sample() -> BatchSample:
    return BatchSample(samples=(_raw_sample(),), metadata={"batch_id": "batch-001"})


def _action_chunk() -> ActionChunk:
    return ActionChunk(
        values=np.ones((2, 7), dtype=np.float32),
        mask=None,
        horizon=2,
        action_dim=7,
        normalized=True,
    )


def test_should_create_model_input_from_batch_sample() -> None:
    """验证 ModelInput 可直接承载 BatchSample。"""
    batch = _batch_sample()

    model_input = ModelInput(batch=batch)

    assert model_input.batch is batch
    assert model_input.batch.batch_size == 1


def test_should_default_model_input_tensors_and_metadata_to_empty_mappings() -> None:
    """验证 ModelInput 的张量与元数据默认值为空映射。"""
    model_input = ModelInput(batch=_batch_sample())

    assert model_input.tensors == {}
    assert model_input.metadata == {}


def test_should_preserve_model_input_tensors_and_metadata() -> None:
    """验证 ModelInput 会透传命名张量和输入级元数据。"""
    tensors = {"state": np.ones((1, 7), dtype=np.float32)}
    metadata: dict[str, Any] = {"view": "front", "batch_id": "batch-001"}

    model_input = ModelInput(batch=_batch_sample(), tensors=tensors, metadata=metadata)

    assert model_input.tensors["state"] is tensors["state"]
    assert model_input.metadata is metadata


def test_should_create_framework_output_with_loss_metrics_and_action_prediction() -> None:
    """验证 FrameworkOutput 可同时承载损失、指标和动作预测。"""
    action = _action_chunk()
    losses: dict[str, LossValue] = {"main": 0.5}
    metrics = {"accuracy": 1.0}

    output = FrameworkOutput(loss=0.5, losses=losses, metrics=metrics, action_pred=action)

    assert output.loss == 0.5
    assert output.losses is losses
    assert output.metrics is metrics
    assert output.action_pred is action


def test_should_allow_framework_output_without_action_prediction() -> None:
    """验证 FrameworkOutput 允许没有动作预测的训练输出。"""
    output = FrameworkOutput(loss=None, losses={}, metrics={"loss_ready": 0.0})

    assert output.action_pred is None
    assert output.metrics["loss_ready"] == 0.0


def test_should_preserve_named_losses_and_metrics() -> None:
    """验证命名损失和指标不会被重写。"""
    aux_loss = np.asarray([0.25], dtype=np.float32)
    losses: dict[str, LossValue] = {"main": 1.0, "aux": aux_loss}
    metrics = {"success_rate": 0.75, "latency_ms": 3.0}

    output = FrameworkOutput(loss=aux_loss, losses=losses, metrics=metrics)

    assert output.loss is aux_loss
    assert output.losses["aux"] is aux_loss
    assert output.metrics["success_rate"] == 0.75
