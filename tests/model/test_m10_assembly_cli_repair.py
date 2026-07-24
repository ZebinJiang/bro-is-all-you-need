"""M10 assembly、家族组合和 CLI 修复的聚焦回归测试。"""

from __future__ import annotations

import ast
import importlib.util
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import SimpleNamespace
from typing import Generator, Protocol, cast

import pytest

from autovla.assets import ModelAssetBundle
from autovla.core.registry import OptionalDependencyError
from autovla.data.transforms import TransformPlan
from autovla.models.assembly import ModelAssemblyRequest, resolve_model_assembly
from autovla.models.capabilities import PrecisionSupport, TopologySupport


@dataclass(frozen=True, slots=True)
class _ConfigIdentity:
    """提供解析 assembly 依赖所需的最小配置身份。"""

    family_key: str = "gr00t_n1d6"
    fingerprint: str = "1" * 64


class _VerifiedBundle:
    """提供不访问磁盘的已验证资产协议替身。"""

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
        """初始化空清单和角色映射。"""

        self.manifest: dict[str, object] = {}
        self.assets_by_role: dict[str, object] = {}

    def validate(self) -> None:
        """确认测试根保持绝对路径。"""

        if not self.root.is_absolute():
            raise ValueError("test asset root must be absolute")


class _EagleConfigLike(Protocol):
    """描述测试替身需要的 Eagle 几何字段。"""

    @property
    def visual_tokens_per_image(self) -> int:
        """返回视觉 token 数。"""

        ...


def _request() -> ModelAssemblyRequest:
    """构造不导入模型运行时的规范装配请求。"""

    return ModelAssemblyRequest(
        family_key="gr00t_n1d6",
        config=_ConfigIdentity(),
        asset_bundle=cast(ModelAssetBundle, _VerifiedBundle()),
        transform_plan=TransformPlan(),
        precision=PrecisionSupport.BFLOAT16,
        topology=TopologySupport.SINGLE_GPU,
    )


def test_assembly_dependencies_are_component_and_operation_granular() -> None:
    """元数据、资产与索引工厂不继承参数分配的 CUDA 扩展依赖。"""

    factories = resolve_model_assembly(_request()).factories
    assert "flash_attn" not in factories.processor.required_modules
    assert factories.checkpoint.required_modules == ()
    assert factories.asset_bundle is not None
    assert factories.asset_bundle.required_modules == ()
    assert "flash_attn" in factories.backbone.required_modules
    assert "flash_attn" in factories.action_head.required_modules
    assert "flash_attn" in factories.model.required_modules


def test_missing_cuda_extension_does_not_block_checkpoint_index_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缺失 CUDA 扩展只阻断参数分配,不阻断 checkpoint 索引适配器。"""

    real_find_spec = importlib.util.find_spec

    def missing_flash_attention(
        name: str,
        package: str | None = None,
    ) -> ModuleSpec | None:
        """仅模拟 flash-attn 缺失并保留其他模块发现。"""

        if name == "flash_attn":
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", missing_flash_attention)
    factories = resolve_model_assembly(_request()).factories
    assert callable(factories.checkpoint.load())
    with pytest.raises(OptionalDependencyError, match="flash_attn"):
        factories.model.load()


def test_cli_uses_typed_family_adapter_without_n1d6_branch() -> None:
    """生产 CLI 只依赖共享适配器,不包含 N1.6 特判或直建。"""

    source = Path("autovla/cli/train.py").read_text(encoding="utf-8")
    assert "TrainingAssemblyAdapter" in source
    assert "registry_key !=" not in source
    assert "gr00t_n1d6" not in source
    assert "Gr00tN1d6" not in source


def test_non_executable_family_fails_before_training_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N1.7 生命周期门在训练依赖和 CUDA 环境配置前关闭。"""

    from autovla.cli import train
    from autovla.config import ExperimentConfig
    from autovla.config.schema.model import ModelConfig
    from autovla.config.schema.run import RunConfig

    config = ExperimentConfig(
        run=RunConfig(intent="training"),
        model=ModelConfig(
            name="NVIDIA Isaac-GR00T N1.7",
            registry_key="gr00t_n1d7",
            runtime_support="asset_required",
            validation_status="checkpoint_terms_and_cosmos_license_access_receipts_blocked",
        ),
    )

    def unexpected_dependency_check() -> None:
        """若生命周期门顺序回退则立即失败。"""

        raise AssertionError("training dependency check ran before lifecycle gate")

    monkeypatch.setattr(train, "_require_training_extra", unexpected_dependency_check)
    with pytest.raises(ValueError, match="runtime is fail-closed: asset_required"):
        train.compose_training_engine(config)


