"""M3 CLI local-smoke 执行层。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, cast

import numpy as np

from genesisvla.core.types import ActionMask, ImageLike, NumericArray, RawSample
from genesisvla.dataloader import CollatedBatch, collate_raw_samples_typed
from genesisvla.training.config import LocalRunnerDryRunConfig
from genesisvla.training.execution_manifest import write_execution_manifest
from genesisvla.training.local_runner import LocalRunner
from genesisvla.training.testing import DeterministicActionFramework


@dataclass(frozen=True, slots=True)
class LocalSmokeExecutionResult:
    """记录一次 CLI local-smoke 的可验证输出。"""

    execution_manifest_path: Path
    checkpoint_manifest_path: Path
    resumed_step: int
    train_metrics: Mapping[str, float]
    eval_metrics: Mapping[str, float]


def _sample_actions(config: LocalRunnerDryRunConfig, *, sample_index: int) -> NumericArray:
    """构造小型 deterministic action 目标。"""
    values = np.arange(config.action_horizon * config.action_dim, dtype=np.float32)
    actions = values.reshape(config.action_horizon, config.action_dim) + float(sample_index)
    return cast(NumericArray, actions)


def _sample_mask(config: LocalRunnerDryRunConfig, *, sample_index: int) -> ActionMask:
    """构造严格 bool action mask。"""
    mask = np.ones((config.action_horizon, config.action_dim), dtype=np.bool_)
    if config.action_horizon * config.action_dim > 1 and sample_index == 1:
        mask[-1, -1] = False
    return cast(ActionMask, mask)


def _sample_image(*, sample_index: int) -> ImageLike:
    """构造不依赖真实数据集的小型图像张量。"""
    image = np.arange(12, dtype=np.float32).reshape(2, 2, 3)
    return cast(ImageLike, image + float(sample_index))


def _build_local_smoke_batch(config: LocalRunnerDryRunConfig) -> CollatedBatch:
    """用公开 M2 contracts 构造纯内存 local-smoke batch。"""
    samples: list[RawSample] = []
    for index in range(2):
        samples.append(
            RawSample(
                images={"rgb": _sample_image(sample_index=index)},
                language=f"local smoke instruction {index}",
                actions=_sample_actions(config, sample_index=index),
                state=cast(
                    NumericArray,
                    np.asarray([float(config.seed), float(index)], dtype=np.float32),
                ),
                robot_tag="local-smoke-test-double",
                metadata={
                    "action_mask": _sample_mask(config, sample_index=index),
                    "sample_source": {
                        "dataset": "in-memory-local-smoke",
                        "sample_index": index,
                        "sample_key": f"local-smoke-{index}",
                    },
                },
            )
        )
    return collate_raw_samples_typed(samples)


def run_local_smoke(config: LocalRunnerDryRunConfig) -> LocalSmokeExecutionResult:
    """执行 deterministic CPU-only local-smoke 并写出 manifest。"""
    runner = LocalRunner(
        config=config.to_local_runner_config(),
        framework=DeterministicActionFramework(prediction_value=1.0),
        batches=(_build_local_smoke_batch(config),),
    )
    runner.setup()
    train_metrics = runner.train()
    eval_metrics = runner.evaluate()
    checkpoint_manifest_path = runner.save_checkpoint(runner.state.step)
    resumed_step = runner.resume(checkpoint_manifest_path)
    execution_manifest_path = write_execution_manifest(
        config,
        train_metrics=train_metrics,
        eval_metrics=eval_metrics,
        checkpoint_manifest_path=checkpoint_manifest_path,
        resumed_step=resumed_step,
    )
    return LocalSmokeExecutionResult(
        execution_manifest_path=execution_manifest_path,
        checkpoint_manifest_path=checkpoint_manifest_path,
        resumed_step=resumed_step,
        train_metrics=train_metrics,
        eval_metrics=eval_metrics,
    )
