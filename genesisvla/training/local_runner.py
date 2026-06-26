"""GenesisVLA CPU-only 本地 runner smoke。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, cast

import numpy as np

from genesisvla.core.types import FrameworkOutput, ModelInput
from genesisvla.dataloader import CollatedBatch
from genesisvla.training.adapter import collated_batch_to_model_input
from genesisvla.training.checkpoint import (
    CheckpointManifest,
    ResumeSpec,
    read_checkpoint_manifest,
    write_checkpoint_manifest,
)


class _RunnerFramework(Protocol):
    """本地 runner 所需的最小框架协议。"""

    def forward(self, batch: ModelInput) -> FrameworkOutput:
        """执行一次前向。"""
        ...


@dataclass(frozen=True, slots=True)
class LocalRunnerConfig:
    """CPU-only local runner 的确定性配置。"""

    run_id: str
    run_root: Path
    max_steps: int
    seed: int
    model_registry_key: str
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str

    def __post_init__(self) -> None:
        """校验本地 runner 配置。"""
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if type(self.seed) is not int:
            raise TypeError("seed must be an int")
        for name in (
            "model_registry_key",
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")

    @property
    def run_dir(self) -> Path:
        """返回本次 smoke run 目录。"""
        return self.run_root / self.run_id

    def resume_spec(self) -> ResumeSpec:
        """返回 checkpoint 恢复兼容性描述。"""
        return ResumeSpec(
            model_registry_key=self.model_registry_key,
            dataset_fingerprint=self.dataset_fingerprint,
            transform_fingerprint=self.transform_fingerprint,
            statistics_fingerprint=self.statistics_fingerprint,
        )


@dataclass(slots=True)
class LocalRunnerState:
    """记录 runner 生命周期状态。"""

    setup_complete: bool = False
    step: int = 0
    epoch: int = 0


class LocalRunner:
    """确定性 CPU-only 本地 runner smoke。"""

    def __init__(
        self,
        *,
        config: LocalRunnerConfig,
        framework: _RunnerFramework,
        batches: Sequence[CollatedBatch],
    ) -> None:
        """绑定 runner 配置、框架 test double 与 in-memory batch。"""
        if not batches:
            raise ValueError("batches must not be empty")
        self.config = config
        self.framework = framework
        self.batches = tuple(batches)
        self.state = LocalRunnerState()
        self._last_batch: CollatedBatch | None = None
        self._last_metrics: dict[str, float] | None = None

    @property
    def checkpoint_dir(self) -> Path:
        """返回 checkpoint manifest 目录。"""
        return self.config.run_dir / "checkpoints"

    def setup(self) -> None:
        """创建本地 run 目录并进入可训练状态。"""
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.state.setup_complete = True

    def train(self) -> dict[str, float]:
        """按固定 batch 顺序执行无优化器的 deterministic smoke。"""
        self._require_setup()
        metrics: dict[str, float] = {}
        for _ in range(self.config.max_steps):
            batch = self.batches[self.state.step % len(self.batches)]
            metrics = self._run_batch(batch)
            self.state.step += 1
            metrics["step"] = float(self.state.step)
            metrics["epoch"] = float(self.state.epoch)
            self._last_batch = batch
            self._last_metrics = dict(metrics)
        return dict(metrics)

    def evaluate(self) -> dict[str, float]:
        """在第一条 batch 上执行确定性评估, 不推进 step。"""
        self._require_setup()
        metrics = self._run_batch(self.batches[0])
        metrics["step"] = float(self.state.step)
        metrics["epoch"] = float(self.state.epoch)
        return metrics

    def save_checkpoint(self, step: int) -> Path:
        """写出 checkpoint manifest。"""
        self._require_setup()
        if self._last_batch is None or self._last_metrics is None:
            raise ValueError("train must run before save_checkpoint")
        manifest = self._build_manifest(
            step=step,
            batch=self._last_batch,
            metrics=self._last_metrics,
        )
        return write_checkpoint_manifest(self.checkpoint_dir / f"step-{step}.json", manifest)

    def resume(self, path: Path) -> int:
        """读取 manifest 并校验恢复兼容性。"""
        self._require_setup()
        manifest = read_checkpoint_manifest(path)
        step = manifest.validate_resume(self.config.resume_spec())
        self.state.step = step
        self.state.epoch = manifest.epoch
        return step

    def _require_setup(self) -> None:
        """确保 runner 生命周期已 setup。"""
        if not self.state.setup_complete:
            raise RuntimeError("LocalRunner.setup() must be called first")

    def _model_input(self, batch: CollatedBatch) -> ModelInput:
        """为当前状态构造 ModelInput。"""
        return collated_batch_to_model_input(
            batch,
            dataset_fingerprint=self.config.dataset_fingerprint,
            transform_fingerprint=self.config.transform_fingerprint,
            statistics_fingerprint=self.config.statistics_fingerprint,
            seed=self.config.seed,
            epoch=self.state.epoch,
        )

    def _run_batch(self, batch: CollatedBatch) -> dict[str, float]:
        """执行单个 batch 并提取确定性指标。"""
        output = self.framework.forward(self._model_input(batch))
        metrics = dict(output.metrics)
        if output.loss is not None:
            metrics["loss"] = float(np.asarray(output.loss).item())
        return metrics

    def _build_manifest(
        self,
        *,
        step: int,
        batch: CollatedBatch,
        metrics: dict[str, float],
    ) -> CheckpointManifest:
        """从最近一次训练 batch 构造 checkpoint manifest。"""
        if batch.action_mask is None or batch.action_horizon is None or batch.action_dim is None:
            raise ValueError("checkpoint manifest requires action mask and action sizes")
        return CheckpointManifest(
            run_id=self.config.run_id,
            step=step,
            epoch=self.state.epoch,
            model_registry_key=self.config.model_registry_key,
            runner_config={"max_steps": self.config.max_steps, "seed": self.config.seed},
            dataset_fingerprint=self.config.dataset_fingerprint,
            transform_fingerprint=self.config.transform_fingerprint,
            statistics_fingerprint=self.config.statistics_fingerprint,
            action_horizon=tuple(int(value) for value in batch.action_horizon.tolist()),
            action_dim=tuple(int(value) for value in batch.action_dim.tolist()),
            mask_shape=cast(
                tuple[int, int, int],
                tuple(int(value) for value in batch.action_mask.shape),
            ),
            valid_action_elements=int(np.count_nonzero(batch.action_mask)),
            sample_source=tuple(dict(item) for item in batch.sample_source),
            metrics=dict(metrics),
        )
