"""M11 家族隔离运行时画像的确定性契约测试。"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from autovla.runtime_profiles import (
    EXPECTED_PROFILE_IDS,
    CudaCompatibilityIntent,
    LegacyRuntimeProfileAdapter,
    ResolvedPackage,
    ResolvedRuntimeLock,
    RuntimeEnvironmentError,
    RuntimeEnvironmentManager,
    RuntimeEnvironmentReceipt,
    RuntimeEnvironmentSpec,
    RuntimeProfileSpec,
    canonical_report_json,
    load_runtime_profiles,
)
from autovla.runtime_profiles.legacy import parse_simple_yaml

ROOT = Path(__file__).resolve().parents[2]


def _conversion_lock(
    profile: RuntimeProfileSpec,
    lock_sha256: str,
) -> ResolvedRuntimeLock:
    """构造测试专用转换 lock,不写入 tracked lock。"""

    return ResolvedRuntimeLock(
        schema_version="autovla.resolved_runtime_lock.v2",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        python_version=profile.requested_python_version,
        python_implementation=profile.python_implementation,
        platform_intent=profile.platform_intent,
        resolver_name="uv",
        resolver_version="0.8.1",
        upstream_revision="1" * 40,
        lock_sha256=lock_sha256,
        packages=(ResolvedPackage("jax", "0.4.1", ()),),
        cuda_compatibility=CudaCompatibilityIntent(
            schema_version="autovla.cuda_compatibility_intent.v1",
            required=False,
            torch_compiled_cuda_version=None,
            cuda_runtime_version=None,
            cuda_driver_version=None,
            cudnn_version=None,
            nccl_version=None,
            compute_capabilities=(),
        ),
    )


def _conversion_probe(command: list[str]) -> subprocess.CompletedProcess[str]:
    """返回与测试转换 lock 完全一致的解释器探测结果。"""

    payload = {
        "python_version": "3.10.14",
        "python_implementation": "CPython",
        "platform": "linux-x86_64",
        "packages": {"jax": "0.4.1"},
        "inventory_sha256": "2" * 64,
        "torch_compiled_cuda_version": None,
        "cuda_runtime_version": None,
        "cuda_driver_version": None,
        "cudnn_version": None,
        "nccl_version": None,
        "gpu_name": None,
        "gpu_compute_capability": None,
        "deepspeed_compatible": None,
        "sys_executable": command[0],
        "sys_prefix": str(Path(command[0]).parent.parent),
    }
    return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")


def _conversion_environment(
    profile: RuntimeProfileSpec,
    lock: ResolvedRuntimeLock,
    *,
    source_sha: str,
) -> RuntimeEnvironmentReceipt:
    """构造转换命令前置门使用的通过环境收据。"""

    return RuntimeEnvironmentReceipt(
        schema_version="autovla.runtime_environment_receipt.v1",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        lock_fingerprint=lock.fingerprint,
        source_sha=source_sha,
        environment_path=f".autovla_envs/{profile.profile_id}",
        installed_packages=(("jax", "0.4.1"),),
        python_implementation="CPython",
        python_version="3.10.14",
        platform="linux-x86_64",
        torch_version=None,
        torch_compiled_cuda_version=None,
        cuda_runtime_version=None,
        cuda_driver_version=None,
        cudnn_version=None,
        nccl_version=None,
        gpu_name=None,
        gpu_compute_capability=None,
        deepspeed_compatible=None,
        offline_flags=(
            ("HF_HUB_OFFLINE", "1"),
            ("PIP_NO_INDEX", "1"),
            ("UV_OFFLINE", "1"),
        ),
        verification_status="pass",
        diagnostics=(),
    )


class _CommandRunner(Protocol):
    """描述运行时管理器在测试中调用命令执行器的最小接口。"""

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        text: bool,
        capture_output: bool = ...,
    ) -> subprocess.CompletedProcess[str]:
        """执行命令并返回文本模式完成结果。"""

        ...


def _checkout_string_list(checkout: dict[str, object], key: str) -> list[str]:
    """验证旧 checkout 镜像字段为字符串列表并返回窄类型。"""

    value = checkout[key]
    assert isinstance(value, list)
    items = cast("list[object]", value)
    assert all(isinstance(item, str) for item in items)
    return cast("list[str]", items)


def test_profile_registry_is_exact_and_uses_canonical_environment_root() -> None:
    """画像身份闭集与环境路径必须完全匹配 M11 合同。"""

    profiles = load_runtime_profiles(ROOT)
    assert tuple(sorted(profiles)) == tuple(sorted(EXPECTED_PROFILE_IDS))
    for profile in profiles.values():
        spec = RuntimeEnvironmentSpec.for_profile(ROOT, profile)
        spec.validate()
        assert spec.environment_root == ROOT / ".autovla_envs"
        assert spec.environment_path == ROOT / ".autovla_envs" / profile.profile_id


def test_packaged_runtime_truth_matches_legacy_checkout_mirrors() -> None:
    """旧 checkout 描述中的 M11 字段必须与包内权威记录完全一致。"""

    filenames = {
        "gr00t_n1d6_runtime": "model-gr00t-n1d6.yaml",
        "gr00t_n1d7_runtime": "model-gr00t-n1d7.yaml",
        "pi0_5_runtime": "model-pi0-5.yaml",
        "pi0_5_conversion": "pi0-5-conversion.yaml",
    }
    for profile_id, profile in load_runtime_profiles().items():
        checkout = parse_simple_yaml(ROOT / "configs/env/profiles" / filenames[profile_id])
        assert checkout["runtime_profile_id"] == profile.profile_id
        assert checkout["runtime_family_key"] == profile.family_key
        assert checkout["runtime_profile_kind"] == profile.kind
        assert checkout["uv_project"] == profile.uv_project.as_posix()
        assert checkout["python_version"] == profile.requested_python_version
        assert checkout["runtime_lock_status"] == profile.lock_status
        assert checkout["runtime_lock_sha256"] == (profile.lock_sha256 or "unresolved")
        assert checkout["runtime_lock_accepted"] is profile.lock_accepted
        assert sorted(_checkout_string_list(checkout, "exact_packages")) == sorted(
            f"{name}=={version}" for name, version in profile.exact_packages
        )
        assert sorted(_checkout_string_list(checkout, "observed_lock_packages")) == sorted(
            f"{name}=={version}" for name, version in profile.observed_lock_packages
        )
        assert sorted(_checkout_string_list(checkout, "prohibited_packages")) == sorted(
            profile.prohibited_packages
        )
        assert checkout["runtime_blockers"] == list(profile.blockers)
        assert checkout["asset_license_gate_status"] == profile.asset_license_gate_status
        assert checkout["requires_cuda"] is profile.requires_cuda


def test_n1d6_preserved_lock_is_rejected_against_m11_package_contract() -> None:
    """历史 N1.6 lock 保留可审计摘要,但不得冒充 M11 接受 lock。"""

    profiles = load_runtime_profiles(ROOT)
    n1d6 = profiles["gr00t_n1d6_runtime"]
    assert n1d6.lock_sha256 == ("41f807307ba96a00313b4e7af1bb584db5df42dfbe877eca09082dab60f5d662")
    assert n1d6.lock_accepted is False
    assert dict(n1d6.exact_packages) == {
        "deepspeed": "0.19.2",
        "torch": "2.7.1",
    }
    assert dict(n1d6.observed_lock_packages) == {
        "numpy": "2.2.6",
        "safetensors": "0.5.3",
        "torch": "2.6.0",
        "torchvision": "0.21.0",
        "transformers": "4.51.3",
        "webdataset": "1.0.2",
    }
    assert "deepspeed" not in dict(n1d6.observed_lock_packages)
    lock = tomllib.loads((ROOT / "envs/model-gr00t-n1d6/uv.lock").read_text(encoding="utf-8"))
    assert "deepspeed" not in {package["name"] for package in lock["package"]}
    assert any("torch 2.6.0" in blocker for blocker in n1d6.blockers)
    assert any("deepspeed" in blocker.lower() for blocker in n1d6.blockers)
    for profile_id in ("gr00t_n1d7_runtime", "pi0_5_runtime", "pi0_5_conversion"):
        profile = profiles[profile_id]
        assert profile.lock_sha256 is None
        assert profile.lock_accepted is False
        assert profile.exact_packages == ()
        assert profile.observed_lock_packages == ()
        assert profile.blockers
        assert not (ROOT / profile.uv_project / "uv.lock").exists()


def test_pi_runtime_rejects_jax_flax_orbax_and_conversion_is_not_training() -> None:
    """生产 Pi0.5 与转换依赖隔离,转换画像不得冒充训练画像。"""

    profiles = load_runtime_profiles(ROOT)
    runtime = profiles["pi0_5_runtime"]
    conversion = profiles["pi0_5_conversion"]
    assert {"jax", "flax", "orbax", "orbax-checkpoint"} <= set(runtime.prohibited_packages)
    assert runtime.is_training_runtime is True
    assert conversion.is_training_runtime is False
    assert conversion.kind == "conversion"


def test_unresolved_projects_are_explicit_non_install_manifests() -> None:
    """未解析项目保留空依赖与 blocker,不制造可接受 lock。"""

    for project in (
        ROOT / "envs/model-gr00t-n1d7/pyproject.toml",
        ROOT / "envs/model-pi0-5/pyproject.toml",
        ROOT / "envs/model-pi0-5-conversion/pyproject.toml",
    ):
        text = project.read_text(encoding="utf-8")
        assert 'requires-python = "==3.10.*"' in text
        assert "dependencies = []" in text
        assert "blocked-unresolved-exact-versions" in text
        assert not project.with_name("uv.lock").exists()


def test_create_requires_authorization_and_unresolved_profiles_fail_closed() -> None:
    """create 无显式授权或无精确 lock 时不得调用 uv。"""

    calls: list[object] = []

    def forbidden_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        """记录意外 runner 调用并立即使测试失败。"""

        calls.append((args, kwargs))
        raise AssertionError("runner must not be called")

    manager = RuntimeEnvironmentManager(ROOT, source_sha="a" * 40, runner=forbidden_runner)
    unauthorized_lock = _conversion_lock(
        manager.profiles["gr00t_n1d6_runtime"],
        "1" * 64,
    )
    with pytest.raises(RuntimeEnvironmentError) as unauthorized:
        manager.create(
            "gr00t_n1d6_runtime",
            unauthorized_lock,
            nonce="fixture-unauthorized",
        )
    assert unauthorized.value.code == "ENVIRONMENT_CREATE_NOT_AUTHORIZED"
    unresolved_lock = _conversion_lock(
        manager.profiles["gr00t_n1d7_runtime"],
        "2" * 64,
    )
    with pytest.raises(RuntimeEnvironmentError) as unresolved:
        manager.create(
            "gr00t_n1d7_runtime",
            unresolved_lock,
            nonce="fixture-unresolved",
            allow_create=True,
        )
    assert unresolved.value.code == "RUNTIME_LOCK_FILE_MISSING"
    assert calls == []


def _copy_profile_fixture(destination: Path) -> None:
    """复制最小画像/项目 fixture,不复制环境或运行产物。"""

    profile_dir = destination / "configs/env/profiles"
    profile_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "pyproject.toml", destination / "pyproject.toml")
    for name in (
        "model-gr00t-n1d6.yaml",
        "model-gr00t-n1d7.yaml",
        "model-pi0-5.yaml",
        "pi0-5-conversion.yaml",
    ):
        shutil.copy2(ROOT / "configs/env/profiles" / name, profile_dir / name)
    for name in (
        "model-gr00t-n1d6",
        "model-gr00t-n1d7",
        "model-pi0-5",
        "model-pi0-5-conversion",
    ):
        source = ROOT / "envs" / name
        target = destination / "envs" / name
        target.mkdir(parents=True)
        shutil.copy2(source / "pyproject.toml", target / "pyproject.toml")
    shutil.copy2(
        ROOT / "envs/model-gr00t-n1d6/uv.lock",
        destination / "envs/model-gr00t-n1d6/uv.lock",
    )


def _accepted_fixture_manager(
    destination: Path,
    runner: _CommandRunner,
) -> tuple[RuntimeEnvironmentManager, ResolvedRuntimeLock]:
    """构造只供事务生命周期测试使用的显式转换 lock fixture。"""

    _copy_profile_fixture(destination)
    lock_path = destination / "envs/model-pi0-5-conversion/uv.lock"
    lock_path.write_text("fixture-lock\n", encoding="utf-8")
    manager = RuntimeEnvironmentManager(
        destination,
        source_sha="e" * 40,
        runner=runner,
    )
    profile = manager.profiles["pi0_5_conversion"]
    lock = _conversion_lock(
        profile,
        hashlib.sha256(lock_path.read_bytes()).hexdigest(),
    )
    return manager, lock


@pytest.mark.parametrize("failure_mode", ["nonzero", "oserror", "missing_interpreter"])
def test_failed_create_is_transactional_and_retryable(
    tmp_path: Path,
    failure_mode: str,
) -> None:
    """uv 失败或解释器缺失不得占用 canonical target,随后可直接重试。"""

    state = {"fail": True}

    def transactional_create_runner(
        command: list[str],
        *,
        env: dict[str, str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        """先模拟指定失败,再在同一 manager 上成功实现 staging。"""

        if command[0] != "uv":
            return _conversion_probe(command)
        if state["fail"] and failure_mode == "oserror":
            raise FileNotFoundError("uv")
        environment_path = Path(env["UV_PROJECT_ENVIRONMENT"])
        if not state["fail"] or failure_mode != "missing_interpreter":
            (environment_path / "bin").mkdir(parents=True, exist_ok=True)
            (environment_path / "bin/python").write_text("fixture", encoding="utf-8")
        if state["fail"] and failure_mode == "nonzero":
            return subprocess.CompletedProcess(
                command,
                7,
                stdout="x" * 9000,
                stderr="offline failure",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    manager, lock = _accepted_fixture_manager(tmp_path, transactional_create_runner)
    canonical = tmp_path / ".autovla_envs/pi0_5_conversion"
    with pytest.raises(RuntimeEnvironmentError) as captured:
        manager.create(
            "pi0_5_conversion",
            lock,
            nonce="fixture-failure",
            allow_create=True,
        )
    expected = (
        "ENVIRONMENT_CREATE_INCOMPLETE"
        if failure_mode == "missing_interpreter"
        else "ENVIRONMENT_CREATE_FAILED"
    )
    assert captured.value.code == expected
    assert not canonical.exists()
    assert not tuple((tmp_path / ".autovla_envs").glob(".materializing-*"))
    receipt_path = (
        tmp_path
        / "runs/tmp/autovla-runtime-profiles/diagnostics"
        / "pi0_5_conversion.last-create-failure.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["error"]["code"] == expected
    assert len(receipt["stdout_tail"]) <= 4096

    state["fail"] = False
    result = manager.create(
        "pi0_5_conversion",
        lock,
        nonce="fixture-retry",
        allow_create=True,
    )
    assert result.lock_fingerprint == lock.fingerprint
    assert (canonical / "bin/python").is_file()
    assert (canonical / ".autovla-runtime-profile.json").is_file()


def test_marker_write_failure_is_transactional_and_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """marker 写失败只留下有界诊断,不发布环境且允许重试。"""

    def staging_interpreter_runner(
        command: list[str],
        *,
        env: dict[str, str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        """在 staging 中实现最小解释器。"""

        if command[0] != "uv":
            return _conversion_probe(command)
        environment_path = Path(env["UV_PROJECT_ENVIRONMENT"])
        (environment_path / "bin").mkdir(parents=True, exist_ok=True)
        (environment_path / "bin/python").write_text("fixture", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    manager, lock = _accepted_fixture_manager(tmp_path, staging_interpreter_runner)
    canonical = tmp_path / ".autovla_envs/pi0_5_conversion"

    def fail_marker(_marker: Path, _payload: dict[str, object]) -> None:
        """模拟文件系统拒绝 marker 写入。"""

        raise OSError("marker denied")

    with monkeypatch.context() as patcher:
        patcher.setattr(manager, "_write_creation_marker", fail_marker)
        with pytest.raises(RuntimeEnvironmentError) as captured:
            manager.create(
                "pi0_5_conversion",
                lock,
                nonce="fixture-marker-failure",
                allow_create=True,
            )
    assert captured.value.code == "ENVIRONMENT_MARKER_WRITE_FAILED"
    assert not canonical.exists()
    assert not tuple((tmp_path / ".autovla_envs").glob(".materializing-*"))

    manager.create(
        "pi0_5_conversion",
        lock,
        nonce="fixture-marker-retry",
        allow_create=True,
    )
    assert canonical.is_dir()


def test_incompatible_preserved_lock_cannot_materialize_environment(tmp_path: Path) -> None:
    """即使旧 lock 摘要匹配,未接受状态也必须在 uv 调用前关闭。"""

    _copy_profile_fixture(tmp_path)
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_runner(
        command: list[str],
        *,
        env: dict[str, str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        """记录环境创建参数并模拟最小可执行文件落盘。"""

        calls.append((command, env))
        environment_path = Path(env["UV_PROJECT_ENVIRONMENT"])
        (environment_path / "bin").mkdir(parents=True)
        (environment_path / "bin/python").write_text("fixture", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    manager = RuntimeEnvironmentManager(tmp_path, source_sha="b" * 40, runner=fake_runner)
    profile = manager.profiles["gr00t_n1d6_runtime"]
    assert profile.lock_sha256 is not None
    incompatible_lock = _conversion_lock(profile, profile.lock_sha256)
    with pytest.raises(RuntimeEnvironmentError) as captured:
        manager.create(
            "gr00t_n1d6_runtime",
            incompatible_lock,
            nonce="fixture-preserved-lock",
            allow_create=True,
        )
    assert captured.value.code == "RUNTIME_LOCK_CUDA_PROFILE_MISMATCH"
    assert calls == []
    inspected = manager.inspect("gr00t_n1d6_runtime")
    assert inspected["lock_hash_matches_descriptor"] is True
    assert inspected["lock_accepted"] is False
    assert inspected["creation_ready"] is False


def test_verify_missing_environment_is_read_only_and_deterministic(tmp_path: Path) -> None:
    """verify 缺失环境时稳定失败,且不得创建 canonical root。"""

    _copy_profile_fixture(tmp_path)
    manager = RuntimeEnvironmentManager(tmp_path, source_sha="c" * 40)
    adapter = LegacyRuntimeProfileAdapter(manager)
    first = adapter.verify("gr00t_n1d6_runtime")
    second = adapter.verify("gr00t_n1d6_runtime")
    assert first.status == "fail"
    assert {item.code for item in first.errors} == {
        "ENVIRONMENT_MISSING",
        "PROFILE_EXACT_VERSIONS_UNRESOLVED",
        "PROFILE_LOCK_NOT_ACCEPTED",
    }
    assert canonical_report_json(first) == canonical_report_json(second)
    assert not (tmp_path / ".autovla_envs").exists()


def test_conversion_exec_rejects_training_before_environment_probe() -> None:
    """转换 profile 对生产训练命令在任何环境副作用前失败。"""

    manager = RuntimeEnvironmentManager(ROOT, source_sha="d" * 40)
    profile = manager.profiles["pi0_5_conversion"]
    lock = _conversion_lock(profile, "1" * 64)
    environment = _conversion_environment(profile, lock, source_sha="d" * 40)
    with pytest.raises(RuntimeEnvironmentError) as captured:
        manager.exec(
            "pi0_5_conversion",
            lock,
            environment,
            ["autovla-train", "config.yaml"],
            asset_fingerprint="2" * 64,
            topology_fingerprint="3" * 64,
            evidence_path="runs/tmp/m12/training.json",
            operation="conversion",
        )
    assert captured.value.code == "CONVERSION_TRAINING_FORBIDDEN"


def test_cli_list_and_inspect_are_machine_readable_and_do_not_create_root() -> None:
    """list/inspect 输出 JSON,读取命令不创建环境。"""

    assert not (ROOT / ".autovla_envs").exists()
    listed = subprocess.run(
        [sys.executable, "-m", "autovla.cli.env", "list"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(listed.stdout)
    assert {item["profile_id"] for item in payload["result"]} == set(EXPECTED_PROFILE_IDS)
    inspected = subprocess.run(
        [sys.executable, "-m", "autovla.cli.env", "inspect", "gr00t_n1d6_runtime"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    inspected_payload = json.loads(inspected.stdout)["result"]
    assert inspected_payload["checkout_bound"] is False
    assert inspected_payload["observed_uv_lock_sha256"] is None
    checkout_inspected = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.cli.env",
            "--checkout-root",
            str(ROOT),
            "inspect",
            "gr00t_n1d6_runtime",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    inspected_payload = json.loads(checkout_inspected.stdout)["result"]
    assert inspected_payload["checkout_bound"] is True
    assert inspected_payload["lock_hash_matches_descriptor"] is True
    assert inspected_payload["lock_accepted"] is False
    assert inspected_payload["creation_ready"] is False
    assert not (ROOT / ".autovla_envs").exists()


def test_cli_packaged_metadata_works_outside_checkout_without_root_inference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """安装产物风格调用可在任意 cwd 读取元数据,且不会猜测 checkout。"""

    from autovla.cli.env import main

    monkeypatch.chdir(tmp_path)
    assert main(["list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert {item["profile_id"] for item in listed["result"]} == set(EXPECTED_PROFILE_IDS)

    assert main(["inspect", "pi0_5_runtime"]) == 0
    inspected = json.loads(capsys.readouterr().out)["result"]
    assert inspected["checkout_bound"] is False
    assert inspected["creation_ready"] is False

def test_cli_manager_construction_failure_is_stable_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """无效显式 checkout 在 manager 构造阶段也返回稳定 JSON。"""

    from autovla.cli.env import main

    assert main(["--checkout-root", str(tmp_path), "list"]) == 2
    failed = json.loads(capsys.readouterr().out)
    assert failed == {
        "ok": False,
        "error": {
            "code": "CHECKOUT_ROOT_INVALID",
            "message": "checkout root must contain pyproject.toml",
        },
    }


def test_source_has_no_global_mutation_or_implicit_sync_path() -> None:
    """实现不得修改 Conda/site-packages,也不得从 verify/exec 调用 create。"""

    manager_source = (ROOT / "autovla/runtime_profiles/manager.py").read_text(encoding="utf-8")
    assert "conda" not in manager_source.lower()
    assert "site-packages" not in manager_source
    verify_body = manager_source.split("    def verify(", 1)[1].split("    @staticmethod", 1)[0]
    exec_body = manager_source.split("    def exec(", 1)[1]
    assert "self.create(" not in verify_body
    assert "self.create(" not in exec_body
    assert "uv sync" not in verify_body
    assert "uv sync" not in exec_body
    cli_source = (ROOT / "autovla/cli/env.py").read_text(encoding="utf-8")
    assert "__file__" not in cli_source
