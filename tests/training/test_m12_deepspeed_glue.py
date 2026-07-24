"""M12 DeepSpeed 分区加载和对称回收的纯 CPU 合同测试。"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest
import torch
from torch import nn

from autovla.training.distributed_receipts import StrategySessionIdentity
from autovla.training.strategy.deepspeed import (
    DeepSpeedStrategy,
    DeepSpeedTrainingSession,
)


class _ZeroStageThreeConfig:
    """提供策略边界需要的 ZeRO stage。"""

    zero_stage = 3


class _CompletedInitialization:
    """模拟已完成的分区构造事务。"""

    state = "completed"


class _FakeZero:
    """记录官方 GatheredParameters 是否包围 family loader。"""

    def __init__(self, events: list[str]) -> None:
        """绑定事件列表。"""

        self._events = events

    @contextmanager
    def GatheredParameters(
        self,
        params: tuple[nn.Parameter, ...],
        *,
        modifier_rank: int,
    ) -> Generator[None, None, None]:
        """模拟 DeepSpeed 官方分区参数协调上下文。"""

        assert params
        assert modifier_rank == 0
        self._events.append("gather-enter")
        try:
            yield
        finally:
            self._events.append("gather-exit")


class _FakeDeepSpeedModule:
    """仅提供测试所需的 zero 命名空间。"""

    def __init__(self, events: list[str]) -> None:
        """构造假 zero API。"""

        self.zero = _FakeZero(events)


def test_zero3_official_loader_runs_inside_strategy_partition_boundary() -> None:
    """ZeRO-3 不再提前阻断,且 family loader 保持语义所有权。"""

    events: list[str] = []
    strategy = object.__new__(DeepSpeedStrategy)
    setattr(strategy, "_deepspeed_config", _ZeroStageThreeConfig())
    setattr(strategy, "_initialization", _CompletedInitialization())
    setattr(strategy, "_deepspeed_module", _FakeDeepSpeedModule(events))
    model = nn.Linear(2, 2)

    def loader() -> str:
        """模拟 family 严格加载器并证明其位于协调上下文内。"""

        events.append("family-loader")
        return "family-evidence"

    result = strategy.load_official_checkpoint(model, loader)

    assert result == "family-evidence"
    assert events == ["gather-enter", "family-loader", "gather-exit"]
    source = Path("autovla/training/strategy/deepspeed.py").read_text(encoding="utf-8")
    strategy_start = source.index("class DeepSpeedStrategy")
    boundary_start = source.index("    def load_official_checkpoint(", strategy_start)
    boundary_end = source.index("    def prepare(", boundary_start)
    boundary = source[boundary_start:boundary_end]
    assert "GatheredParameters(parameters, modifier_rank=0)" in boundary
    assert "model.load_state_dict" not in boundary


class _DestroyingEngine:
    """记录 engine 销毁并可注入失败。"""

    def __init__(self, events: list[str], *, fail: bool = False) -> None:
        """保存事件列表和失败开关。"""

        self._events = events
        self._fail = fail

    def destroy(self) -> None:
        """记录销毁并按需抛错。"""

        self._events.append("engine")
        if self._fail:
            raise RuntimeError("engine destroy failed")


def _session(engine: object) -> DeepSpeedTrainingSession:
    """构造只用于 close 合同的最小 session。"""

    session = object.__new__(DeepSpeedTrainingSession)
    values: dict[str, object] = {
        "_engine": engine,
        "_optimizer": object(),
        "_scheduler": object(),
        "_owns_process_group": True,
        "_pending_boundary": None,
        "_backward_complete": False,
        "_window_micro_steps": 0,
        "_device": torch.device("cpu"),
        "_closed": False,
        "_teardown_receipt": None,
        "_session_identity": StrategySessionIdentity(
            strategy="deepspeed_zero_3",
            rank=0,
            world_size=2,
            topology_fingerprint="d" * 64,
            configuration_fingerprint="e" * 64,
        ),
    }
    vars(session).update(values)
    return session


def test_success_close_destroys_engine_clears_references_and_owned_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正常 close 与失败回滚对称,且第二次 close 无副作用。"""

    import autovla.training.strategy.deepspeed as module

    events: list[str] = []
    monkeypatch.setattr(module.dist, "is_initialized", lambda: True)
    monkeypatch.setattr(
        module.dist,
        "destroy_process_group",
        lambda: events.append("group"),
    )
    session = _session(_DestroyingEngine(events))

    session.close()
    session.close()

    assert events == ["engine", "group"]
    assert session.teardown_receipt is not None
    assert session.teardown_receipt.engine_status == "destroyed"
    assert session.teardown_receipt.process_group_status == "destroyed"
    assert session.teardown_receipt.references_cleared is True
    for name in ("_engine", "_optimizer", "_scheduler", "_device"):
        assert getattr(session, name) is None


def test_close_preserves_first_failure_but_still_destroys_owned_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """engine 销毁失败不能跳过后续进程组回收或引用清理。"""

    import autovla.training.strategy.deepspeed as module

    events: list[str] = []
    monkeypatch.setattr(module.dist, "is_initialized", lambda: True)
    monkeypatch.setattr(
        module.dist,
        "destroy_process_group",
        lambda: events.append("group"),
    )
    session = _session(_DestroyingEngine(events, fail=True))

    with pytest.raises(RuntimeError, match="engine destroy failed"):
        session.close()

    assert events == ["engine", "group"]
    assert session.teardown_receipt is not None
    assert session.teardown_receipt.engine_status == "failed"
    assert session.teardown_receipt.process_group_status == "destroyed"
    assert session.teardown_receipt.failure_types == ("RuntimeError",)
    session.close()
