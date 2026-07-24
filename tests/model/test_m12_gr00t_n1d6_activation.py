"""M12 GR00T N1.6 运行画像激活边界的轻量契约测试。"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, NoReturn, cast

import pytest

from autovla.models.assembly import ModelAssemblyRequest
from autovla.models.families.gr00t_n1d6 import factory as factory_module
from autovla.models.families.gr00t_n1d6.assets import Gr00tN1d6AssetBundle
from autovla.models.families.gr00t_n1d6.factory import Gr00tN1d6ModelFactory
from autovla.models.families.gr00t_n1d6.specification import GR00T_N1D6_SPEC
from autovla.runtime_profiles.contracts import (
    FamilyRuntimeProfile,
    RuntimeCompatibilityReport,
    RuntimeEnvironmentFingerprint,
)
from autovla.training.runtime import VerifiedTrainingRuntime

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


ROOT = Path(__file__).resolve().parents[2]
ORACLE_PATH = ROOT / "tests/model/oracles/gr00t_n1d6/activation_boundary.json"
FACTORY_PATH = ROOT / "autovla/models/families/gr00t_n1d6/factory.py"


def _verified_runtime(*, family_key: str = "gr00t_n1d6") -> VerifiedTrainingRuntime:
    """构造不访问文件或载荷的共享已验证运行画像。"""

    profile = FamilyRuntimeProfile(
        profile_id="gr00t_n1d6_runtime",
        family_key=family_key,
        kind="training_runtime",
        descriptor_path=Path("configs/env/profiles/model-gr00t-n1d6.yaml"),
        uv_project=Path("envs/model-gr00t-n1d6"),
        requested_python_version="3.10",
        lock_status="exact_locked_runtime_verified",
        lock_sha256="1" * 64,
        lock_accepted=True,
        exact_packages=(("torch", "2.7.1"),),
        observed_lock_packages=(("torch", "2.7.1"),),
        prohibited_packages=(),
        blockers=(),
        asset_license_gate_status="conditional_restrictive_research_terms",
        requires_cuda=True,
    )
    fingerprint = RuntimeEnvironmentFingerprint(
        schema_version="autovla.runtime_profile_fingerprint.v1",
        source_sha="2" * 40,
        profile_id=profile.profile_id,
        profile_descriptor_sha256="3" * 64,
        pyproject_sha256="4" * 64,
        uv_lock_sha256=profile.lock_sha256,
        requested_python_version="3.10",
        environment_path=f".autovla_envs/{profile.profile_id}",
        python_executable=f".autovla_envs/{profile.profile_id}/bin/python",
        python_version="3.10.14",
        python_implementation="CPython",
        platform="linux",
        observed_packages=(("torch", "2.7.1"),),
        installed_distribution_inventory_sha256="5" * 64,
        torch_compiled_cuda_version="12.4",
        cuda_runtime_version="12.4",
        cuda_driver_version="550",
        cudnn_version="9",
        nccl_version="2.21",
        gpu_name="A100",
        gpu_compute_capability="8.0",
        offline_flags=(("HF_HUB_OFFLINE", "1"),),
    )
    report = RuntimeCompatibilityReport(
        schema_version="autovla.runtime_compatibility_report.v1",
        profile_id=profile.profile_id,
        source_sha=fingerprint.source_sha,
        fingerprint=fingerprint,
        expected_versions=profile.exact_packages,
        observed_versions=fingerprint.observed_packages,
        path_isolation_checks=(("canonical_environment_path", True),),
        prohibited_dependency_checks=(),
        cuda_compatibility_checks=(("gpu_available", True),),
        asset_and_license_gate_status=profile.asset_license_gate_status,
        errors=(),
        warnings=(),
        status="pass",
    )
    return VerifiedTrainingRuntime(profile, report)


def _request(family_key: str = "gr00t_n1d6") -> ModelAssemblyRequest:
    """构造仅供前置门禁使用且不解引用载荷的请求替身。"""

    return cast(
        ModelAssemblyRequest,
        SimpleNamespace(
            family_key=family_key,
            asset_bundle=object.__new__(Gr00tN1d6AssetBundle),
        ),
    )


def test_runtime_bundle_requires_exact_shared_verified_runtime_before_assembly() -> None:
    """伪造画像在进入资产或模型构造前失败关闭。"""

    class _NoAssemblyFactory(Gr00tN1d6ModelFactory):
        """记录门禁错误时不应发生的模型装配。"""

        def __call__(self, request: ModelAssemblyRequest) -> NoReturn:
            """任何调用都表示运行画像门禁顺序回归。"""

            del request
            raise AssertionError("model assembly must not run before runtime verification")

    signature = inspect.signature(Gr00tN1d6ModelFactory.build_runtime_bundle)
    assert signature.parameters["verified_runtime"].kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError, match="shared VerifiedTrainingRuntime"):
        _NoAssemblyFactory().build_runtime_bundle(
            _request(),
            verified_runtime=cast(VerifiedTrainingRuntime, object()),
        )


def test_runtime_bundle_consumes_caller_verified_immutable_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    """家族不拥有 lock 摘要,只原样消费共享验证层身份。"""

    runtime = _verified_runtime()
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
        verified_runtime=runtime,
    )

    assert returned is captured
    assert captured["runtime_profile_identity"] == runtime.bundle_profile_identity
    assert captured["runtime_profile_identity"] == (
        "gr00t_n1d6_runtime@lock-sha256:" + "1" * 64
    )
    source = FACTORY_PATH.read_text(encoding="utf-8")
    assert "_RUNTIME_PROFILE_IDENTITY" not in source
    assert re.search(r"@lock-sha256:[0-9a-f]{64}", source) is None


def test_verified_runtime_family_mismatch_fails_before_assembly() -> None:
    """其他家族的已验证画像不能激活 N1.6 装配。"""

    class _NoAssemblyFactory(Gr00tN1d6ModelFactory):
        """记录家族漂移时不应发生的模型装配。"""

        def __call__(self, request: ModelAssemblyRequest) -> NoReturn:
            """任何调用都表示家族身份门禁顺序回归。"""

            del request
            raise AssertionError("model assembly must not run for a mismatched runtime")

    with pytest.raises(ValueError, match="profile family must match"):
        _NoAssemblyFactory().build_runtime_bundle(
            _request(),
            verified_runtime=_verified_runtime(family_key="gr00t_n1d7"),
        )


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
    assert oracle["runtime_profile_id"] == "gr00t_n1d6_runtime"
    assert oracle["runtime_identity_scheme"] == "lock-sha256"
    assert oracle["accepted_source_checkpoint_evidence"] == list(
        requirements.evidence.accepted_evidence
    )
    assert oracle["runtime_ready"] is False
    assert requirements.evidence.runtime_ready is False
    assert GR00T_N1D6_SPEC.runtime_ready is False


def test_activation_boundary_imports_without_model_runtime_dependencies() -> None:
    """导入家族工厂和规范不会加载 Torch、Transformers 或 safetensors。"""

    script = """
import sys
from autovla.models.families.gr00t_n1d6.factory import Gr00tN1d6ModelFactory
from autovla.models.families.gr00t_n1d6.specification import GR00T_N1D6_SPEC
assert Gr00tN1d6ModelFactory
assert GR00T_N1D6_SPEC.runtime_ready is False
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
