"""M10 DeepSpeed/session 所有权回归检查。"""

import importlib
import json
import subprocess
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import pytest

from autovla.assets import ModelAssetBundle
from autovla.data.transforms import TransformPlan
from autovla.models.assembly import ModelAssemblyRequest, ModelRuntimeBundle
from autovla.models.capabilities import PrecisionSupport, TopologySupport
from autovla.runtime_profiles import (
    RuntimeEnvironmentError,
    RuntimeEnvironmentFingerprint,
    RuntimeEnvironmentManager,
    RuntimeEnvironmentSpec,
    load_runtime_profiles,
)


@dataclass(frozen=True, slots=True)
class _ConfigIdentity:
    """提供规范装配请求所需的最小模型配置身份。"""

    family_key: str = "gr00t_n1d6"
    fingerprint: str = "1" * 64


class _VerifiedBundle:
    """提供不访问磁盘的已验证资产包替身。"""

    family_key = "gr00t_n1d6"
    revision = "2" * 40
    root = Path("/verified/gr00t_n1d6")
    checkpoint_candidates: tuple[Path, ...] = ()
    tokenizer_or_processor_assets: tuple[Path, ...] = ()
    backbone_assets: tuple[Path, ...] = ()
    provenance: tuple[object, ...] = ()
    license_records: tuple[object, ...] = ()
    fingerprint = "3" * 64

    def __init__(self) -> None:
        """初始化独立的空验证清单和角色映射。"""
        self.manifest: dict[str, object] = {}
        self.assets_by_role: dict[str, object] = {}

    def validate(self) -> None:
        """确认测试资产根保持绝对路径。"""
        if not self.root.is_absolute():
            raise ValueError("test asset root must be absolute")


class _OneShotContextFactory:
    """记录初始化上下文请求和进入次数,并拒绝重复消费。"""

    identity = "test.strategy.zero3.v1"

    def __init__(self) -> None:
        """初始化一次性上下文计数。"""
        self.calls = 0
        self.entries = 0
        self.exits = 0

    def __call__(self) -> AbstractContextManager[None]:
        """返回只允许请求一次的测试上下文。"""
        self.calls += 1
        if self.calls != 1:
            raise RuntimeError("test initialization context requested more than once")

        @contextmanager
        def enter() -> Generator[None, None, None]:
            """记录 family 工厂拥有的唯一上下文进入。"""
            self.entries += 1
            try:
                yield
            finally:
                self.exits += 1

        return enter()


RuntimeBundle = ModelRuntimeBundle[object, object, object, object, object, object]


class ModelFactoryForTest(Protocol):
    """描述本测试消费的公共工厂行为,避免跨模块导入私有名称。"""

    def build_runtime_bundle(self, value: ModelAssemblyRequest, /) -> RuntimeBundle:
        """根据同一装配请求返回运行包。"""

        ...


class ModelFactoryInvoker(Protocol):
    """描述测试动态解析的生产模型工厂调用边界。"""

    def __call__(
        self,
        request: ModelAssemblyRequest,
        factory: ModelFactoryForTest,
        /,
    ) -> RuntimeBundle:
        """把规范请求交给模型工厂并返回已验证运行包。"""

        ...


class EnvironmentProbe(Protocol):
    """描述测试动态解析的绑定环境 probe。"""

    def __call__(
        self,
        spec: RuntimeEnvironmentSpec,
        /,
    ) -> tuple[RuntimeEnvironmentFingerprint, dict[str, object]]:
        """执行单次隔离环境 probe。"""

        ...


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


def test_zero3_initialization_is_family_owned_and_one_shot() -> None:
    """假工厂证明 CLI 传递同一请求且不重复进入一次性上下文。"""

    source = Path("autovla/training/strategy/deepspeed.py").read_text(encoding="utf-8")
    assert "class _ZeroInitializationContext" in source
    assert "initialization context may be requested once" in source
    assert "model must be built inside model_initialization_context" in source
    assert "PartitionedModelConstruction" not in source

    context_factory = _OneShotContextFactory()
    request = ModelAssemblyRequest(
        family_key="gr00t_n1d6",
        config=_ConfigIdentity(),
        asset_bundle=cast(ModelAssetBundle, _VerifiedBundle()),
        transform_plan=TransformPlan(),
        precision=PrecisionSupport.BFLOAT16,
        topology=TopologySupport.DEEPSPEED_ZERO_3,
        local_files_only=True,
        initialization_context_factory=context_factory,
    )
    result = cast(RuntimeBundle, object.__new__(ModelRuntimeBundle))
    received: list[ModelAssemblyRequest] = []

    class FakeFactory:
        """模拟由 family 独占初始化上下文的模型工厂。"""

        def build_runtime_bundle(self, value: ModelAssemblyRequest, /) -> RuntimeBundle:
            """记录请求并在请求携带的上下文中模拟唯一运行包构造。"""
            received.append(value)
            with value.initialization_context_factory():
                pass
            return result

    train_module = importlib.import_module("autovla.cli.train")
    factory_boundary_name = "_invoke_model_factory"
    raw_invoker = cast(object, getattr(train_module, factory_boundary_name))
    assert callable(raw_invoker)
    actual = cast(ModelFactoryInvoker, raw_invoker)(request, FakeFactory())

    assert actual is result
    assert received == [request]
    assert context_factory.calls == 1
    assert context_factory.entries == 1
    assert context_factory.exits == 1


