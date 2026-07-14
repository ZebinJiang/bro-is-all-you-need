"""生产 checkpoint 预验证、回滚和 FSDP2 边界行为测试。"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import pickle
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from functools import partial
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import TYPE_CHECKING, Iterator, Protocol, Sequence, TypeGuard, cast, runtime_checkable

import numpy as np
import pytest
from numpy.typing import NDArray

from autovla.training.checkpointing.identity import (
    canonicalize_json_value,
    stable_fingerprint,
)
from autovla.training.strategy.base import (
    CheckpointCollectiveError,
    CheckpointCollectiveProtocol,
    CheckpointCollectiveStatus,
)

TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None
requires_torch = pytest.mark.skipif(
    not TORCH_AVAILABLE,
    reason="production checkpoint runtime tests require torch; no substitute runtime is permitted",
)

if TYPE_CHECKING or TORCH_AVAILABLE:
    import torch

    from autovla.data.module import DataModule
    from autovla.data.types import DataModuleState, DataStage
    from autovla.models.families.gr00t_n1d6.checkpoint import Gr00tN1d6CheckpointAdapter
    from autovla.training.callbacks.base import TrainingCallback
    from autovla.training.checkpointing.identity import checkpoint_compatibility_fingerprint
    from autovla.training.checkpointing.manager import CheckpointManager
    from autovla.training.checkpointing.manifest import ProductionCheckpointManifest
    from autovla.training.checkpointing.state_dict import (
        capture_rng_state,
        restore_rng_state,
        sha256_file,
        validate_rng_state,
    )
    from autovla.training.engine import TrainingEngine
    from autovla.training.precision import PrecisionPolicy
    from autovla.training.state import TrainingState
    from autovla.training.strategy.base import TrainingStrategy
    from autovla.training.strategy.fully_sharded_data_parallel import (
        FullyShardedDataParallelStrategy,
    )
    from autovla.training.strategy.single_device import SingleDeviceStrategy
    from autovla.training.telemetry.logger import MetricLogger
else:
    torch = None


@runtime_checkable
class _TorchLoader(Protocol):
    """描述测试使用的 tensor-only torch.load 调用。"""

    def __call__(
        self,
        filename: str | Path,
        *,
        map_location: str,
        weights_only: bool,
    ) -> object:
        """读取本地测试 checkpoint。"""
        ...


@runtime_checkable
class _TorchSaver(Protocol):
    """描述测试使用的 torch.save 调用。"""

    def __call__(self, value: object, filename: str | Path) -> None:
        """写入本地测试 checkpoint。"""
        ...


@runtime_checkable
class _OptimizerStep(Protocol):
    """描述优化器 step 的测试调用。"""

    def __call__(self, closure: object | None = None) -> object:
        """推进一次优化器状态。"""
        ...


@runtime_checkable
class _ModuleFilter(Protocol):
    """描述 FSDP 模块筛选器。"""

    def __call__(self, name: str, module: object) -> bool:
        """返回模块是否应被 FSDP 包装。"""
        ...


@runtime_checkable
class _ApplyWithRollback(Protocol):
    """描述 checkpoint manager 的白盒应用边界。"""

    def __call__(
        self,
        manager: CheckpointManager,
        *,
        root: Path,
        manifest: ProductionCheckpointManifest,
        prepared: Mapping[str, object],
        model: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler.LRScheduler,
        strategy: TrainingStrategy,
        data_module: DataModule,
        callbacks: Sequence[TrainingCallback],
        metric_logger: MetricLogger,
    ) -> TrainingState:
        """应用预验证状态并返回训练状态。"""
        ...


class _CanonicalMode(Enum):
    """提供枚举持久化测试值。"""

    EXACT = "exact"


@dataclass(frozen=True)
class _CanonicalRecord:
    """提供 dataclass 字段级规范化测试值。"""

    path: Path
    values: tuple[int, bool]


def test_canonical_json_value_is_recursive_stable_and_typed(tmp_path: Path) -> None:
    """嵌套结构共享唯一 JSON 形状且保持布尔和整数类型。"""

    tuple_value = {
        "record": _CanonicalRecord(tmp_path / "asset", (1, True)),
        "mode": _CanonicalMode.EXACT,
        "nested": (("sample", 7), [False, 2.5]),
    }
    list_value = {
        "nested": [["sample", 7], [False, 2.5]],
        "mode": "exact",
        "record": {"path": str(tmp_path / "asset"), "values": [1, True]},
    }
    canonical = canonicalize_json_value(tuple_value)
    assert canonical == list_value
    canonical_record = _object_mapping(_string_mapping(canonical)["record"])
    canonical_values = _object_sequence(canonical_record["values"])
    assert type(canonical_values[0]) is int
    assert type(canonical_values[1]) is bool
    assert stable_fingerprint(tuple_value) == stable_fingerprint(list_value)
    assert json.loads(json.dumps(canonical)) == canonical


@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_canonical_json_value_rejects_non_finite_with_path(value: float) -> None:
    """非有限浮点在字段路径处失败关闭。"""

    with pytest.raises(ValueError, match=r"\$\.data_manifest\.stats\[1\]"):
        canonicalize_json_value({"stats": [0.0, value]}, "$.data_manifest")


def test_canonical_json_value_rejects_unsupported_value_with_path() -> None:
    """不支持的对象报告精确字段路径和运行时类型。"""

    with pytest.raises(TypeError, match=r"\$\.config\.model\.opaque.*object"):
        canonicalize_json_value({"model": {"opaque": object()}}, "$.config")


@pytest.mark.parametrize("invalid_key", (None, 1))
def test_canonical_json_value_rejects_every_non_string_mapping_key(invalid_key: object) -> None:
    """所有非字符串映射键均报告容器路径和运行时类型。"""

    expected_type = type(invalid_key).__name__
    with pytest.raises(
        TypeError,
        match=rf"mapping key at \$\.config\.model: {expected_type}",
    ):
        canonicalize_json_value({"model": {invalid_key: "wrong"}}, "$.config")


class _CardinalityLoader:
    """用声明和实际批次数分离的迭代器探测终止契约。"""

    def __init__(self, declared: int, actual: int) -> None:
        """保存声明基数和实际可交付对象数。"""

        self.declared = declared
        self.actual = actual

    def __len__(self) -> int:
        """返回引擎用于计划的声明批次数。"""

        return self.declared

    def __iter__(self) -> Iterator[int]:
        """交付指定数量的无类型测试对象。"""

        yield from range(self.actual)


def _cardinality_engine(loader: _CardinalityLoader) -> TrainingEngine:
    """构造只执行真实 train_epoch 控制流的最小引擎。"""

    engine = TrainingEngine.__new__(TrainingEngine)
    state = SimpleNamespace(
        epoch=0,
        resume_seed=0,
        global_step=0,
        should_stop=False,
        stop_reason=None,
    )
    data_module = SimpleNamespace(train_dataloader=lambda: loader)
    object.__setattr__(
        engine,
        "context",
        SimpleNamespace(
            state=state,
            config=SimpleNamespace(max_steps=None),
            data_module=data_module,
        ),
    )
    object.__setattr__(engine, "_setup", True)
    object.__setattr__(engine, "_closed", False)
    object.__setattr__(engine, "_force_accumulation_boundary", False)
    object.__setattr__(engine, "_is_final_loader_batch", False)
    object.__setattr__(engine, "_deferred_optimizer_step_output", None)
    object.__setattr__(engine, "_deferred_scheduled_checkpoint", False)
    object.__setattr__(engine, "_data_wait_seconds", 0.0)

    def ignore_event(self: TrainingEngine, event: str, *args: object) -> None:
        """忽略白盒引擎回调。"""

    def ignore_batch(self: TrainingEngine, batch: object) -> None:
        """忽略白盒训练批次。"""

    object.__setattr__(engine, "_call", MethodType(ignore_event, engine))
    object.__setattr__(engine, "train_step", MethodType(ignore_batch, engine))
    return engine


class _FakeCollectiveTransport:
    """用预先约定的全 rank 结果记录真实协议的集体顺序。"""

    def __init__(
        self,
        rank: int,
        script: tuple[tuple[CheckpointCollectiveStatus, ...], ...],
    ) -> None:
        """保存本 rank、共同脚本和事件序列。"""

        self._rank = rank
        self._script = list(script)
        self.events: list[tuple[str, str]] = []

    @property
    def rank(self) -> int:
        """返回模拟 rank。"""

        return self._rank

    @property
    def world_size(self) -> int:
        """固定模拟两个 rank。"""

        return 2

    @property
    def is_primary(self) -> bool:
        """返回是否模拟 rank 0。"""

        return self.rank == 0

    def gather_checkpoint_status(
        self,
        status: CheckpointCollectiveStatus,
    ) -> tuple[CheckpointCollectiveStatus, ...]:
        """核对本地状态后返回每个 rank 相同的有序结果。"""

        self.events.append(("gather", status.phase))
        if not self._script:
            raise AssertionError("unexpected checkpoint collective gather")
        gathered = self._script.pop(0)
        assert status == gathered[self.rank]
        payloads = tuple(item.to_payload() for item in gathered)
        for payload in payloads:
            assert all(type(value) in {str, int, bool} for value in payload.values())
            assert all(not isinstance(value, BaseException) for value in payload.values())
        return tuple(CheckpointCollectiveStatus.from_payload(payload) for payload in payloads)

    def barrier(self) -> None:
        """记录协议的共同 barrier。"""

        self.events.append(("barrier", ""))

    def assert_complete(self) -> None:
        """确认协议消费了全部预期集体。"""

        assert not self._script


def _status_pair(
    phase: str,
    *,
    failing_rank: int | None = None,
    detail: str = "injected failure",
) -> tuple[CheckpointCollectiveStatus, CheckpointCollectiveStatus]:
    """构造按 rank 排列的共同阶段结果。"""

    statuses: list[CheckpointCollectiveStatus] = []
    for rank in range(2):
        if rank == failing_rank:
            statuses.append(CheckpointCollectiveStatus.failure(phase, rank, RuntimeError(detail)))
        else:
            statuses.append(CheckpointCollectiveStatus.success(phase, rank))
    return statuses[0], statuses[1]


def _collective_order(transport: _FakeCollectiveTransport) -> tuple[tuple[str, str], ...]:
    """返回仅包含集体调用的顺序证据。"""

    return tuple(transport.events)


@requires_torch
@pytest.mark.parametrize(
    ("declared", "actual", "error"),
    ((2, 1, "underflow"), (2, 3, "overflow"), (0, 1, "overflow")),
)
def test_training_engine_rejects_loader_cardinality_drift(
    monkeypatch: pytest.MonkeyPatch,
    declared: int,
    actual: int,
    error: str,
) -> None:
    """真实 epoch 控制流必须在状态推进前拒绝欠交付和超交付。"""

    import autovla.training.engine as engine_module

    def identity_batch(batch: object) -> object:
        """保留基数测试对象。"""

        return batch

    monkeypatch.setattr(engine_module, "_require_training_batch", identity_batch)
    engine = _cardinality_engine(_CardinalityLoader(declared, actual))
    with pytest.raises(RuntimeError, match=error):
        engine.train_epoch()
    assert engine.state.epoch == 0
    assert engine.state.resume_seed == 0


@requires_torch
def test_training_engine_requires_terminal_stop_before_epoch_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """精确基数只有在额外 next 确认 StopIteration 后才提交 epoch。"""

    import autovla.training.engine as engine_module

    def identity_batch(batch: object) -> object:
        """保留终止探针对象。"""

        return batch

    monkeypatch.setattr(engine_module, "_require_training_batch", identity_batch)
    engine = _cardinality_engine(_CardinalityLoader(2, 2))
    engine.train_epoch()
    assert engine.state.epoch == 1
    assert engine.state.resume_seed == 1


@requires_torch
def test_strategy_local_rank_public_contract() -> None:
    """单设备与分布式策略公开节点内 rank,供数据分区绑定。"""

    from autovla.training.strategy.distributed_data_parallel import (
        DistributedDataParallelStrategy,
    )

    precision = PrecisionPolicy("float32")
    single = SingleDeviceStrategy(precision, device="cpu")
    ddp = DistributedDataParallelStrategy(precision, expected_world_size=2)
    fsdp2 = FullyShardedDataParallelStrategy(
        precision,
        expected_world_size=2,
        module_filter=lambda name, module: False,
    )
    object.__setattr__(ddp, "_local_rank", 1)
    object.__setattr__(fsdp2, "_local_rank", 1)
    assert single.local_rank == 0
    assert ddp.local_rank == 1
    assert fsdp2.local_rank == 1


def _perform_test_action(
    actions: list[str] | None,
    name: str,
    *,
    error: str | None = None,
) -> None:
    """记录模拟动作并按需注入本 rank 失败。"""

    if actions is not None:
        actions.append(name)
    if error is not None:
        raise RuntimeError(error)


def test_rank_zero_publication_failure_has_common_cleanup_and_exit_order() -> None:
    """rank 0 发布失败时全部 rank 同序清理并抛出同一错误。"""

    script = (
        _status_pair("save.publish", failing_rank=0, detail="publication failed"),
        _status_pair("save.publish.cleanup"),
    )
    messages: list[str] = []
    for rank in range(2):
        transport = _FakeCollectiveTransport(rank, script)
        local_actions: list[str] = []

        with pytest.raises(CheckpointCollectiveError) as caught:
            CheckpointCollectiveProtocol(transport).run_phase(
                "save.publish",
                partial(
                    _perform_test_action,
                    local_actions,
                    "publish",
                    error="publication failed",
                ),
                primary_only=True,
                cleanup=partial(_perform_test_action, local_actions, "cleanup"),
            )
        messages.append(str(caught.value))
        assert _collective_order(transport) == (
            ("gather", "save.publish"),
            ("gather", "save.publish.cleanup"),
            ("barrier", ""),
        )
        assert local_actions == (["publish", "cleanup"] if rank == 0 else [])
        transport.assert_complete()
    assert messages[0] == messages[1]


def test_nonzero_apply_failure_rolls_back_every_rank_in_common_order() -> None:
    """非零 rank 应用失败时成功 peer 也进入相同回滚协议。"""

    script = (
        _status_pair("restore.apply", failing_rank=1, detail="rank one apply failed"),
        _status_pair("restore.rollback"),
        _status_pair("restore.cleanup"),
    )
    messages: list[str] = []
    for rank in range(2):
        transport = _FakeCollectiveTransport(rank, script)
        local_actions: list[str] = []

        with pytest.raises(CheckpointCollectiveError) as caught:
            CheckpointCollectiveProtocol(transport).run_apply_with_rollback(
                apply=partial(
                    _perform_test_action,
                    local_actions,
                    "apply",
                    error="rank one apply failed" if rank == 1 else None,
                ),
                rollback=partial(_perform_test_action, local_actions, "rollback"),
                cleanup=partial(_perform_test_action, local_actions, "cleanup"),
            )
        messages.append(str(caught.value))
        assert _collective_order(transport) == (
            ("gather", "restore.apply"),
            ("gather", "restore.rollback"),
            ("gather", "restore.cleanup"),
            ("barrier", ""),
        )
        assert local_actions[:2] == ["apply", "rollback"]
        assert ("cleanup" in local_actions) is (rank == 0)
        transport.assert_complete()
    assert messages[0] == messages[1]


def test_rollback_failure_is_reported_after_common_cleanup_order() -> None:
    """任一 rank 回滚失败仍保持共同清理和共同错误。"""

    script = (
        _status_pair("restore.apply", failing_rank=1, detail="apply failed"),
        _status_pair("restore.rollback", failing_rank=0, detail="rollback failed"),
        _status_pair("restore.cleanup"),
    )
    messages: list[str] = []
    for rank in range(2):
        transport = _FakeCollectiveTransport(rank, script)

        with pytest.raises(CheckpointCollectiveError) as caught:
            CheckpointCollectiveProtocol(transport).run_apply_with_rollback(
                apply=partial(
                    _perform_test_action,
                    None,
                    "apply",
                    error="apply failed" if rank == 1 else None,
                ),
                rollback=partial(
                    _perform_test_action,
                    None,
                    "rollback",
                    error="rollback failed" if rank == 0 else None,
                ),
                cleanup=partial(_perform_test_action, None, "cleanup"),
            )
        messages.append(str(caught.value))
        assert _collective_order(transport) == (
            ("gather", "restore.apply"),
            ("gather", "restore.rollback"),
            ("gather", "restore.cleanup"),
            ("barrier", ""),
        )
        transport.assert_complete()
    assert messages[0] == messages[1]
    assert "phase=restore.rollback,rank=0" in messages[0]


def test_all_success_commits_without_rollback_and_keeps_collective_order() -> None:
    """全部应用成功时跳过回滚但仍共同清理后提交。"""

    script = (
        _status_pair("restore.apply"),
        _status_pair("restore.cleanup"),
    )
    for rank in range(2):
        transport = _FakeCollectiveTransport(rank, script)
        local_actions: list[str] = []

        CheckpointCollectiveProtocol(transport).run_apply_with_rollback(
            apply=partial(_perform_test_action, local_actions, "apply"),
            rollback=partial(_perform_test_action, local_actions, "rollback"),
            cleanup=partial(_perform_test_action, local_actions, "cleanup"),
        )
        assert _collective_order(transport) == (
            ("gather", "restore.apply"),
            ("gather", "restore.cleanup"),
            ("barrier", ""),
        )
        assert local_actions == (["apply", "cleanup"] if rank == 0 else ["apply"])
        transport.assert_complete()


class _DataState:
    """为 checkpoint 测试提供严格 DataModuleState 行为。"""

    def __init__(self) -> None:
        """构造无 loader 的 committed fit 边界。"""

        self.value = DataModuleState(
            schema_version=DataModuleState.SCHEMA_VERSION,
            stage=DataStage.FIT,
            manifest_fingerprint="manifest",
            train_loader=None,
            validation_loader=None,
        ).to_dict()

    def state_dict(self) -> Mapping[str, object]:
        """返回独立状态副本。"""

        return copy.deepcopy(self.value)

    def validate_state_dict(self, state: Mapping[str, object]) -> None:
        """验证 schema 和当前 manifest 身份。"""

        parsed = DataModuleState.from_dict(state)
        if parsed.manifest_fingerprint != "manifest":
            raise ValueError("data manifest mismatch")

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        """验证后原子替换状态。"""

        self.validate_state_dict(state)
        self.value = copy.deepcopy(dict(state))


def _manager(
    root: Path,
    *,
    config: Mapping[str, object] | None = None,
) -> CheckpointManager:
    """构造固定身份的生产 checkpoint manager。"""

    adapter = Gr00tN1d6CheckpointAdapter()
    resolved_config: Mapping[str, object] = config or {
        "name": "checkpoint-test",
        "model": {"family": "gr00t_n1d6"},
        "training": {
            "checkpoint": {
                "directory": str(root),
                "resume_from": None,
                "save_every_steps": 1,
            },
            "logging": {"jsonl_path": str(root / "metrics.jsonl"), "log_every_steps": 1},
            "optimization": {"key": "adamw", "learning_rate": 0.001},
            "precision": {"mode": "float32"},
            "distributed": {"strategy_key": "single_device", "world_size": 1},
        },
        "data": {"schema": "stable"},
    }
    return CheckpointManager(
        root=root,
        run_id="checkpoint-test",
        model_family="gr00t_n1d6",
        autovla_version="0.1.0.dev0",
        git_commit="a" * 40,
        config=resolved_config,
        config_fingerprint=checkpoint_compatibility_fingerprint(resolved_config),
        model_config_fingerprint="model-config-fingerprint",
        model_capability_fingerprint="model-capability-fingerprint",
        checkpoint_adapter_name=f"{type(adapter).__module__}.{type(adapter).__qualname__}",
        data_manifest={"decision": "NO_BACKEND_WINNER"},
        data_fingerprints={"data": "manifest"},
        normalization={"statistics": "stats"},
        provenance={"local_files_only": True},
    )


def _runtime(tmp_path: Path) -> dict[str, object]:
    """建立单设备模型、优化器、调度器和控制状态。"""

    model = torch.nn.Sequential(torch.nn.Linear(3, 4), torch.nn.Linear(4, 2))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loss = model(torch.ones(2, 3)).square().mean()
    loss.backward()
    step: object = getattr(optimizer, "step", None)
    if not isinstance(step, _OptimizerStep):
        raise TypeError("optimizer step must be callable")
    step()
    optimizer.zero_grad(set_to_none=True)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda _: 1.0)
    strategy = SingleDeviceStrategy(PrecisionPolicy("float32"), device="cpu")
    strategy.setup()
    strategy.prepare_model(model)
    data = _DataState()
    callbacks = (TrainingCallback(),)
    logger = MetricLogger(stdout=False)
    manager = _manager(tmp_path / "checkpoints")
    state = TrainingState(global_step=1, optimizer_step=1, samples_seen=2)
    checkpoint = manager.save(
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        strategy=strategy,
        data_module=cast(DataModule, data),
        callbacks=callbacks,
        metric_logger=logger,
        state=state,
        reason="manual",
    )
    return {
        "model": model,
        "optimizer": optimizer,
        "scheduler": scheduler,
        "strategy": strategy,
        "data": data,
        "callbacks": callbacks,
        "logger": logger,
        "manager": manager,
        "checkpoint": checkpoint,
        "adapter": Gr00tN1d6CheckpointAdapter(),
    }


def _assert_nested_equal(left: object, right: object) -> None:
    """递归比较包含 tensor 的状态。"""

    if isinstance(left, torch.Tensor):
        assert isinstance(right, torch.Tensor)
        assert torch.equal(left, right)
    elif _is_object_mapping(left):
        assert _is_object_mapping(right) and set(left) == set(right)
        for key in left:
            _assert_nested_equal(left[key], right[key])
    elif _is_object_list(left):
        assert _is_object_list(right)
        assert len(left) == len(right)
        for first, second in zip(left, right, strict=True):
            _assert_nested_equal(first, second)
    elif _is_object_tuple(left):
        assert _is_object_tuple(right)
        assert len(left) == len(right)
        for first, second in zip(left, right, strict=True):
            _assert_nested_equal(first, second)
    else:
        assert left == right


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """收窄动态 checkpoint 映射。"""

    return isinstance(value, Mapping)


def _is_string_object_dict(value: object) -> TypeGuard[dict[str, object]]:
    """收窄需要原位修改的字符串键 checkpoint 字典。"""

    return _is_object_dict(value) and all(isinstance(key, str) for key in value)


def _is_object_dict(value: object) -> TypeGuard[dict[object, object]]:
    """收窄动态 checkpoint 字典。"""

    return isinstance(value, dict)


def _is_object_sequence(value: object) -> TypeGuard[list[object] | tuple[object, ...]]:
    """收窄动态 checkpoint 序列。"""

    return isinstance(value, (list, tuple))


def _is_object_list(value: object) -> TypeGuard[list[object]]:
    """收窄动态 checkpoint 列表。"""

    return isinstance(value, list)


def _is_object_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
    """收窄动态 checkpoint 元组。"""

    return isinstance(value, tuple)


def _object_mapping(value: object) -> Mapping[object, object]:
    """校验动态值为对象映射。"""

    if not _is_object_mapping(value):
        raise TypeError("expected checkpoint mapping")
    return value


def _string_mapping(value: object) -> Mapping[str, object]:
    """复制并校验字符串键 checkpoint 映射。"""

    mapping = _object_mapping(value)
    result: dict[str, object] = {}
    for key, item in mapping.items():
        if not isinstance(key, str):
            raise TypeError("checkpoint mapping keys must be strings")
        result[key] = item
    return result


def _string_dict(value: object) -> dict[str, object]:
    """原位返回字符串键字典供损坏注入测试使用。"""

    if not _is_string_object_dict(value):
        raise TypeError("expected mutable checkpoint dictionary")
    return value


def _object_sequence(value: object) -> list[object] | tuple[object, ...]:
    """校验动态值为 checkpoint 列表或元组。"""

    if not _is_object_sequence(value):
        raise TypeError("expected checkpoint sequence")
    return value


def _torch_load(path: str | Path) -> object:
    """通过精确协议调用 tensor-only torch.load。"""

    loader: object = getattr(torch, "load", None)
    if not isinstance(loader, _TorchLoader):
        raise TypeError("torch.load must be callable")
    return loader(path, map_location="cpu", weights_only=True)


def _torch_save(value: object, path: str | Path) -> None:
    """通过精确协议调用 torch.save。"""

    saver: object = getattr(torch, "save", None)
    if not isinstance(saver, _TorchSaver):
        raise TypeError("torch.save must be callable")
    saver(value, path)


def _snapshot(runtime: Mapping[str, object]) -> dict[str, object]:
    """捕获所有可变 live 状态用于拒绝后不变性证明。"""

    model = cast(torch.nn.Module, runtime["model"])
    optimizer = cast(torch.optim.Optimizer, runtime["optimizer"])
    scheduler = cast(torch.optim.lr_scheduler.LRScheduler, runtime["scheduler"])
    strategy = cast(SingleDeviceStrategy, runtime["strategy"])
    data = cast(_DataState, runtime["data"])
    logger = cast(MetricLogger, runtime["logger"])
    return {
        "model": copy.deepcopy(model.state_dict()),
        "optimizer": copy.deepcopy(optimizer.state_dict()),
        "scheduler": copy.deepcopy(scheduler.state_dict()),
        "strategy": copy.deepcopy(dict(strategy.strategy_state_dict())),
        "data": copy.deepcopy(data.state_dict()),
        "logger": copy.deepcopy(logger.state_dict()),
        "rng": capture_rng_state(),
    }


def _rewrite_checkpoint(checkpoint: Path, mutate: str) -> None:
    """注入一种结构损坏并同步摘要,确保命中预验证而非文件摘要。"""

    state_path = checkpoint / "state.pt"
    payload = _string_dict(_torch_load(state_path))
    if mutate == "model":
        model = _string_dict(payload["model"])
        key = next(iter(model))
        model[key] = torch.zeros(1)
    elif mutate == "optimizer":
        optimizer = _string_dict(payload["optimizer"])
        param_groups = _object_sequence(optimizer["param_groups"])
        _string_dict(param_groups[0])["params"] = []
    elif mutate == "scheduler":
        _string_dict(payload["scheduler"]).pop("last_epoch")
    elif mutate == "strategy":
        _string_dict(payload["strategy"])["name"] = "wrong"
    elif mutate == "training":
        _string_dict(payload["training_state"])["microbatch_step"] = 1
    elif mutate == "data":
        rank_state = _string_dict(_string_dict(payload["rank_runtime_state"])["0"])
        _string_dict(rank_state["data_module"])["manifest_fingerprint"] = "corrupt"
    elif mutate == "rng":
        rank_state = _string_dict(_string_dict(payload["rank_runtime_state"])["0"])
        _string_dict(rank_state["rng"])["torch_cpu"] = torch.zeros(
            1,
            dtype=torch.uint8,
        )
    elif mutate == "rank":
        _string_dict(_string_dict(payload["rank_runtime_state"])["0"])["schema_version"] = "wrong"
    elif mutate == "callback":
        payload["callback_state"] = {"wrong": {}}
    elif mutate == "logger":
        _string_dict(payload["logger_state"])["records_written"] = -1
    else:
        raise AssertionError(mutate)
    _torch_save(payload, state_path)
    manifest_path = checkpoint / "manifest.json"
    manifest = _string_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
    manifest["state_sha256"] = sha256_file(state_path)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    completion_path = checkpoint / "COMPLETED.json"
    completion = _string_dict(json.loads(completion_path.read_text(encoding="utf-8")))
    completion["state_sha256"] = manifest["state_sha256"]
    completion["manifest_sha256"] = sha256_file(manifest_path)
    completion_path.write_text(
        json.dumps(completion, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@requires_torch
def test_manifest_records_complete_identity_and_control_state(tmp_path: Path) -> None:
    """生产 manifest 和控制 payload 覆盖版本、Git、指纹、adapter 与状态。"""

    runtime = _runtime(tmp_path)
    checkpoint = cast(Path, runtime["checkpoint"])
    manifest = _string_dict(json.loads((checkpoint / "manifest.json").read_text(encoding="utf-8")))
    payload = _string_dict(_torch_load(checkpoint / "state.pt"))
    assert manifest["schema_version"] == "autovla.production_training_checkpoint.v3"
    assert manifest["autovla_version"] == "0.1.0.dev0"
    assert manifest["git_commit"] == "a" * 40
    assert manifest["model_config_fingerprint"] == "model-config-fingerprint"
    assert manifest["config_fingerprint"] == checkpoint_compatibility_fingerprint(
        _string_mapping(manifest["config"])
    )
    assert manifest["model_capability_fingerprint"] == "model-capability-fingerprint"
    adapter = _string_mapping(manifest["checkpoint_adapter_report"])["adapter"]
    assert isinstance(adapter, str) and adapter.endswith("Gr00tN1d6CheckpointAdapter")
    assert manifest["state_storage"] == "consolidated"
    assert {
        "model",
        "optimizer",
        "scheduler",
        "strategy",
        "training_state",
        "callback_state",
        "logger_state",
        "rank_runtime_state",
    } == set(payload)


@requires_torch
def test_checkpoint_compatibility_excludes_only_operational_locations(tmp_path: Path) -> None:
    """输出、日志和 resume 路径可变,优化语义变化仍在应用前失败。"""
    runtime = _runtime(tmp_path)
    saved_manager = cast(CheckpointManager, runtime["manager"])
    operational = copy.deepcopy(saved_manager.config)
    training = cast(dict[str, object], operational["training"])
    checkpoint = cast(dict[str, object], training["checkpoint"])
    logging = cast(dict[str, object], training["logging"])
    checkpoint["directory"] = str(tmp_path / "other-output")
    checkpoint["resume_from"] = str(runtime["checkpoint"])
    logging["jsonl_path"] = str(tmp_path / "other-log.jsonl")
    assert checkpoint_compatibility_fingerprint(operational) == saved_manager.config_fingerprint

    compatible = _manager(tmp_path / "compatible-root", config=operational)
    restored = compatible.load(
        cast(Path, runtime["checkpoint"]),
        model=cast(torch.nn.Module, runtime["model"]),
        optimizer=cast(torch.optim.Optimizer, runtime["optimizer"]),
        scheduler=cast(torch.optim.lr_scheduler.LRScheduler, runtime["scheduler"]),
        strategy=cast(SingleDeviceStrategy, runtime["strategy"]),
        data_module=cast(DataModule, runtime["data"]),
        family_adapter=cast(Gr00tN1d6CheckpointAdapter, runtime["adapter"]),
        callbacks=cast(tuple[TrainingCallback, ...], runtime["callbacks"]),
        metric_logger=cast(MetricLogger, runtime["logger"]),
    )
    assert restored.optimizer_step == 1

    incompatible = copy.deepcopy(operational)
    incompatible_training = cast(dict[str, object], incompatible["training"])
    optimization = cast(dict[str, object], incompatible_training["optimization"])
    optimization["learning_rate"] = 0.002
    incompatible_manager = _manager(tmp_path / "incompatible-root", config=incompatible)
    before = _snapshot(runtime)
    with pytest.raises(ValueError, match=r"config_fingerprint|config_compatibility"):
        incompatible_manager.load(
            cast(Path, runtime["checkpoint"]),
            model=cast(torch.nn.Module, runtime["model"]),
            optimizer=cast(torch.optim.Optimizer, runtime["optimizer"]),
            scheduler=cast(torch.optim.lr_scheduler.LRScheduler, runtime["scheduler"]),
            strategy=cast(SingleDeviceStrategy, runtime["strategy"]),
            data_module=cast(DataModule, runtime["data"]),
            family_adapter=cast(Gr00tN1d6CheckpointAdapter, runtime["adapter"]),
            callbacks=cast(tuple[TrainingCallback, ...], runtime["callbacks"]),
            metric_logger=cast(MetricLogger, runtime["logger"]),
        )
    _assert_nested_equal(before, _snapshot(runtime))


@requires_torch
def test_nested_identity_round_trip_and_mismatch_never_enters_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """嵌套 tuple/list 可恢复,而类型不匹配在 apply 入口前失败。"""

    config = {
        "name": "checkpoint-test",
        "model": {"family": "gr00t_n1d6", "layers": (2, [4, 8])},
        "data": {"schema": "stable"},
    }
    runtime = _runtime(tmp_path / "saved")
    checkpoint = cast(Path, runtime["checkpoint"])
    saved_manifest = _string_dict(
        json.loads((checkpoint / "manifest.json").read_text(encoding="utf-8"))
    )
    saved_manifest["config"] = canonicalize_json_value(config)
    saved_manifest["config_fingerprint"] = checkpoint_compatibility_fingerprint(config)
    manifest_path = checkpoint / "manifest.json"
    manifest_path.write_text(json.dumps(saved_manifest, sort_keys=True) + "\n", encoding="utf-8")
    completion_path = checkpoint / "COMPLETED.json"
    completion = _string_dict(json.loads(completion_path.read_text(encoding="utf-8")))
    completion["manifest_sha256"] = sha256_file(manifest_path)
    completion_path.write_text(json.dumps(completion, sort_keys=True) + "\n", encoding="utf-8")

    manager = _manager(tmp_path / "restored", config=config)
    calls = 0
    original_apply: object = getattr(CheckpointManager, "_apply_with_rollback", None)
    if not isinstance(original_apply, _ApplyWithRollback):
        raise TypeError("CheckpointManager apply boundary must be callable")

    def count_apply(
        self: CheckpointManager,
        *,
        root: Path,
        manifest: ProductionCheckpointManifest,
        prepared: Mapping[str, object],
        model: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler.LRScheduler,
        strategy: TrainingStrategy,
        data_module: DataModule,
        callbacks: Sequence[TrainingCallback],
        metric_logger: MetricLogger,
    ) -> TrainingState:
        """记录进入 apply 边界的次数。"""

        nonlocal calls
        calls += 1
        return original_apply(
            self,
            root=root,
            manifest=manifest,
            prepared=prepared,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            strategy=strategy,
            data_module=data_module,
            callbacks=callbacks,
            metric_logger=metric_logger,
        )

    monkeypatch.setattr(CheckpointManager, "_apply_with_rollback", count_apply)
    restored = manager.load(
        checkpoint,
        model=cast(torch.nn.Module, runtime["model"]),
        optimizer=cast(torch.optim.Optimizer, runtime["optimizer"]),
        scheduler=cast(torch.optim.lr_scheduler.LRScheduler, runtime["scheduler"]),
        strategy=cast(SingleDeviceStrategy, runtime["strategy"]),
        data_module=cast(DataModule, runtime["data"]),
        family_adapter=cast(Gr00tN1d6CheckpointAdapter, runtime["adapter"]),
        callbacks=cast(tuple[TrainingCallback, ...], runtime["callbacks"]),
        metric_logger=cast(MetricLogger, runtime["logger"]),
    )
    assert restored.optimizer_step == 1
    assert calls == 1

    incompatible = copy.deepcopy(config)
    cast(dict[str, object], incompatible["model"])["layers"] = [2, [4, "8"]]
    rejected = _manager(tmp_path / "rejected", config=incompatible)
    before = _snapshot(runtime)
    with pytest.raises(ValueError, match="config_fingerprint"):
        rejected.load(
            checkpoint,
            model=cast(torch.nn.Module, runtime["model"]),
            optimizer=cast(torch.optim.Optimizer, runtime["optimizer"]),
            scheduler=cast(torch.optim.lr_scheduler.LRScheduler, runtime["scheduler"]),
            strategy=cast(SingleDeviceStrategy, runtime["strategy"]),
            data_module=cast(DataModule, runtime["data"]),
            family_adapter=cast(Gr00tN1d6CheckpointAdapter, runtime["adapter"]),
            callbacks=cast(tuple[TrainingCallback, ...], runtime["callbacks"]),
            metric_logger=cast(MetricLogger, runtime["logger"]),
        )
    assert calls == 1
    _assert_nested_equal(before, _snapshot(runtime))


@pytest.mark.parametrize(
    "corruption",
    (
        "model",
        "optimizer",
        "scheduler",
        "strategy",
        "training",
        "data",
        "rng",
        "rank",
        "callback",
        "logger",
    ),
)
@requires_torch
def test_corruption_is_rejected_before_any_live_state_mutation(
    tmp_path: Path,
    corruption: str,
) -> None:
    """每类结构损坏均在应用前拒绝且全部 live 状态保持不变。"""

    runtime = _runtime(tmp_path)
    before = _snapshot(runtime)
    _rewrite_checkpoint(cast(Path, runtime["checkpoint"]), corruption)
    manager = cast(CheckpointManager, runtime["manager"])
    with pytest.raises((TypeError, ValueError, RuntimeError)):
        manager.load(
            cast(Path, runtime["checkpoint"]),
            model=cast(torch.nn.Module, runtime["model"]),
            optimizer=cast(torch.optim.Optimizer, runtime["optimizer"]),
            scheduler=cast(torch.optim.lr_scheduler.LRScheduler, runtime["scheduler"]),
            strategy=cast(SingleDeviceStrategy, runtime["strategy"]),
            data_module=cast(DataModule, runtime["data"]),
            family_adapter=cast(Gr00tN1d6CheckpointAdapter, runtime["adapter"]),
            callbacks=cast(tuple[TrainingCallback, ...], runtime["callbacks"]),
            metric_logger=cast(MetricLogger, runtime["logger"]),
        )
    after = _snapshot(runtime)
    _assert_nested_equal(before, after)


@requires_torch
def test_apply_failure_rolls_back_model_optimizer_and_control_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """预验证后的意外 scheduler 失败会恢复进入 load 时的全部状态。"""

    runtime = _runtime(tmp_path)
    model = cast(torch.nn.Module, runtime["model"])
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.add_(7.0)
    before = _snapshot(runtime)
    scheduler = cast(torch.optim.lr_scheduler.LRScheduler, runtime["scheduler"])
    scheduler_type = type(scheduler)
    original_load = scheduler_type.load_state_dict
    calls = 0

    def fail_once(
        instance: torch.optim.lr_scheduler.LRScheduler,
        state: Mapping[str, object],
    ) -> None:
        """首次应用失败,回滚应用使用原实现。"""

        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected apply failure")
        original_load(instance, dict(state))

    monkeypatch.setattr(scheduler_type, "load_state_dict", fail_once)
    manager = cast(CheckpointManager, runtime["manager"])
    with pytest.raises(RuntimeError, match="injected apply failure"):
        manager.load(
            cast(Path, runtime["checkpoint"]),
            model=model,
            optimizer=cast(torch.optim.Optimizer, runtime["optimizer"]),
            scheduler=scheduler,
            strategy=cast(SingleDeviceStrategy, runtime["strategy"]),
            data_module=cast(DataModule, runtime["data"]),
            family_adapter=cast(Gr00tN1d6CheckpointAdapter, runtime["adapter"]),
            callbacks=cast(tuple[TrainingCallback, ...], runtime["callbacks"]),
            metric_logger=cast(MetricLogger, runtime["logger"]),
        )
    after = _snapshot(runtime)
    assert calls == 2
    _assert_nested_equal(before, after)


@requires_torch
def test_numpy_rng_uses_primitive_exact_uint32_keys_and_weights_only_round_trip(
    tmp_path: Path,
) -> None:
    """624 个 uint32 键经 pickle、对象边界和 weights-only 保存后精确恢复。"""
    before = capture_rng_state()
    keys = tuple((index * 2654435761) & 0xFFFFFFFF for index in range(624))
    keys = (0, 0xFFFFFFFF, *keys[2:])
    state = capture_rng_state()
    state["numpy"] = {
        "algorithm": "MT19937",
        "keys": keys,
        "position": 624,
        "has_gauss": 0,
        "cached_gaussian": 0.0,
    }
    try:
        validate_rng_state(state)
        pickled: object = pickle.loads(pickle.dumps(state))
        pickled_mapping = _string_mapping(pickled)
        pickled_numpy = _string_mapping(pickled_mapping["numpy"])
        assert pickled_numpy.get("keys") == keys
        path = tmp_path / "rng.pt"
        _torch_save(state, path)
        loaded_state = _string_mapping(_torch_load(path))
        validate_rng_state(loaded_state)
        restore_rng_state(loaded_state)
        restored = cast(
            tuple[str, NDArray[np.uint32], int, int, float],
            np.random.get_state(),
        )
        assert restored[0] == "MT19937"
        assert tuple(int(value) for value in restored[1]) == keys
        assert restored[1].dtype == np.dtype(np.uint32)
        assert restored[2:] == (624, 0, 0.0)
    finally:
        restore_rng_state(before)


@requires_torch
@pytest.mark.parametrize("bad_key", (-1, 0x1_0000_0000, True, 1.5))
def test_numpy_rng_rejects_non_uint32_primitive_before_apply(bad_key: object) -> None:
    """越界值、bool 和非整数在 RNG 应用前被严格拒绝。"""
    state = capture_rng_state()
    numpy_state = dict(cast(Mapping[str, object], state["numpy"]))
    raw_keys = numpy_state["keys"]
    if not _is_object_tuple(raw_keys):
        raise TypeError("numpy RNG keys must be a tuple")
    keys: list[object] = list(raw_keys)
    keys[17] = bad_key
    numpy_state["keys"] = tuple(keys)
    state["numpy"] = numpy_state
    with pytest.raises((TypeError, ValueError)):
        validate_rng_state(state)


@requires_torch
def test_fsdp2_checkpoint_boundary_fails_closed_outside_reviewed_torch_versions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """未审核 Torch 版本不得进入 FSDP2 DCP 运行时。"""

    strategy = FullyShardedDataParallelStrategy(
        PrecisionPolicy("bfloat16"),
        expected_world_size=2,
        module_filter=lambda name, module: bool(name and module),
    )
    monkeypatch.setattr(torch, "__version__", "2.7.0")
    with pytest.raises(
        RuntimeError,
        match="SOURCE_IMPLEMENTED/DISTRIBUTED_RUNTIME_NOT_EXECUTED",
    ):
        strategy.save_sharded_checkpoint(
            tmp_path / "dcp",
            torch.nn.Linear(2, 2),
            torch.optim.AdamW(torch.nn.Linear(2, 2).parameters()),
        )


@requires_torch
def test_fsdp2_selector_targets_production_blocks_and_forbids_full_state() -> None:
    """FSDP2 显式选择 Eagle/DiT block 且拒绝 rank-zero 完整状态。"""

    transformer_block = type("TransformerBlock", (), {})()
    qwen_block = type("Qwen3DecoderLayer", (), {})()
    unrelated = torch.nn.Linear(2, 2)
    from autovla.cli import train as train_cli

    module_filter: object = getattr(train_cli, "_gr00t_fsdp_module_filter", None)
    if not isinstance(module_filter, _ModuleFilter):
        raise TypeError("GR00T FSDP module filter must be callable")
    assert module_filter(
        "action_head.model.transformer_blocks.0",
        transformer_block,
    )
    assert module_filter(
        "backbone.model.language_model.model.layers.0",
        qwen_block,
    )
    assert not module_filter("action_head.conditioner", unrelated)

    strategy = FullyShardedDataParallelStrategy(
        PrecisionPolicy("bfloat16"),
        expected_world_size=2,
        module_filter=lambda name, module: bool(name and module),
    )
    model = torch.nn.Linear(2, 2)
    object.__setattr__(strategy, "_prepared_model", model)
    with pytest.raises(RuntimeError, match="distributed sharded checkpoint boundary"):
        strategy.model_state_dict(model)
    with pytest.raises(RuntimeError, match="distributed sharded checkpoint boundary"):
        strategy.optimizer_state_dict(torch.optim.AdamW(model.parameters()))
