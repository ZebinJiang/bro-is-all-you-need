"""M10 DeepSpeed/session 所有权的纯源码回归检查。"""

from pathlib import Path


def test_deepspeed_strategy_uses_canonical_stage_key() -> None:
    """验证 strategy/session 均使用配置层规范 ZeRO stage 键。"""

    source = Path("autovla/training/strategy/deepspeed.py").read_text(encoding="utf-8")

    assert 'return f"deepspeed_zero_{self._deepspeed_config.zero_stage}"' in source
    assert 'config.distributed.strategy_key != f"deepspeed_zero_{self._zero_stage}"' in source
    assert 'config.distributed.strategy_key != "deepspeed"' not in source


def test_deepspeed_step_requires_exactly_one_backward() -> None:
    """验证 session 明确追踪 forward/backward/step 的一次性状态。"""

    source = Path("autovla/training/strategy/deepspeed.py").read_text(encoding="utf-8")

    assert "DeepSpeed backward may run only once per forward" in source
    assert "boundary is None or not self._backward_complete" in source
    assert "self._backward_complete = True" in source
    assert "self._backward_complete = False" in source


def test_checkpoint_manager_delegates_scheduler_ownership() -> None:
    """验证公共 manager 不再直接重复恢复策略拥有的 scheduler。"""

    manager = Path("autovla/training/checkpointing/manager.py").read_text(encoding="utf-8")
    session = Path("autovla/training/session.py").read_text(encoding="utf-8")
    deepspeed = Path("autovla/training/strategy/deepspeed.py").read_text(encoding="utf-8")

    assert "strategy.scheduler_state_dict()" in manager
    assert "strategy.validate_scheduler_state_dict(scheduler_state)" in manager
    assert "strategy.load_scheduler_state_dict(" in manager
    assert "scheduler.load_state_dict(" not in manager
    assert "def load_scheduler_state_dict" in session
    assert "禁止公共 manager 重复加载" in deepspeed


def test_zero3_initialization_is_family_neutral_and_one_shot() -> None:
    """验证 CLI 仅进入策略上下文,模型 family 不感知 DeepSpeed。"""

    source = Path("autovla/training/strategy/deepspeed.py").read_text(encoding="utf-8")
    cli = Path("autovla/cli/train.py").read_text(encoding="utf-8")

    assert "class _ZeroInitializationContext" in source
    assert "initialization context may be requested once" in source
    assert "model must be built inside model_initialization_context" in source
    assert "PartitionedModelConstruction" not in source
    assert "StrategyInitializationContextFactory(strategy)" in cli
    assert "initialization_context_factory=initialization_context_factory" in cli
    context = cli.index("with initialization_context_factory():")
    factory = cli.index("components = model_factory(family_config)", context)
    assert context < factory
