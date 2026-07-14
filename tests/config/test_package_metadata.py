"""验证 AutoVLA 分发元数据和构建发现边界。"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import TypeGuard

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_should_follow_pep621_package_contract() -> None:
    """验证依赖、URL、动态版本和许可证字段位于合法 PEP 621 表。"""
    payload = _toml_table(tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8")))
    project = _toml_table(payload["project"])
    description = project["description"]
    urls = _toml_table(project["urls"])
    optional = _toml_table(project["optional-dependencies"])

    assert project["name"] == "autovla"
    assert isinstance(description, str) and description.startswith("AutoVLA infrastructure")
    assert project["dynamic"] == ["version"]
    assert project["dependencies"] == ["numpy", "omegaconf"]
    assert all(isinstance(value, str) for value in urls.values())
    assert project["license"] == ("MIT AND Apache-2.0 AND LicenseRef-NVIDIA-Isaac-GR00T-N1D6")
    assert _toml_table(payload["build-system"])["requires"] == ["setuptools==77.0.3"]
    dev_dependencies = _object_list(optional["dev"])
    assert "tomli>=2; python_version < '3.11'" in dev_dependencies
    assert "sagemaker" not in optional


def test_setuptools_should_discover_only_autovla_and_package_resources() -> None:
    """验证构建发现仅覆盖 AutoVLA 并包含配置资源。"""
    payload = _toml_table(tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8")))
    tool = _toml_table(payload["tool"])
    setuptools = _toml_table(tool["setuptools"])
    packages = _toml_table(setuptools["packages"])
    package_data = _toml_table(setuptools["package-data"])
    project = _toml_table(payload["project"])
    pytest_config = _toml_table(tool["pytest"])
    pytest_options = _toml_table(pytest_config["ini_options"])

    assert _toml_table(packages["find"])["include"] == ["autovla", "autovla.*"]
    assert "resources/**/*.yaml" in _object_list(package_data["autovla"])
    assert _toml_table(project["scripts"]) == {
        "autovla-train": "autovla.cli.train:main",
        "autovla-inspect-config": "autovla.cli.inspect_config:main",
    }
    assert pytest_options["testpaths"] == ["tests"]
    assert {"runs", "envs", "examples"}.issubset(_object_list(pytest_options["norecursedirs"]))


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """收窄 TOML 动态映射。"""
    return isinstance(value, Mapping)


def _toml_table(value: object) -> dict[str, object]:
    """验证 TOML table 使用字符串键。"""
    if not _is_object_mapping(value):
        raise TypeError("expected TOML table")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("TOML table keys must be strings")
        result[key] = item
    return result


def _object_list(value: object) -> list[object]:
    """验证 TOML array 并固定元素边界。"""
    if not _is_object_list(value):
        raise TypeError("expected TOML array")
    return value


def _is_object_list(value: object) -> TypeGuard[list[object]]:
    """收窄 TOML 动态数组。"""
    return isinstance(value, list)


def test_build_gate_should_verify_both_archives_and_clean_installed_cli() -> None:
    """验证构建命令覆盖 wheel/sdist、许可证、隔离安装和包内配置。"""
    script = (ROOT / "scripts/quality/autovla_build_verify_project_local.sh").read_text(
        encoding="utf-8"
    )
    for required in (
        "--wheel --sdist",
        "Apache-2.0.txt",
        "MIT.txt",
        "NVIDIA-ISAAC-GROOT-N1D6.txt",
        "THIRD_PARTY_NOTICES.md",
        "--no-index",
        'autovla-train" --help',
        'autovla-inspect-config" --help',
        "pkg://experiments/local_debug",
        "autovla_version",
        '"torch_lazy": True',
        "forbidden binary/model/data artifact suffix",
        "--build-python is required",
        'setuptools_version != "77.0.3"',
        '"$BUILD_PY" -m build',
        "strip_sdist_root=True",
        "autovla.egg-info",
        "--quality-python is required",
        "--clean-install-venv must be under --work-root",
    ):
        assert required in script
    for retired_state in (
        "GVLA-M2-TOOLENV-RECOVERY-001",
        "m1-tool-venv",
        "m1-tool-pip-cache",
        "m1-tool-pip-tmp",
        "current-fingerprint.txt",
        "m1-tool-venv.ready.json",
    ):
        assert retired_state not in script


def test_full_build_gate_should_require_explicit_task_local_inputs() -> None:
    """验证 full mode 在任何写入前拒绝缺少的任务本地参数。"""
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/quality/autovla_build_verify_project_local.sh"),
            "--build-python",
            sys.executable,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "--quality-python is required" in result.stderr


def test_ci_should_pin_build_backend_and_select_all_m6_cpu_tests() -> None:
    """验证 CI 显式安装兼容后端并在离线运行阶段选择新测试。"""
    workflow = (ROOT / ".github/workflows/autovla.yml").read_text(encoding="utf-8")
    assert "setuptools==77.0.3" in workflow
    assert "python -m venv runs/tmp/m6-build-env" in workflow
    assert '--build-python "$PWD/runs/tmp/m6-build-env/bin/python"' in workflow
    assert '--quality-python "$PWD/runs/tmp/m6-build-env/bin/python"' in workflow
    assert '--wheelhouse "$PWD/runs/tmp/m6-build-wheelhouse"' in workflow
    assert "requirements/ci/m6-cpu-runtime.txt" in workflow
    assert "python -m pip install --no-deps ." in workflow
    assert "python -m pip check" in workflow
    assert ".[dev," not in workflow
    assert 'HF_HUB_OFFLINE: "1"' in workflow
    assert "tests/training/test_m6_runtime_commands.py" in workflow
    assert "tests/training/test_production_runtime_source_contract.py" in workflow


def _archive_members(prefix: str = "") -> dict[str, bytes]:
    """构造满足许可证和包资源边界的最小 archive 成员。"""
    return {
        f"{prefix}LICENSE": b"license\n",
        f"{prefix}THIRD_PARTY_NOTICES.md": b"notices\n",
        f"{prefix}licenses/Apache-2.0.txt": b"apache\n",
        f"{prefix}licenses/MIT.txt": b"mit\n",
        f"{prefix}licenses/NVIDIA-ISAAC-GROOT-N1D6.txt": b"nvidia\n",
        f"{prefix}autovla/__init__.py": b"__version__ = 'test'\n",
        f"{prefix}autovla/data/datasets/base.py": b"# package source\n",
        f"{prefix}autovla/dataloader/datasets/base.py": b"# package source\n",
        f"{prefix}autovla/resources/configs/experiments/local_debug.yaml": b"name: test\n",
        f"{prefix}autovla/resources/configs/models/gr00t_n1d6.yaml": b"model: {}\n",
    }


def _write_archives(
    root: Path,
    *,
    wheel_extra: str | None = None,
    sdist_extra: str | None = None,
    sdist_root: str = "autovla-0.1.0",
) -> tuple[Path, Path]:
    """写入最小 wheel/sdist,可注入一个恶意嵌套成员。"""
    wheel = root / "autovla-0.1.0-py3-none-any.whl"
    wheel_members = _archive_members()
    if wheel_extra is not None:
        wheel_members[wheel_extra] = b"blocked\n"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in wheel_members.items():
            archive.writestr(name, content)

    sdist = root / "autovla-0.1.0.tar.gz"
    sdist_members = _archive_members(f"{sdist_root}/")
    if sdist_extra is not None:
        sdist_members[sdist_extra] = b"blocked\n"
    with tarfile.open(sdist, "w:gz") as archive:
        for name, content in sdist_members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return wheel, sdist


def _scan_archives(wheel: Path, sdist: Path, output: Path) -> subprocess.CompletedProcess[str]:
    """调用 build gate 的无构建扫描模式。"""
    return subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/quality/autovla_build_verify_project_local.sh"),
            "--build-python",
            sys.executable,
            "--scan-only",
            "--wheel",
            str(wheel),
            "--sdist",
            str(sdist),
            "--scan-output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_archive_scanner_should_accept_normalized_safe_wheel_and_sdist(tmp_path: Path) -> None:
    """验证 sdist 去根后与 wheel 使用同一精确成员策略。"""
    wheel, sdist = _write_archives(tmp_path)
    output = tmp_path / "scan.json"
    result = _scan_archives(wheel, sdist, output)
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["forbidden_scan"] == "PASS"
    assert payload["normalized_sdist_members"] == payload["normalized_wheel_members"]


def test_archive_scanner_should_reject_starvla_sdist_root(tmp_path: Path) -> None:
    """验证被剥离前的 sdist 分发根也必须是 AutoVLA。"""
    wheel, sdist = _write_archives(tmp_path, sdist_root="starVLA-1.0.0")
    result = _scan_archives(wheel, sdist, tmp_path / "scan.json")
    assert result.returncode == 1
    assert "sdist distribution root must be autovla-<version>" in result.stderr


@pytest.mark.parametrize(
    ("wheel_extra", "sdist_extra", "expected"),
    (
        ("autovla/vendor/runs/model.safetensors", None, "forbidden archive component: runs"),
        (
            "autovla/vendor/model.safetensors",
            None,
            "forbidden binary/model/data artifact suffix",
        ),
        ("starVLA/legacy.py", None, "forbidden archive component: starvla"),
        ("tests/test_leak.py", None, "forbidden archive component: tests"),
        (
            "autovla/vendor/related-assets/source.py",
            None,
            "forbidden archive component: related-assets",
        ),
        (
            None,
            "autovla-0.1.0/nested/tests/test_leak.py",
            "forbidden archive component: tests",
        ),
        (
            None,
            "autovla-0.1.0/autovla/vendor/code-input/source.py",
            "forbidden archive component: code-input",
        ),
        (
            None,
            "autovla-0.1.0/autovla/vendor/datasets/sample.py",
            "forbidden archive component: datasets",
        ),
        ("datasets/sample.py", None, "forbidden archive component: datasets"),
        (
            None,
            "autovla-0.1.0/datasets/sample.py",
            "forbidden archive component: datasets",
        ),
        (
            None,
            "autovla-0.1.0/autovla/vendor/cache/item.py",
            "forbidden archive component: cache",
        ),
        (
            None,
            "autovla-0.1.0/autovla/vendor/checkpoints/state.py",
            "forbidden archive component: checkpoints",
        ),
        (
            None,
            "autovla-0.1.0/autovla/vendor/upstream-clones/source.py",
            "forbidden archive component: upstream-clones",
        ),
        (
            None,
            "autovla-0.1.0/nested/envs/runtime/python",
            "forbidden archive component: envs",
        ),
    ),
)
def test_archive_scanner_should_reject_malicious_nested_members(
    tmp_path: Path,
    wheel_extra: str | None,
    sdist_extra: str | None,
    expected: str,
) -> None:
    """验证 wheel/sdist 的嵌套泄漏与旧 StarVLA 根均被阻断。"""
    wheel, sdist = _write_archives(
        tmp_path,
        wheel_extra=wheel_extra,
        sdist_extra=sdist_extra,
    )
    result = _scan_archives(wheel, sdist, tmp_path / "scan.json")
    assert result.returncode == 1
    assert expected in result.stderr
