"""M11 训练运行包、画像门禁和副作用顺序测试。"""

from pathlib import Path

import pytest

from autovla.runtime_profiles.contracts import (
    FamilyRuntimeProfile,
    RuntimeCompatibilityReport,
    RuntimeDiagnostic,
    RuntimeEnvironmentFingerprint,
)
from autovla.runtime_profiles.errors import RuntimeEnvironmentError
from autovla.training.runtime import VerifiedTrainingRuntime


def _profile(*, blocked: bool = False) -> FamilyRuntimeProfile:
    """构造不访问文件系统的训练画像。"""

    return FamilyRuntimeProfile(
        profile_id="gr00t_n1d6_runtime",
        family_key="gr00t_n1d6",
        kind="training_runtime",
        descriptor_path=Path("configs/env/profiles/model-gr00t-n1d6.yaml"),
        uv_project=Path("envs/model-gr00t-n1d6"),
        requested_python_version="3.10",
        lock_status="exact_locked_runtime_unverified",
        lock_sha256="1" * 64,
        exact_packages=(("torch", "2.6.0"),),
        prohibited_packages=(),
        blockers=("license unresolved",) if blocked else (),
        asset_license_gate_status=(
            "blocked_license" if blocked else "conditional_restrictive_research_terms"
        ),
        requires_cuda=True,
    )


def _report(
    profile: FamilyRuntimeProfile,
    *,
    realized: bool = True,
    compatible: bool = True,
) -> RuntimeCompatibilityReport:
    """构造已实现或失败关闭的兼容报告。"""

    fingerprint = RuntimeEnvironmentFingerprint(
        schema_version="autovla.runtime_profile_fingerprint.v1",
        source_sha="2" * 40,
        profile_id=profile.profile_id,
        profile_descriptor_sha256="3" * 64,
        pyproject_sha256="4" * 64,
        uv_lock_sha256=profile.lock_sha256,
        requested_python_version="3.10",
        environment_path=f".autovla_envs/{profile.profile_id}",
        python_executable=(f".autovla_envs/{profile.profile_id}/bin/python" if realized else None),
        python_version="3.10.14" if realized else None,
        python_implementation="CPython" if realized else None,
        platform="linux" if realized else None,
        observed_packages=(("torch", "2.6.0"),) if realized else (),
        installed_distribution_inventory_sha256="5" * 64 if realized else None,
        torch_compiled_cuda_version="12.4" if realized else None,
        cuda_runtime_version="12.4" if realized else None,
        cuda_driver_version="550" if realized else None,
        cudnn_version="9" if realized else None,
        nccl_version="2.21" if realized else None,
        gpu_name="A100" if realized else None,
        gpu_compute_capability="8.0" if realized else None,
        offline_flags=(("HF_HUB_OFFLINE", "1"),),
    )
    errors = () if compatible else (RuntimeDiagnostic("VERSION_MISMATCH", "torch"),)
    return RuntimeCompatibilityReport(
        schema_version="autovla.runtime_compatibility_report.v1",
        profile_id=profile.profile_id,
        source_sha=fingerprint.source_sha,
        fingerprint=fingerprint,
        expected_versions=profile.exact_packages,
        observed_versions=fingerprint.observed_packages,
        path_isolation_checks=(("canonical_environment_path", True),),
        prohibited_dependency_checks=(),
        cuda_compatibility_checks=(("gpu_available", realized),),
        asset_and_license_gate_status=profile.asset_license_gate_status,
        errors=errors,
        warnings=(),
        status="pass" if compatible else "fail",
    )


def test_training_runtime_requires_realized_compatible_cuda_profile() -> None:
    """兼容且已实现的 CUDA 画像产生规范 bundle 身份。"""

    profile = _profile()
    runtime = VerifiedTrainingRuntime(profile, _report(profile))

    assert runtime.bundle_profile_identity == ("gr00t_n1d6_runtime@lock-sha256:" + "1" * 64)


@pytest.mark.parametrize(
    ("realized", "compatible", "code"),
    (
        (False, True, "ENVIRONMENT_NOT_REALIZED"),
        (True, False, "ENVIRONMENT_INCOMPATIBLE"),
    ),
)
def test_training_runtime_fails_closed_before_composition(
    realized: bool,
    compatible: bool,
    code: str,
) -> None:
    """未实现或不兼容画像不能形成训练运行身份。"""

    profile = _profile()
    with pytest.raises(RuntimeEnvironmentError, match=code):
        VerifiedTrainingRuntime(
            profile,
            _report(profile, realized=realized, compatible=compatible),
        )


def test_training_runtime_rejects_unresolved_license_gate() -> None:
    """许可或资产 blocker 必须在环境兼容性之前失败关闭。"""

    profile = _profile(blocked=True)
    with pytest.raises(RuntimeEnvironmentError, match="PROFILE_BLOCKED"):
        VerifiedTrainingRuntime(profile, _report(profile))


def test_composition_root_orders_all_gates_before_heavy_side_effects() -> None:
    """源码顺序保证 C3、画像和运行包身份先于 CUDA、模型和数据。"""

    source = Path("autovla/cli/train.py").read_text(encoding="utf-8")
    asset_gate = source.index("if not asset_status.runtime_authorized")
    profile_gate = source.index("resolve_verified_training_runtime(", asset_gate)
    training_extra = source.index("_require_training_extra()", profile_gate)
    cuda_setup = source.index("strategy.configure_process_environment()", training_extra)
    runtime_bundle = source.index("_invoke_model_factory(", cuda_setup)
    data_module = source.index("data_factory.create(config.data)", runtime_bundle)

    assert asset_gate < profile_gate < training_extra < cuda_setup < runtime_bundle < data_module
    assert "TrainingRuntimeIdentity.from_bundle" in source
    assert '"model_runtime_identity": runtime_identity.to_dict()' in source
