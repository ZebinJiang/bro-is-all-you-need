"""生产 checkpoint 的真正独立解释器恢复证明。"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None
requires_torch = pytest.mark.skipif(
    not TORCH_AVAILABLE,
    reason="fresh-process checkpoint test requires the production Torch runtime",
)


def _run_worker(command: tuple[str, ...], *, cwd: Path, environment: dict[str, str]) -> None:
    """运行独立解释器,并在失败时保留完整子进程诊断。"""

    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.fail(
            f"fresh checkpoint worker failed ({completed.returncode})\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


_WORKER = r'''
import json
import random
import sys
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import torch

from autovla.data.types import DatasetManifest, DataModuleState, DataStage
from autovla.models.families.gr00t_n1d6.checkpoint import Gr00tN1d6CheckpointAdapter
from autovla.training.callbacks.base import TrainingCallback
from autovla.training.checkpointing.identity import checkpoint_compatibility_fingerprint
from autovla.training.checkpointing.manager import CheckpointManager
from autovla.training.precision import PrecisionPolicy
from autovla.training.state import TrainingState
from autovla.training.strategy.base import PreparedTrainingSessionBase
from autovla.training.telemetry.logger import MetricLogger


class CheckpointSession(PreparedTrainingSessionBase):
    """仅实现 checkpoint 公共状态协议,不提供训练 runtime。"""

    def __init__(self):
        """绑定无缩放精度状态但不设置设备。"""

        super().__init__(PrecisionPolicy("float32"))

    @property
    def rank(self):
        """返回唯一协议 rank。"""

        return 0

    @property
    def local_rank(self):
        """返回唯一协议 local rank。"""

        return 0

    @property
    def world_size(self):
        """返回单进程 world size。"""

        return 1

    def setup(self):
        """拒绝训练 runtime 初始化。"""

        raise RuntimeError("checkpoint protocol fake has no training setup")

    def prepare_model(self, model):
        """拒绝模型准备。"""

        raise RuntimeError("checkpoint protocol fake cannot prepare a model")

    def all_finite(self, finite):
        """拒绝训练有限性检查。"""

        raise RuntimeError("checkpoint protocol fake cannot execute training")

    def reduce_mean(self, value):
        """拒绝训练归约。"""

        raise RuntimeError("checkpoint protocol fake cannot execute training")

    def broadcast_text(self, value):
        """返回单进程 checkpoint 控制文本。"""

        return value

    def collect_rank_runtime_state(self, local_state):
        """规范化唯一 rank 控制状态。"""

        return self._validate_rank_runtime_states((local_state,))

    def clip_gradients(self, model, max_norm):
        """拒绝训练梯度裁剪。"""

        raise RuntimeError("checkpoint protocol fake cannot execute training")

    def model_state_dict(self, model):
        """物化 checkpoint 测试模型状态。"""

        return model.state_dict()

    def load_model_state_dict(self, model, state):
        """严格恢复 checkpoint 测试模型状态。"""

        model.load_state_dict(dict(state), strict=True)

    def barrier(self):
        """单进程协议无需 barrier。"""

        return None

    def close(self):
        """假对象不持有运行时资源。"""

        return None


class DataState:
    """提供严格且无加载器进程的数据模块状态。"""

    def __init__(self):
        self.manifest = DatasetManifest(
            datasets=("fresh-local",),
            backends=("lerobot_local",),
            splits=("train",),
            sample_counts=(1,),
            source_fingerprints=("fresh-source",),
            schema_fingerprints=("fresh-schema",),
            temporal_query_fingerprints=("fresh-temporal",),
            weights=(1.0,),
            embodiments=("gr1",),
            mix_strategy="weighted",
            mix_seed=3,
            balance_by="dataset",
            loader_batch_size=1,
            loader_drop_last=False,
            transform_fingerprint="fresh-transform",
            statistics_fingerprint="fresh-statistics",
            metadata={"backend_decision": "NO_BACKEND_WINNER"},
        )
        self.value = DataModuleState(
            schema_version=DataModuleState.SCHEMA_VERSION,
            stage=DataStage.FIT,
            manifest_fingerprint="fresh-manifest",
            train_loader=None,
            validation_loader=None,
        ).to_dict()

    def dataset_manifest(self):
        """返回 fresh-process 恢复使用的数据身份。"""

        return self.manifest

    def state_dict(self):
        return dict(self.value)

    def validate_state_dict(self, state):
        parsed = DataModuleState.from_dict(state)
        if parsed.manifest_fingerprint != "fresh-manifest":
            raise ValueError("data manifest mismatch")

    def load_state_dict(self, state):
        self.validate_state_dict(state)
        self.value = dict(state)


def runtime(root):
    model = torch.nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.01)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.5)
    strategy = CheckpointSession()
    adapter = Gr00tN1d6CheckpointAdapter()
    config = {"name": "fresh", "model": {"shape": (2, [1, 3])}, "data": {"ids": (0, 1, 2, 3)}}
    manager = CheckpointManager(
        root=root,
        run_id="fresh-process",
        model_family="gr00t_n1d6",
        autovla_version="0.1.0.dev0",
        git_commit="b" * 40,
        config=config,
        config_fingerprint=checkpoint_compatibility_fingerprint(config),
        model_config_fingerprint="model",
        model_capability_fingerprint="capability",
        checkpoint_adapter_name=f"{type(adapter).__module__}.{type(adapter).__qualname__}",
        data_manifest={"decision": "NO_BACKEND_WINNER", "nested": ("map", [0, 1])},
        data_fingerprints={"data": "fresh-manifest"},
        normalization={"mean": (0.0, [1.0])},
        provenance={"local_files_only": True},
    )
    return (
        model,
        optimizer,
        scheduler,
        strategy,
        adapter,
        manager,
        DataState(),
        (TrainingCallback(),),
        MetricLogger(stdout=False),
    )


def probes():
    return {
        "python": random.random(),
        "numpy": float(np.random.random()),
        "torch": float(torch.rand(())),
    }


phase = sys.argv[1]
root = Path(sys.argv[2])
result = Path(sys.argv[3])
if phase == "save":
    random.seed(71)
    np.random.seed(72)
    torch.manual_seed(73)
    model, optimizer, scheduler, strategy, adapter, manager, data, callbacks, logger = runtime(root)
    for _ in range(2):
        optimizer.zero_grad(set_to_none=True)
        model(torch.tensor([[1.0, 2.0]])).square().mean().backward()
        optimizer.step()
        scheduler.step()
    logger.log({"step": 2})
    state = TrainingState(global_step=2, optimizer_step=2, samples_seen=2)
    checkpoint = manager.save(
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        strategy=strategy,
        data_module=data,
        callbacks=callbacks,
        metric_logger=logger,
        state=state,
        reason="fresh-process",
    )
    selected = [float(value) for value in next(model.parameters()).detach().flatten()]
    result.write_text(json.dumps({
        "checkpoint": str(checkpoint),
        "next_ids": list(range(state.samples_seen, state.samples_seen + 2)),
        "scheduler_epoch": scheduler.last_epoch,
        "learning_rate": scheduler.get_last_lr(),
        "parameters": selected,
        "optimizer_step": int(next(iter(optimizer.state.values()))["step"].item()),
        "logger": logger.state_dict(),
        "probes": probes(),
    }, sort_keys=True), encoding="utf-8")
elif phase == "load":
    checkpoint = Path(json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))["checkpoint"])
    random.seed(991)
    np.random.seed(992)
    torch.manual_seed(993)
    model, optimizer, scheduler, strategy, adapter, manager, data, callbacks, logger = runtime(root)
    state = manager.load(
        checkpoint,
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        strategy=strategy,
        data_module=data,
        family_adapter=adapter,
        callbacks=callbacks,
        metric_logger=logger,
    )
    selected = [float(value) for value in next(model.parameters()).detach().flatten()]
    result.write_text(json.dumps({
        "next_ids": list(range(state.samples_seen, state.samples_seen + 2)),
        "scheduler_epoch": scheduler.last_epoch,
        "learning_rate": scheduler.get_last_lr(),
        "parameters": selected,
        "optimizer_step": int(next(iter(optimizer.state.values()))["step"].item()),
        "logger": logger.state_dict(),
        "probes": probes(),
    }, sort_keys=True), encoding="utf-8")
else:
    raise AssertionError(phase)
'''


@requires_torch
def test_checkpoint_resume_in_two_genuinely_fresh_interpreters(tmp_path: Path) -> None:
    """B1 完全退出后,B2 从 JSON manifest 恢复精确下一样本和状态身份。"""

    repository = Path(__file__).resolve().parents[2]
    save_result = tmp_path / "save-result.json"
    load_result = tmp_path / "load-result.json"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repository)
    _run_worker(
        (sys.executable, "-c", _WORKER, "save", str(tmp_path / "checkpoints"), str(save_result)),
        cwd=tmp_path,
        environment=environment,
    )
    _run_worker(
        (
            sys.executable,
            "-c",
            _WORKER,
            "load",
            str(tmp_path / "fresh-manager-root"),
            str(load_result),
            str(save_result),
        ),
        cwd=tmp_path,
        environment=environment,
    )
    saved = json.loads(save_result.read_text(encoding="utf-8"))
    restored = json.loads(load_result.read_text(encoding="utf-8"))
    saved.pop("checkpoint")
    assert restored == saved
