"""M10 DeepSpeed/session 所有权回归检查。"""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from autovla.assets import ModelAssetBundle
from autovla.cli.train import _invoke_model_factory, _ModelFactory
from autovla.data.transforms import TransformPlan
from autovla.models.assembly import ModelAssemblyRequest, ModelAssemblyResult
from autovla.models.capabilities import PrecisionSupport, TopologySupport


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
        def enter() -> Iterator[None]:
            """记录 family 工厂拥有的唯一上下文进入。"""
            self.entries += 1
            try:
                yield
            finally:
                self.exits += 1

        return enter()


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
    result = object.__new__(ModelAssemblyResult)
    received: list[ModelAssemblyRequest] = []

    class FakeFactory:
        """模拟由 family 独占初始化上下文的模型工厂。"""

        def __call__(self, value: ModelAssemblyRequest, /) -> ModelAssemblyResult:
            """记录请求并在请求携带的上下文中模拟分配。"""
            received.append(value)
            with value.initialization_context_factory():
                pass
            return result

    actual = _invoke_model_factory(request, cast(_ModelFactory, FakeFactory()))

    assert actual is result
    assert received == [request]
    assert context_factory.calls == 1
    assert context_factory.entries == 1
    assert context_factory.exits == 1
