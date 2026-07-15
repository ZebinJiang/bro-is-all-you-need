"""PreparedTrainingSession 架构与 source-only 所有权测试。"""

import importlib.util
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


class _IntSubclass(int):
    """提供必须被运行时计数契约拒绝的整数子类。"""


class _FakeDeepSpeedCounters:
    """提供不执行模型或训练的 DeepSpeed 公共计数与清梯度假对象。"""

    def __init__(self, global_steps: object, skipped_steps: object) -> None:
        """保存计数并初始化清梯度调用记录。"""

        self.global_steps = global_steps
        self.skipped_steps = skipped_steps
        self.zero_grad_calls = 0

    def zero_grad(self) -> None:
        """记录一次官方公共清梯度调用。"""

        self.zero_grad_calls += 1


def test_topology_and_step_result_import_without_torch() -> None:
    """在阻止 Torch 解析的新进程中验证纯 metadata 契约可导入。"""

    script = """
import importlib.abc
import sys

class BlockTorch(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "torch" or fullname.startswith("torch."):
            raise ModuleNotFoundError("Torch intentionally unavailable")
        return None

sys.meta_path.insert(0, BlockTorch())
import autovla.training.strategy as strategy
from autovla.training.session import OptimizerStepResult, TrainingTopology
assert "torch" not in sys.modules
assert "SingleGpuStrategy" in dir(strategy)
assert TrainingTopology.__name__ == "TrainingTopology"
assert OptimizerStepResult.__name__ == "OptimizerStepResult"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_optimizer_step_result_is_typed_and_frozen() -> None:
    """验证 committed-step 结果不能被 callback 侧篡改。"""

    from autovla.training.session import OptimizerStepResult

    result = OptimizerStepResult(
        update_committed=True,
        global_grad_norm=0.5,
        learning_rates=(1e-4,),
        overflow_detected=False,
        skipped_reason=None,
        micro_step=4,
        optimizer_step=1,
    )

    assert result.update_committed is True
    field_name = "optimizer_step"
    with pytest.raises(FrozenInstanceError):
        setattr(result, field_name, 2)


def test_strategy_lazy_exports_preserve_canonical_identity() -> None:
    """验证懒导出返回 session canonical 对象且具体策略保持延迟。"""

    script = """
