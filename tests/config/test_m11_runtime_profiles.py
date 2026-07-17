"""M11 家族隔离运行时画像的确定性契约测试。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from autovla.runtime_profiles import (
    EXPECTED_PROFILE_IDS,
    RuntimeEnvironmentError,
    RuntimeEnvironmentManager,
    RuntimeEnvironmentSpec,
    canonical_report_json,
    load_runtime_profiles,
)

ROOT = Path(__file__).resolve().parents[2]


def test_profile_registry_is_exact_and_uses_canonical_environment_root() -> None:
    """画像身份闭集与环境路径必须完全匹配 M11 合同。"""

    profiles = load_runtime_profiles(ROOT)
    assert tuple(sorted(profiles)) == tuple(sorted(EXPECTED_PROFILE_IDS))
    for profile in profiles.values():
        spec = RuntimeEnvironmentSpec.for_profile(ROOT, profile)
        spec.validate()
        assert spec.environment_root == ROOT / ".autovla_envs"
        assert spec.environment_path == ROOT / ".autovla_envs" / profile.profile_id


def test_only_n1d6_preserves_accepted_exact_lock_and_pins() -> None:
    """只保留 intake 已证实的 N1.6 精确版本，不猜测另外三套版本。"""

    profiles = load_runtime_profiles(ROOT)
    n1d6 = profiles["gr00t_n1d6_runtime"]
    assert n1d6.lock_sha256 == (
        "41f807307ba96a00313b4e7af1bb584db5df42dfbe877eca09082dab60f5d662"
    )
    assert dict(n1d6.exact_packages) == {
        "numpy": "2.2.6",
        "safetensors": "0.5.3",
        "torch": "2.6.0",
        "torchvision": "0.21.0",
        "transformers": "4.51.3",
        "webdataset": "1.0.2",
    }
    for profile_id in ("gr00t_n1d7_runtime", "pi0_5_runtime", "pi0_5_conversion"):
        profile = profiles[profile_id]
        assert profile.lock_sha256 is None
        assert profile.exact_packages == ()
        assert profile.blockers
        assert not (ROOT / profile.uv_project / "uv.lock").exists()


def test_pi_runtime_rejects_jax_flax_orbax_and_conversion_is_not_training() -> None:
    """生产 Pi0.5 与转换依赖隔离，转换画像不得冒充训练画像。"""

    profiles = load_runtime_profiles(ROOT)
    runtime = profiles["pi0_5_runtime"]
    conversion = profiles["pi0_5_conversion"]
    assert {"jax", "flax", "orbax", "orbax-checkpoint"} <= set(
        runtime.prohibited_packages
    )
    assert runtime.is_training_runtime is True
    assert conversion.is_training_runtime is False
    assert conversion.kind == "conversion"


def test_unresolved_projects_are_explicit_non_install_manifests() -> None:
    """未解析项目保留空依赖与 blocker，不制造可接受 lock。"""

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
        calls.append((args, kwargs))
        raise AssertionError("runner must not be called")

    manager = RuntimeEnvironmentManager(ROOT, source_sha="a" * 40, runner=forbidden_runner)
    with pytest.raises(RuntimeEnvironmentError) as unauthorized:
        manager.create("gr00t_n1d6_runtime")
    assert unauthorized.value.code == "ENVIRONMENT_CREATE_NOT_AUTHORIZED"
    with pytest.raises(RuntimeEnvironmentError) as unresolved:
        manager.create("gr00t_n1d7_runtime", allow_create=True)
    assert unresolved.value.code == "PROFILE_EXACT_VERSIONS_UNRESOLVED"
    assert calls == []


def _copy_profile_fixture(destination: Path) -> None:
    """复制最小画像/项目 fixture，不复制环境或运行产物。"""

    profile_dir = destination / "configs/env/profiles"
    profile_dir.mkdir(parents=True)
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


def test_create_command_is_offline_locked_and_project_local(tmp_path: Path) -> None:
    """显式 create 只渲染 offline/locked uv，并写入固定环境根。"""

    _copy_profile_fixture(tmp_path)
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_runner(
        command: list[str],
        *,
        env: dict[str, str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, env))
        environment_path = Path(env["UV_PROJECT_ENVIRONMENT"])
        (environment_path / "bin").mkdir(parents=True)
        (environment_path / "bin/python").write_text("fixture", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    manager = RuntimeEnvironmentManager(tmp_path, source_sha="b" * 40, runner=fake_runner)
    result = manager.create("gr00t_n1d6_runtime", allow_create=True)
    command, env = calls[0]
    assert command[:4] == ["uv", "sync", "--offline", "--locked"]
    assert env["UV_OFFLINE"] == "1"
    assert env["PIP_NO_INDEX"] == "1"
    assert env["UV_PROJECT_ENVIRONMENT"] == str(
        tmp_path / ".autovla_envs/gr00t_n1d6_runtime"
    )
    assert result["environment_path"] == ".autovla_envs/gr00t_n1d6_runtime"


def test_verify_missing_environment_is_read_only_and_deterministic(tmp_path: Path) -> None:
    """verify 缺失环境时稳定失败，且不得创建 canonical root。"""

    _copy_profile_fixture(tmp_path)
    manager = RuntimeEnvironmentManager(tmp_path, source_sha="c" * 40)
    first = manager.verify("gr00t_n1d6_runtime")
    second = manager.verify("gr00t_n1d6_runtime")
    assert first.status == "fail"
    assert {item.code for item in first.errors} == {"ENVIRONMENT_MISSING"}
    assert canonical_report_json(first) == canonical_report_json(second)
    assert not (tmp_path / ".autovla_envs").exists()


def test_conversion_exec_rejects_training_before_environment_probe() -> None:
    """转换 profile 对生产训练命令在任何环境副作用前失败。"""

    manager = RuntimeEnvironmentManager(ROOT, source_sha="d" * 40)
    with pytest.raises(RuntimeEnvironmentError) as captured:
        manager.exec("pi0_5_conversion", ["autovla-train", "config.yaml"])
    assert captured.value.code == "CONVERSION_TRAINING_FORBIDDEN"


def test_cli_list_inspect_verify_are_machine_readable_and_do_not_create_root() -> None:
    """list/inspect/verify 输出 JSON，读取命令不创建环境。"""

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
    assert json.loads(inspected.stdout)["result"]["lock_hash_matches_descriptor"] is True
    verified = subprocess.run(
        [sys.executable, "-m", "autovla.cli.env", "verify", "gr00t_n1d6_runtime"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert verified.returncode == 2
    assert json.loads(verified.stdout)["result"]["status"] == "fail"
    assert not (ROOT / ".autovla_envs").exists()


def test_source_has_no_global_mutation_or_implicit_sync_path() -> None:
    """实现不得修改 Conda/site-packages，也不得从 verify/exec 调用 create。"""

    manager_source = (ROOT / "autovla/runtime_profiles/manager.py").read_text(encoding="utf-8")
    assert "conda" not in manager_source.lower()
    assert "site-packages" not in manager_source
    verify_body = manager_source.split("    def verify(", 1)[1].split("    @staticmethod", 1)[0]
    exec_body = manager_source.split("    def exec(", 1)[1]
    assert "self.create(" not in verify_body
    assert "self.create(" not in exec_body
    assert "uv sync" not in verify_body
    assert "uv sync" not in exec_body
