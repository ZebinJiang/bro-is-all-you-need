"""DDP rendezvous 与梯度有限性聚合的 CPU fake-dist 测试。"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Protocol, cast


@dataclass(frozen=True, slots=True)
class _FakeTopology:
    """提供生产 DDP setup 消费的最小已验证拓扑。"""

    rank: int = 1
    local_rank: int = 1
    world_size: int = 2
    device_index: int = 1
    master_addr: str | None = "node-a"
    master_port: int | None = 29500


class _FakeNativeSession:
    """为提取的 DDP 类提供 topology/device 公共基类。"""

    _topology: _FakeTopology
    _device: str

    @property
    def topology(self) -> _FakeTopology:
        """返回 fake 拓扑。"""

        return self._topology

    @property
    def device(self) -> str:
        """返回 fake CUDA 设备身份。"""

        return self._device


class _FakeCuda:
    """记录 setup 的 CUDA 副作用顺序。"""

    def __init__(self, events: list[str]) -> None:
        """绑定共享事件列表。"""

        self._events = events

    def is_available(self) -> bool:
        """声明 fake CUDA 可用。"""

        return True

    def set_device(self, device: object) -> None:
        """记录设备绑定。"""

        self._events.append(f"set_device:{device}")


class _FakeTorch:
    """暴露 DDP setup 所需的最小 torch 表面。"""

    def __init__(self, events: list[str]) -> None:
        """构造 fake CUDA 模块。"""

        self.cuda = _FakeCuda(events)


class _FakeDist:
    """记录 process-group 初始化参数。"""

    def __init__(self, events: list[str]) -> None:
        """初始化未建组状态。"""

        self._events = events
        self.initialized = False
        self.kwargs: dict[str, object] = {}

    def is_initialized(self) -> bool:
        """返回 fake 建组状态。"""

        return self.initialized

    def init_process_group(self, **kwargs: object) -> None:
        """记录建组参数并提交状态。"""

        self._events.append("init_process_group")
        self.kwargs = dict(kwargs)
        self.initialized = True

    def destroy_process_group(self) -> None:
        """回收 fake process group。"""

        self.initialized = False

    def get_backend(self) -> str:
        """返回生产要求的 fake backend。"""

        return "nccl"

    def get_world_size(self) -> int:
        """返回 fake world size。"""

        return 2

    def get_rank(self) -> int:
        """返回 fake rank。"""

        return 1


class _FakePrecision:
    """记录 precision setup 而不导入 Torch。"""

    def __init__(self, events: list[str]) -> None:
        """绑定共享事件列表。"""

        self._events = events

    def setup(self, device: object) -> None:
        """记录 precision 绑定。"""

        self._events.append(f"precision:{device}")


class _ExtractedSession(Protocol):
    """约束从生产 AST 提取的 fake session 可写和可调用表面。"""

    _topology: _FakeTopology
    _device: str
    _timeout_seconds: int
    _owns_process_group: bool
    precision: _FakePrecision

    def setup(self) -> None:
        """执行提取的生产 setup。"""

        ...


def _fake_ddp_session() -> tuple[_ExtractedSession, _FakeDist, list[str]]:
    """从生产源码提取 DDP 类并绑定纯 CPU fake 模块。"""

    source = Path("autovla/training/strategy/distributed_data_parallel.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DistributedDataParallelTrainingSession"
    )
    class_node.bases = [ast.Name(id="NativePreparedTrainingSession", ctx=ast.Load())]
    module = ast.fix_missing_locations(
        ast.Module(
            body=[
                ast.ImportFrom(
                    module="__future__",
                    names=[ast.alias(name="annotations")],
                    level=0,
                ),
                class_node,
            ],
            type_ignores=[],
        )
    )
    events: list[str] = []
    fake_dist = _FakeDist(events)
    namespace: dict[str, object] = {
        "NativePreparedTrainingSession": _FakeNativeSession,
        "torch": _FakeTorch(events),
        "dist": fake_dist,
        "timedelta": timedelta,
    }
    exec(compile(module, "distributed_data_parallel.py", "exec"), namespace)
    session_type = cast(type[object], namespace["DistributedDataParallelTrainingSession"])
    session = cast(_ExtractedSession, session_type.__new__(session_type))
    object.__setattr__(session, "_topology", _FakeTopology())
    object.__setattr__(session, "_device", "cuda:1")
    object.__setattr__(session, "_timeout_seconds", 30)
    object.__setattr__(session, "_owns_process_group", False)
    session.precision = _FakePrecision(events)
    return session, fake_dist, events


def test_setup_runs_with_cpu_fake_dist_and_explicit_rendezvous() -> None:
    """提取的生产 setup 在纯 CPU fake-dist 上验证显式 rendezvous。"""

    session, fake_dist, events = _fake_ddp_session()

    session.setup()

    assert fake_dist.kwargs["init_method"] == "tcp://node-a:29500"
    assert fake_dist.kwargs["rank"] == 1
    assert fake_dist.kwargs["world_size"] == 2
    assert events == ["set_device:cuda:1", "init_process_group", "precision:cuda:1"]


def test_engine_proves_loader_counts_before_strategy_prepare() -> None:
    """Engine 必须在任何 collective-bearing strategy prepare 前验证数据计划。"""

    source = Path("autovla/training/engine.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    setup = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "setup"
        and any(
            isinstance(child, ast.Attribute) and child.attr == "optimizer_factory"
            for child in ast.walk(node)
        )
    )
    setup_source = ast.get_source_segment(source, setup)
    assert setup_source is not None
    proof = setup_source.index("self._validate_distributed_loader_plan(topology, loader)")
    prepare = setup_source.index("self.context.strategy.prepare(")
    assert proof < prepare


def test_setup_source_validates_rendezvous_before_side_effects() -> None:
    """源码顺序保证 rendezvous 校验先于 CUDA 和 process-group 副作用。"""

    source = Path("autovla/training/strategy/distributed_data_parallel.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    setup = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "setup"
        and any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "init_process_group"
            for child in ast.walk(node)
        )
    )
    setup_source = ast.get_source_segment(source, setup)
    assert setup_source is not None
    rendezvous = setup_source.index("init_method = self._rendezvous_init_method()")
    cuda_check = setup_source.index("torch.cuda.is_available()")
    process_group = setup_source.index("dist.init_process_group(")
    assert rendezvous < cuda_check < process_group
    for argument in ("init_method=init_method", "rank=self.rank", "world_size=self.world_size"):
        assert argument in setup_source


def test_gradient_finiteness_source_has_one_host_decision_and_no_rank_collective() -> None:
    """源码结构固定为一次 ``item``, 且梯度检查不调用 rank collective。"""

    source = Path("autovla/training/session.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_gradients_finite"
    )
    item_calls = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "item"
    ]
    assert len(item_calls) == 1
    method_source = ast.get_source_segment(source, method)
    assert method_source is not None
    assert "_foreach_norm" in method_source
    assert "all_finite" not in method_source