def test_zero3_official_checkpoint_boundary_fails_before_family_loader() -> None:
    """ZeRO-3 在 engine 前拒绝 whole-module loader, ZeRO-2 保持原严格路径。"""

    from autovla.training.session import StrategyInitializationContextFactory, TrainingStrategy

    source = Path("autovla/training/strategy/deepspeed.py").read_text(encoding="utf-8")
    strategy_start = source.index("class DeepSpeedStrategy")
    boundary_start = source.index("def load_official_checkpoint", strategy_start)
    boundary_end = source.index("def prepare", boundary_start)
    boundary_source = source[boundary_start:boundary_end]
    assert "if self._deepspeed_config.zero_stage == 3" in boundary_source
    assert boundary_source.index("raise RuntimeError(") < boundary_source.index("return loader()")

    calls: list[str] = []

    def loader() -> str:
        """记录 family loader 是否真正被调用。"""

        calls.append("loaded")
        return "evidence"

    class FakeStrategy:
        """模拟由 strategy 拥有的 checkpoint 决策,不导入 Torch。"""

        name = "fake_partitioned"
        topology = object()

        def configure_process_environment(self) -> None:
            """测试无需配置设备。"""

        def model_initialization_context(self) -> AbstractContextManager[None]:
            """返回无副作用上下文。"""

            @contextmanager
            def enter() -> Generator[None, None, None]:
                """提供协议要求的上下文。"""

                yield

            return enter()

        def prepare(self, **_: object) -> object:
            """提供运行时协议要求的方法名。"""

            return object()

        def load_official_checkpoint(
            self,
            model: object,
            callback: object,
            /,
        ) -> object:
            """在 callback 调用前模拟 ZeRO-3 失败关闭。"""

            del model, callback
            raise RuntimeError("whole-module state_dict loading is forbidden")

    strategy = cast(TrainingStrategy, FakeStrategy())
    boundary = StrategyInitializationContextFactory(strategy)
    with pytest.raises(RuntimeError, match="whole-module state_dict loading is forbidden"):
        boundary.load_official_checkpoint(object(), loader)
    assert calls == []


def test_official_family_factories_use_one_strategy_load_boundary() -> None:
    """三个可执行 family 均经规范请求加载, 不直接拥有策略分支。"""

    paths = (
        Path("autovla/models/families/gr00t_n1d6/factory.py"),
        Path("autovla/models/families/gr00t_n1d7/factory.py"),
        Path("autovla/models/families/pi0_5/factory.py"),
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "request.load_official_checkpoint(" in source


def test_runtime_probe_rejects_non_text_optional_fields() -> None:
    """环境 probe 的可选文本字段不得接受数字、容器或隐式字符串化。"""

    root = Path(__file__).resolve().parents[2]
    profile = load_runtime_profiles(root)["gr00t_n1d6_runtime"]
    spec = RuntimeEnvironmentSpec.for_profile(root, profile)
    payload: dict[str, object] = {"packages": {}}

    def fake_runner(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        """返回当前测试设置的不可信 JSON probe 载荷。"""

        return subprocess.CompletedProcess(
            ["python"],
            0,
            stdout=json.dumps(payload),
            stderr="",
        )

    manager = RuntimeEnvironmentManager(root, source_sha="f" * 40, runner=fake_runner)
    probe_boundary_name = "_probe_environment"
    raw_probe = cast(object, getattr(manager, probe_boundary_name))
    assert callable(raw_probe)
    probe = cast(EnvironmentProbe, raw_probe)
    optional_fields = (
        "torch_compiled_cuda_version",
        "cuda_runtime_version",
        "cuda_driver_version",
        "cudnn_version",
        "nccl_version",
        "gpu_name",
        "gpu_compute_capability",
    )
    for field in optional_fields:
        payload.clear()
        payload.update({"packages": {}, field: 7})
        try:
            probe(spec)
        except RuntimeEnvironmentError as exc:
            assert exc.code == "ENVIRONMENT_PROBE_INVALID"
            assert field in exc.message
        else:
            raise AssertionError(f"malformed probe field {field!r} must fail closed")