def test_full_model_builder_has_one_initialization_context_owner() -> None:
    """完整模型构造只进入一次上下文并在其中完成全部组件组合。"""

    tree = ast.parse(
        Path("autovla/models/families/gr00t_n1d6/factory.py").read_text(encoding="utf-8")
    )
    factory = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Gr00tN1d6ModelFactory"
    )
    call = next(
        node
        for node in factory.body
        if isinstance(node, ast.FunctionDef) and node.name == "__call__"
    )
    contexts = [node for node in ast.walk(call) if isinstance(node, ast.With)]
    assert len(contexts) == 1
    called_methods = {
        node.func.attr
        for node in ast.walk(contexts[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"_build_backbone", "_build_action_head", "_build_processor"} <= called_methods


class _OneShotContextFactory:
    """记录共享组件 builder 的初始化上下文消费次数。"""

    identity = "test.zero3.one-shot"

    def __init__(self) -> None:
        """初始化调用与进入计数。"""

        self.calls = 0
        self.entries = 0

    def __call__(self) -> AbstractContextManager[None]:
        """返回仅允许创建一次的上下文。"""

        self.calls += 1
        if self.calls != 1:
            raise RuntimeError("initialization context requested more than once")

        @contextmanager
        def _enter() -> Generator[None, None, None]:
            """记录唯一进入。"""

            self.entries += 1
            yield

        return _enter()


def test_registered_backbone_path_delegates_to_one_shot_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """注册 backbone 路径复用同一 builder 并只消费一次初始化上下文。"""

    from autovla.models.families.gr00t_n1d6.assets import Gr00tN1d6AssetBundle
    from autovla.models.families.gr00t_n1d6.config import Gr00tN1d6Config
    from autovla.models.families.gr00t_n1d6.factory import (
        Gr00tN1d6ModelFactory,
        _Gr00tN1d6BackboneFactory,
    )

    bundle = object.__new__(Gr00tN1d6AssetBundle)
    object.__setattr__(bundle, "base_checkpoint", SimpleNamespace(root=Path("/base")))
    object.__setattr__(bundle, "eagle_support", SimpleNamespace(root=Path("/eagle")))
    context = _OneShotContextFactory()
    request = object.__new__(ModelAssemblyRequest)
    object.__setattr__(request, "family_key", "gr00t_n1d6")
    object.__setattr__(request, "config", Gr00tN1d6Config())
    object.__setattr__(request, "asset_bundle", bundle)
    object.__setattr__(request, "initialization_context_factory", context)
    sentinel = object()

    def fake_load_eagle_config(
        path: str | Path,
        *,
        family_image_size: int | None,
    ) -> _EagleConfigLike:
        """返回不读取磁盘的 Eagle 配置替身。"""

        del path, family_image_size
        return cast(_EagleConfigLike, SimpleNamespace(visual_tokens_per_image=256))

    def no_parameter_dependencies(cls: type[Gr00tN1d6ModelFactory]) -> None:
        """避免测试访问可选模型依赖。"""

        del cls

    def fake_build_backbone(
        config: Gr00tN1d6Config,
        eagle_config: _EagleConfigLike,
    ) -> object:
        """回显稳定对象以隔离真实参数分配。"""

        del config, eagle_config
        return sentinel

    monkeypatch.setattr(
        "autovla.models.families.gr00t_n1d6.factory._load_eagle_config",
        fake_load_eagle_config,
    )
    monkeypatch.setattr(
        Gr00tN1d6ModelFactory,
        "_require_parameter_dependencies",
        classmethod(no_parameter_dependencies),
    )
    monkeypatch.setattr(
        Gr00tN1d6ModelFactory,
        "_build_backbone",
        staticmethod(fake_build_backbone),
    )

    assert _Gr00tN1d6BackboneFactory()(request) is sentinel
    assert context.calls == 1
    assert context.entries == 1