import sys
import autovla.training.strategy as strategy
from autovla.training.session import PreparedTrainingSession, TrainingStrategy
assert strategy.PreparedTrainingSession is PreparedTrainingSession
assert strategy.TrainingStrategy is TrainingStrategy
assert "autovla.training.strategy.single_device" not in sys.modules
assert "autovla.training.strategy.deepspeed" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_concrete_strategy_remains_torch_runtime_boundary() -> None:
    """验证具体策略解析才进入 Torch 依赖边界。"""

    script = """
import importlib.abc
import sys

class BlockTorch(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "torch" or fullname.startswith("torch."):
            raise ModuleNotFoundError("Torch intentionally unavailable")
        return None

sys.meta_path.insert(0, BlockTorch())
import autovla.training.strategy as strategy
assert "torch" not in sys.modules
try:
    strategy.SingleGpuStrategy
except ModuleNotFoundError as error:
    assert "Torch intentionally unavailable" in str(error)
else:
    raise AssertionError("concrete strategy unexpectedly loaded without Torch")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("counter", (True, _IntSubclass(1)))
def test_session_runtime_counters_require_builtin_int(counter: object) -> None:
    """验证拓扑和 step 结果拒绝 bool 与整数子类。"""

    from autovla.training.session import OptimizerStepResult, TrainingTopology

    with pytest.raises(TypeError, match="built-in integer"):
        TrainingTopology(
            rank=counter,
            local_rank=0,
            world_size=1,
            backend="none",
            device_index=0,
            node_rank=0,
            local_world_size=1,
            launcher="direct",
            strategy="single_gpu",
        )
    with pytest.raises(TypeError, match="built-in integer"):
        OptimizerStepResult(
            update_committed=False,
            global_grad_norm=None,
            learning_rates=(1e-4,),
            overflow_detected=False,
            skipped_reason="gradient_accumulation",
            micro_step=counter,
            optimizer_step=0,
        )


def test_engine_has_no_strategy_branch_or_ordinary_optimizer_step() -> None:
    """验证 Engine 只消费 generic session 调用。"""

    source = Path("autovla/training/engine.py").read_text(encoding="utf-8")

    assert "strategy_key" not in source
    assert ".optimizer.step(" not in source
    assert ".scheduler.step(" not in source
    assert "session.forward(" in source
    assert "session.backward(" in source
    assert "session.step(" in source
    assert "step_result.update_committed" in source


def test_deepspeed_integration_is_lazy_and_uses_only_dependency_runtime() -> None:
    """验证 DeepSpeed 仅在策略文件延迟导入且没有复制/替代 runtime。"""

    source = Path("autovla/training/strategy/deepspeed.py").read_text(encoding="utf-8")
    registry = Path("autovla/training/registry.py").read_text(encoding="utf-8")

    assert 'import_module("deepspeed")' in source
    assert "deepspeed.initialize" not in registry
    assert ".initialize(" in source
    assert "._engine.backward(" in source
    assert "._engine.step(" in source
    assert "._engine.zero_grad(" in source
    assert "is_gradient_accumulation_boundary(" in source
    assert "(self._engine.micro_steps + 1) %" not in source
    assert "self._optimizer_steps = _committed_optimizer_steps(" in source
    assert "._engine.save_checkpoint(" in source
    assert "._engine.load_checkpoint(" in source
    assert "accelerate" not in source.lower()
    assert '"offload_optimizer"' not in source
    assert '"offload_param"' not in source
    assert "module.zero.Init(config_dict_or_path=self._generated_config)" in source
    assert "DeepSpeed ZeRO-3 model must be built inside model_initialization_context" in source
    assert "model.construct_model()" not in source
    cli = Path("autovla/cli/train.py").read_text(encoding="utf-8")
    context = cli.index("with initialization_context_factory():")
    construct = cli.index("components = model_factory(family_config)", context)
    assert context < construct


def test_failed_deepspeed_prepare_cleanup_preserves_preexisting_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """失败注入证明仅回收当前 prepare 新建的 engine 与进程组。"""

    if importlib.util.find_spec("torch") is None:
        pytest.skip("project-local Torch runtime is unavailable")
    import autovla.training.strategy.deepspeed as deepspeed_strategy

    events: list[str] = []

    class Engine:
        def destroy(self) -> None:
            events.append("engine")

    monkeypatch.setattr(deepspeed_strategy.dist, "is_initialized", lambda: True)
    monkeypatch.setattr(
        deepspeed_strategy.dist,
        "destroy_process_group",
        lambda: events.append("group"),
    )
    deepspeed_strategy._rollback_failed_prepare(engine=Engine(), process_group_preexisting=True)
    assert events == ["engine"]
    deepspeed_strategy._rollback_failed_prepare(engine=Engine(), process_group_preexisting=False)
    assert events == ["engine", "engine", "group"]


def test_deepspeed_prepare_failure_points_share_one_transaction() -> None:
    """构造、优化器、initialize、返回校验与 session 校验都进入同一回滚。"""

    source = Path("autovla/training/strategy/deepspeed.py").read_text(encoding="utf-8")
    prepare = source[source.index("    def prepare(", source.index("class DeepSpeedStrategy")) :]
    begin = prepare.index("try:")
    rollback = prepare.index("_rollback_failed_prepare(")
    for marker in (
        "optimizer_factory(model)",
        "scheduler_factory(optimizer, batches_per_epoch)",
        "module.initialize(",
        "isinstance(engine_value, _DeepSpeedEngine)",
        "DeepSpeedTrainingSession(",
        "session.setup()",
    ):
        assert begin < prepare.index(marker) < rollback
    assert "except BaseException:" in prepare[:rollback]


def test_nonfinite_loss_cleanup_preserves_engine_stop_path() -> None:
    """验证非有限损失先清 session 梯度再记录根停止原因。"""

    source = Path("autovla/training/engine.py").read_text(encoding="utf-8")

    forward = source.index("self.session.forward(")
    finite = source.index("torch.isfinite(", forward)
    zero_grad = source.index("self.session.zero_grad()", finite)
    stop_reason = source.index("StopReason.NONFINITE_LOSS", zero_grad)
    assert forward < finite < zero_grad < stop_reason


def test_deepspeed_counter_and_zero_grad_protocol_fake() -> None:
    """验证 committed 计数和 pending 窗口清理由轻量假 engine 驱动。"""

    if importlib.util.find_spec("torch") is None:
        pytest.skip("project-local Torch runtime is unavailable")
    from autovla.training.strategy.deepspeed import (
        DeepSpeedTrainingSession,
        _committed_optimizer_steps,
    )

    engine = _FakeDeepSpeedCounters(global_steps=7, skipped_steps=2)
    assert _committed_optimizer_steps(engine.global_steps, engine.skipped_steps) == 5
    with pytest.raises(ValueError, match="cannot exceed"):
        _committed_optimizer_steps(1, 2)
    with pytest.raises(TypeError, match="built-in integer"):
        _committed_optimizer_steps(True, 0)

    session = DeepSpeedTrainingSession.__new__(DeepSpeedTrainingSession)
    object.__setattr__(session, "_engine", engine)
    object.__setattr__(session, "_pending_boundary", True)
    object.__setattr__(session, "_backward_complete", True)
    object.__setattr__(session, "_window_micro_steps", 3)
    session.zero_grad()

    assert engine.zero_grad_calls == 1
    assert session._pending_boundary is None
    assert session._backward_complete is False
    assert session._window_micro_steps == 0


def test_registry_exposes_only_supported_production_strategy_keys() -> None:
    """验证 registry 仅暴露 single、DDP 和三个显式 ZeRO stage。"""

    from autovla.core.registry import UnknownRegistrationError
    from autovla.training.registry import build_training_strategy_registry

    registry = build_training_strategy_registry()

    assert registry.names() == (
        "deepspeed_zero_1",
        "deepspeed_zero_2",
        "deepspeed_zero_3",
        "distributed_data_parallel",
        "single_gpu",
    )
    with pytest.raises(UnknownRegistrationError):
        registry.get("fsdp2")


def test_historical_fsdp_import_is_an_unsupported_shim() -> None:
    """验证历史导入给出确定迁移指导且没有隐藏实现。"""

    source = Path("autovla/training/strategy/fully_sharded_data_parallel.py").read_text(
        encoding="utf-8"
    )

    assert "raise RuntimeError" in source
    assert "deepspeed with zero_stage=3" in source
    assert "save_sharded_checkpoint" not in source
