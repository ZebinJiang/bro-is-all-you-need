"""AutoVLA 协议契约测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np

from autovla.core.protocols import FrameworkProtocol, PolicyProtocol, RunnerProtocol
from autovla.core.types import ActionChunk, BatchSample, FrameworkOutput, ModelInput, RawSample


def _raw_sample(**overrides: Any) -> RawSample:
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.zeros((2, 7), dtype=np.float32),
        "state": np.zeros((7,), dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"episode_id": "ep-protocol"},
    }
    payload.update(overrides)
    return RawSample(**payload)


def _model_input() -> ModelInput:
    batch = BatchSample(samples=(_raw_sample(),), metadata={"batch_id": "batch-protocol"})
    return ModelInput(batch=batch, tensors={"state": np.ones((1, 7), dtype=np.float32)})


def _action_chunk() -> ActionChunk:
    return ActionChunk(
        values=np.ones((2, 7), dtype=np.float32),
        mask=None,
        horizon=2,
        action_dim=7,
        normalized=True,
    )


class FakeFramework:
    """用于验证 FrameworkProtocol 结构契约的最小框架。"""

    def __init__(self) -> None:
        self.forward_calls = 0

    def forward(self, batch: ModelInput) -> FrameworkOutput:
        self.forward_calls += 1
        return FrameworkOutput(
            loss=0.25,
            losses={"main": 0.25},
            metrics={"batch_size": float(batch.batch.batch_size)},
            action_pred=None,
        )

    def predict_action(self, obs: ModelInput) -> ActionChunk:
        _ = obs
        return _action_chunk()


class FakeRunner:
    """用于验证 RunnerProtocol 生命周期契约的最小运行器。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.setup_called = False
        self.saved_steps: list[int] = []
        self.resume_path: Path | None = None

    def setup(self) -> None:
        self.setup_called = True

    def train(self) -> Mapping[str, float]:
        return {"loss": 0.1}

    def evaluate(self) -> Mapping[str, float]:
        return {"success_rate": 1.0}

    def save_checkpoint(self, step: int) -> Path:
        self.saved_steps.append(step)
        return self.root / f"step-{step}.ckpt"

    def resume(self, path: Path) -> int:
        self.resume_path = path
        if not self.saved_steps:
            return 0
        return self.saved_steps[-1]


class FakePolicy:
    """用于验证 PolicyProtocol 交互契约的最小策略。"""

    def __init__(self) -> None:
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def select_action(self, observation: ModelInput) -> ActionChunk:
        _ = observation
        return _action_chunk()


def test_should_accept_framework_protocol_implementation() -> None:
    """验证显式 FrameworkProtocol 注解接受结构匹配实现。"""
    fake = FakeFramework()
    framework: FrameworkProtocol = fake

    output = framework.forward(_model_input())

    assert output.metrics["batch_size"] == 1.0
    assert fake.forward_calls == 1


def test_should_forward_and_predict_action_through_framework_protocol() -> None:
    """验证可通过 FrameworkProtocol 同时前向和预测动作。"""
    framework: FrameworkProtocol = FakeFramework()
    model_input = _model_input()

    output = framework.forward(model_input)
    action = framework.predict_action(model_input)

    assert output.loss == 0.25
    assert action.values.shape == (2, 7)


def test_should_accept_runner_protocol_implementation(tmp_path: Path) -> None:
    """验证显式 RunnerProtocol 注解接受结构匹配实现。"""
    runner: RunnerProtocol = FakeRunner(tmp_path)

    metrics = runner.evaluate()

    assert metrics["success_rate"] == 1.0


def test_should_exercise_runner_lifecycle_methods(tmp_path: Path) -> None:
    """验证 RunnerProtocol 生命周期方法可串联调用。"""
    fake = FakeRunner(tmp_path)
    runner: RunnerProtocol = fake

    runner.setup()
    train_metrics = runner.train()
    eval_metrics = runner.evaluate()
    checkpoint = runner.save_checkpoint(12)
    resumed_step = runner.resume(checkpoint)

    assert fake.setup_called is True
    assert train_metrics["loss"] == 0.1
    assert eval_metrics["success_rate"] == 1.0
    assert checkpoint == tmp_path / "step-12.ckpt"
    assert fake.resume_path == checkpoint
    assert resumed_step == 12


def test_should_accept_policy_protocol_implementation() -> None:
    """验证显式 PolicyProtocol 注解接受结构匹配实现。"""
    policy: PolicyProtocol = FakePolicy()

    action = policy.select_action(_model_input())

    assert action.horizon == 2
    assert action.action_dim == 7


def test_should_reset_and_select_action_through_policy_protocol() -> None:
    """验证可通过 PolicyProtocol 重置并选择动作。"""
    fake = FakePolicy()
    policy: PolicyProtocol = fake

    policy.reset()
    action = policy.select_action(_model_input())

    assert fake.reset_count == 1
    assert action.normalized is True
