"""M12 DeepSpeed 分区加载和对称回收的纯 CPU 合同测试。"""

from collections.abc import Mapping
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


class _ZeroStageTwoConfig:
    """提供非分区官方加载边界需要的 ZeRO stage。"""

    zero_stage = 2


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


class _SingleRankTopology:
    """为纯 CPU 假对象提供 rank0 分区协调身份。"""

    rank = 0
    world_size = 1


class _FakePartitionedSink:
    """记录 family-owned sink 的审计、写入和证据恢复。"""

    def __init__(self, events: list[str]) -> None:
        """绑定事件并记录已审计名称。"""

        self._events = events
        self._audited: set[str] = set()

    def prepare(self) -> None:
        """记录 rank0 准备。"""

        self._events.append("sink-prepare")

    def audit_tensor(
        self,
        name: str,
        logical_shape: tuple[int, ...],
        /,
    ) -> None:
        """记录逐张量逻辑 shape 审计。"""

        assert all(isinstance(dimension, int) for dimension in logical_shape)
        self._audited.add(name)
        self._events.append(f"audit:{name}")

    def complete_audit(
        self,
        *,
        parameter_names: tuple[str, ...],
        buffer_names: tuple[str, ...],
    ) -> None:
        """证明模型参数与 buffer 已全部审计。"""

        assert self._audited == set(parameter_names) | set(buffer_names)
        self._events.append("audit-complete")

    def load_tensor(self, name: str, tensor: object, /) -> None:
        """记录 rank0-only mutation 调用。"""

        assert isinstance(tensor, torch.Tensor)
        self._events.append(f"load:{name}")

    def finish(self) -> dict[str, object]:
        """返回可 collective 传输的 family 载荷。"""

        self._events.append("sink-finish")
        return {"evidence": "family-evidence"}

    def restore_result(self, payload: Mapping[str, object], /) -> str:
        """恢复 family 结果。"""

        self._events.append("sink-restore")
        assert payload == {"evidence": "family-evidence"}
        return "family-evidence"


def test_zero3_official_loader_runs_inside_strategy_partition_boundary() -> None:
    """ZeRO-3 逐参数 gather,且只有 family sink 拥有 mutation。"""

    events: list[str] = []
    strategy = object.__new__(DeepSpeedStrategy)
    vars(strategy).update(
        {
            "_deepspeed_config": _ZeroStageThreeConfig(),
            "_initialization": _CompletedInitialization(),
            "_deepspeed_module": _FakeDeepSpeedModule(events),
            "_topology": _SingleRankTopology(),
        }
    )
    model = nn.Linear(2, 2)

    def loader() -> str:
        """普通 loader 在 ZeRO-3 下绝不能执行。"""

        raise AssertionError("ordinary whole-model loader must not run under ZeRO-3")

    result = strategy.load_official_checkpoint(
        model,
        loader,
        partitioned_loader=lambda: _FakePartitionedSink(events),
    )

    assert result == "family-evidence"
    assert events == [
        "sink-prepare",
        "audit:weight",
        "audit:bias",
        "audit-complete",
        "gather-enter",
        "load:weight",
        "gather-exit",
        "gather-enter",
        "load:bias",
        "gather-exit",
        "sink-finish",
        "sink-restore",
    ]
    source = Path("autovla/training/strategy/deepspeed.py").read_text(encoding="utf-8")
    strategy_start = source.index("class DeepSpeedStrategy")
    boundary_start = source.index("    def load_official_checkpoint(", strategy_start)
    boundary_end = source.index("    def prepare(", boundary_start)
    boundary = source[boundary_start:boundary_end]
    assert "GatheredParameters((parameter,), modifier_rank=0)" in boundary
    assert "tuple(model.parameters())" not in boundary
    assert "model.load_state_dict" not in boundary


def test_zero3_missing_family_partition_sink_fails_closed() -> None:
    """ZeRO-3 不能退回普通 whole-model loader。"""

    strategy = object.__new__(DeepSpeedStrategy)
    vars(strategy).update(
        {
            "_deepspeed_config": _ZeroStageThreeConfig(),
            "_initialization": _CompletedInitialization(),
            "_deepspeed_module": _FakeDeepSpeedModule([]),
            "_topology": _SingleRankTopology(),
        }
    )
    with pytest.raises(RuntimeError, match="family-owned partitioned adapter"):
        strategy.load_official_checkpoint(nn.Linear(2, 2), lambda: "forbidden")


def test_zero12_preserves_direct_family_strict_loader() -> None:
    """ZeRO-1/2 继续执行原 family loader,不要求 partition sink。"""

    strategy = object.__new__(DeepSpeedStrategy)
    vars(strategy).update({"_deepspeed_config": _ZeroStageTwoConfig()})

    assert strategy.load_official_checkpoint(object(), lambda: "strict-local") == "strict-local"


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
