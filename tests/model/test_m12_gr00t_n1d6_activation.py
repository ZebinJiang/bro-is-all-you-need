"""M12 GR00T N1.6 运行画像激活边界的轻量契约测试。"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, NoReturn, cast

import pytest

from autovla.models.assembly import ModelAssemblyRequest
from autovla.models.capabilities import (
    CheckpointFormat,
    RuntimeSupportLevel,
)
from autovla.models.families.gr00t_n1d6 import factory as factory_module
from autovla.models.families.gr00t_n1d6.assets import Gr00tN1d6AssetBundle
from autovla.models.families.gr00t_n1d6.factory import Gr00tN1d6ModelFactory
from autovla.models.families.gr00t_n1d6.specification import GR00T_N1D6_SPEC
from autovla.models.families.specification import RuntimeSupportState

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


ROOT = Path(__file__).resolve().parents[2]
ORACLE_PATH = ROOT / "tests/model/oracles/gr00t_n1d6/activation_boundary.json"
FACTORY_PATH = ROOT / "autovla/models/families/gr00t_n1d6/factory.py"


def _request() -> ModelAssemblyRequest:
    """构造仅供前置门禁使用且不解引用载荷的请求替身。"""

    return cast(
        ModelAssemblyRequest,
        SimpleNamespace(
            family_key="gr00t_n1d6",
            asset_bundle=object.__new__(Gr00tN1d6AssetBundle),
        ),
    )


class _NoAssemblyFactory(Gr00tN1d6ModelFactory):
    """记录身份门禁错误时不应发生的模型装配。"""

    def __call__(self, request: ModelAssemblyRequest) -> NoReturn:
        """任何调用都表示运行画像身份门禁顺序回归。"""

        del request
        raise AssertionError("model assembly must not run before identity validation")


def test_model_factory_has_no_training_layer_dependency() -> None:
    """模型工厂不得导入或引用 Training 层运行类型。"""

    tree = ast.parse(FACTORY_PATH.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not any(name.startswith("autovla.training") for name in imported_modules)
    assert "VerifiedTrainingRuntime" not in referenced_names


def test_runtime_bundle_requires_keyword_only_exact_non_empty_string() -> None:
    """运行画像身份必须在装配前以精确非空字符串显式提供。"""

    signature = inspect.signature(Gr00tN1d6ModelFactory.build_runtime_bundle)
    parameter = signature.parameters["runtime_profile_identity"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.annotation == "str"

    with pytest.raises(TypeError, match="exact str"):
        _NoAssemblyFactory().build_runtime_bundle(
            _request(),
            runtime_profile_identity=cast(str, object()),
        )
    with pytest.raises(TypeError, match="exact str"):
        _NoAssemblyFactory().build_runtime_bundle(
            _request(),
            runtime_profile_identity=cast(str, type("_Identity", (str,), {})("verified")),
        )
    with pytest.raises(ValueError, match="must not be empty"):
        _NoAssemblyFactory().build_runtime_bundle(
            _request(),
            runtime_profile_identity="  ",
        )


def test_runtime_bundle_consumes_caller_verified_immutable_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    """家族不拥有 lock 摘要,只原样消费调用方验证的字符串身份。"""

    runtime_profile_identity = "caller-verified:gr00t_n1d6/runtime-profile/v1"
    result = SimpleNamespace(plan=SimpleNamespace(definition=GR00T_N1D6_SPEC))
    evidence = object()
    captured: dict[str, object] = {}

    def _assemble(
        self: Gr00tN1d6ModelFactory,
        request: ModelAssemblyRequest,
    ) -> object:
        """返回不含模型载荷的最小装配结果替身。"""

        del self, request
        return result

    def _capture_runtime_bundle(**values: object) -> object:
        """捕获传给共享运行包的数据而不构造模型对象。"""

        captured.update(values)
        return captured

    def _runtime_asset_evidence(bundle: Gr00tN1d6AssetBundle) -> object:
        """确认同一类型化资产包被投影为测试证据。"""

        assert isinstance(bundle, Gr00tN1d6AssetBundle)
        return evidence

    monkeypatch.setattr(Gr00tN1d6ModelFactory, "__call__", _assemble)
    monkeypatch.setattr(factory_module, "_asset_runtime_evidence", _runtime_asset_evidence)
    monkeypatch.setattr(factory_module, "ModelRuntimeBundle", _capture_runtime_bundle)

    returned = Gr00tN1d6ModelFactory().build_runtime_bundle(
        _request(),
        runtime_profile_identity=runtime_profile_identity,
    )

    assert returned is captured
    assert captured["runtime_profile_identity"] == runtime_profile_identity
    source = FACTORY_PATH.read_text(encoding="utf-8")
    assert "_RUNTIME_PROFILE_IDENTITY" not in source
    assert "lock-sha256" not in source


def test_c1_c2r7_evidence_remains_non_runtime_activation_evidence() -> None:
    """源码和 checkpoint 证据保持来源派生,不得提升 runtime_ready。"""

    oracle = cast(
        dict[str, object],
        json.loads(ORACLE_PATH.read_text(encoding="utf-8")),
    )
    requirements = GR00T_N1D6_SPEC.assembly_requirements
    assert requirements is not None
    assert oracle["schema_version"] == "autovla.gr00t_n1d6.activation_boundary_oracle.v1"
    assert oracle["family_key"] == GR00T_N1D6_SPEC.family_key
    assert oracle["runtime_profile_identity_contract"] == "caller_verified_exact_non_empty_str"
    assert oracle["accepted_source_checkpoint_evidence"] == list(
        requirements.evidence.accepted_evidence
    )
    assert oracle["runtime_ready"] is False
    assert requirements.evidence.runtime_ready is False
    assert GR00T_N1D6_SPEC.runtime_support is RuntimeSupportState.EXECUTABLE
    assert GR00T_N1D6_SPEC.runtime_supported is False
    assert requirements.runtime_level is RuntimeSupportLevel.ASSET_GATED
    assert GR00T_N1D6_SPEC.validation_status == (
        "c1_c2r7_checkpoint_validated_blocked_c3_data_runtime_unverified"
    )
    assert oracle["local_files_only"] is GR00T_N1D6_SPEC.local_files_only is True
    assert requirements.checkpoint.checkpoint_format is CheckpointFormat.SAFETENSORS
    assert oracle["checkpoint_format"] == requirements.checkpoint.checkpoint_format.value
    assert oracle["remote_code_allowed"] is False


def test_activation_boundary_imports_without_model_runtime_dependencies() -> None:
    """导入家族工厂和规范不会加载 Torch、Transformers 或 safetensors。"""

    script = """
import sys
from autovla.models.families.gr00t_n1d6.factory import Gr00tN1d6ModelFactory
from autovla.models.families.gr00t_n1d6.specification import GR00T_N1D6_SPEC
assert Gr00tN1d6ModelFactory
assert GR00T_N1D6_SPEC.runtime_supported is False
assert GR00T_N1D6_SPEC.assembly_requirements.evidence.runtime_ready is False
assert not any(
    name == 'autovla.training' or name.startswith('autovla.training.')
    for name in sys.modules
)
assert not {'torch', 'transformers', 'safetensors'} & set(sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
