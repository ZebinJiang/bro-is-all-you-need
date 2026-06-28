"""AutoVLA 仓库级策略测试。"""

import ast
import json
import subprocess
import zipfile
from pathlib import Path

from setuptools import find_namespace_packages


def repo_root() -> Path:
    """返回仓库根目录路径。"""
    return Path(__file__).resolve().parents[2]


def read_text(path: Path) -> str:
    """读取 UTF-8 文本文件内容。"""
    return path.read_text(encoding="utf-8")


def package_discovery_excludes(root: Path) -> list[str]:
    """提取 pyproject 中 setuptools package discovery 排除规则。"""
    pyproject = read_text(root / "pyproject.toml")
    section = pyproject.split("[tool.setuptools.packages.find]", 1)[1]
    section = section.split("\n[", 1)[0]
    exclude_block = section.split("exclude = [", 1)[1].split("]", 1)[0]

    excludes: list[str] = []
    for line in exclude_block.splitlines():
        value = line.split("#", 1)[0].strip().rstrip(",")
        if value:
            excludes.append(str(ast.literal_eval(value)))
    return excludes


def build_wrapper_forbidden_top_level(root: Path) -> set[str]:
    """从 wheel 扫描器源码提取顶层禁入路径集合。"""
    wrapper = read_text(root / "scripts/quality/genesis_build_verify_project_local.sh")
    prefix = "forbidden_top_level = "
    for line in wrapper.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            value = stripped.removeprefix(prefix)
            parsed = ast.literal_eval(value)
            assert isinstance(parsed, set)
            return {str(item) for item in parsed}
    raise AssertionError("missing wheel scanner forbidden_top_level policy")


def git_ls_files(root: Path, pathspec: str) -> list[str]:
    """返回给定 pathspec 下被 Git 追踪的路径。"""
    result = subprocess.run(
        ["git", "ls-files", pathspec],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def make_target_body(text: str, target: str) -> str:
    """提取 Makefile target 的缩进行命令体。"""
    marker = f"{target}:"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line == marker:
            body: list[str] = []
            for body_line in lines[index + 1 :]:
                if body_line and not body_line.startswith(("\t", " ")):
                    break
                body.append(body_line)
            return "\n".join(body)
    raise AssertionError(f"missing Makefile target: {target}")


def root_yaml_scalar(text: str, key: str) -> str:
    """提取根层级 YAML 标量值, 用于轻量治理断言。"""
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip().strip('"')
    raise AssertionError(f"missing root YAML key: {key}")


def root_yaml_list(text: str, key: str) -> list[str]:
    """提取根层级 YAML 字符串列表, 用于轻量治理断言。"""
    prefix = f"{key}:"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            inline_value = line.removeprefix(prefix).strip()
            if inline_value == "[]":
                return []
            assert inline_value == "", f"expected block YAML list for key: {key}"

            values: list[str] = []
            for item_line in lines[index + 1 :]:
                if item_line and not item_line.startswith((" ", "\t")):
                    break
                stripped = item_line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                assert stripped.startswith(
                    "- "
                ), f"expected YAML list item under {key}: {item_line}"
                values.append(stripped.removeprefix("- ").split("#", 1)[0].strip().strip('"'))
            return values
    raise AssertionError(f"missing root YAML list key: {key}")


def task_index_gate_statuses(task_index: str, task_id: str) -> set[str]:
    """返回任务在任务索引状态列表中的出现位置。"""
    statuses: set[str] = set()
    for status_key in ("active", "blocked", "completed"):
        if task_id in root_yaml_list(task_index, status_key):
            statuses.add(status_key)
    return statuses


def assert_no_placeholders(text: str, path: Path) -> None:
    """确认治理文档不包含占位内容标记。"""
    banned_tokens = ("TODO", "TBD", "placeholder", "lorem")
    for token in banned_tokens:
        assert token not in text, f"{path} contains forbidden token {token!r}"


def test_should_have_autovla_docs() -> None:
    root = repo_root()
    docs = {
        "architecture": root / "docs/autovla/rfc_000_architecture.md",
        "coding": root / "docs/autovla/coding_standard.md",
        "testing": root / "docs/autovla/testing_standard.md",
        "m1_lite": root / "docs/autovla/m1_lite_contract.md",
    }

    for path in docs.values():
        assert path.exists(), f"missing required AutoVLA doc: {path}"
        text = read_text(path)
        assert "AutoVLA" in text
        assert_no_placeholders(text, path)

    architecture = read_text(docs["architecture"])
    assert "StarVLA" in architecture
    assert "seven-layer" in architecture
    assert "make autovla-check" in architecture

    coding = read_text(docs["coding"])
    for phrase in ("Branch Policy", "Pyright", "Ruff", "Black", "Chinese docstrings", "100"):
        assert phrase in coding

    testing = read_text(docs["testing"])
    for phrase in ("TDD-first", "make autovla-check", "StarVLA backlog"):
        assert phrase in testing

    m1_lite = read_text(docs["m1_lite"])
    for phrase in (
        "M1-lite",
        "numpy-only",
        "torch-free",
        "FrameworkOutput.loss",
        "M3/M4",
    ):
        assert phrase in m1_lite


def test_should_publish_autovla_typed_marker() -> None:
    """确认 AutoVLA typed marker 会随包发布。"""
    root = repo_root()

    assert (root / "autovla/py.typed").exists()
    pyproject = read_text(root / "pyproject.toml")
    assert '"autovla" = ["py.typed"]' in pyproject


def test_should_pin_quality_toolchain_outside_dev_extra() -> None:
    """确认质量工具链使用独立锁定依赖面, 而不是 dev extra 漂移安装。"""
    root = repo_root()
    requirements = read_text(root / "requirements/quality/quality-requirements.txt")
    constraints = read_text(root / "requirements/quality/quality-constraints.txt")
    bootstrap = read_text(root / "scripts/quality/bootstrap_project_local_tools.sh")

    for required in (
        "black",
        "ruff",
        "pyright",
        "pytest",
        "build",
        "setuptools",
        "wheel",
        "numpy",
        "omegaconf",
        "pyarrow",
    ):
        assert required in requirements

    for pinned in (
        "black==26.5.1",
        "ruff==0.15.18",
        "pyright==1.1.410",
        "pytest==9.1.1",
        "build==1.5.0",
        "setuptools==80.9.0",
        "wheel==0.47.0",
        "numpy==2.2.6",
        "omegaconf==2.3.1",
        "pyarrow==18.1.0",
    ):
        assert pinned in constraints

    assert 'pip install -e ".[dev]"' not in bootstrap
    assert "quality-requirements.txt" in bootstrap
    assert "quality-constraints.txt" in bootstrap
    assert "--no-index" in bootstrap
    assert "--find-links" in bootstrap
    assert "--fill-wheelhouse" in bootstrap
    assert "PIP_DISABLE_PIP_VERSION_CHECK=1" in bootstrap
    assert "PIP_NO_INPUT=1" in bootstrap
    assert "m1-tool-venv.ready.json" in bootstrap
    assert "wheelhouse_manifest" in bootstrap
    assert "missing wheelhouse distributions:" in bootstrap
    assert "exit 66" in bootstrap
    assert "missing-requirements" in bootstrap
    assert "missing-binary-requirements" in bootstrap
    assert "missing-source-build-requirements" in bootstrap
    assert "bounded_online_wheelhouse_fill" in bootstrap
    assert "bounded_online_source_wheel_build" in bootstrap
    assert "SOURCE_BUILD_ALLOWLIST" in bootstrap
    assert "antlr4-python3-runtime==4.9.3" in bootstrap
    assert "source_build_fallbacks" in bootstrap
    assert "--only-binary=:all:" in bootstrap
    assert "--no-binary=:all:" in bootstrap
    assert "--no-deps" in bootstrap
    assert "[build-system]" in read_text(root / "pyproject.toml")
    assert 'build-backend = "setuptools.build_meta"' in read_text(root / "pyproject.toml")


def test_should_pin_pyarrow_and_write_real_parquet_fixture_smoke(tmp_path: Path) -> None:
    """确认真实 Parquet fixture 依赖被锁定, 且可写入/读取实际 parquet 文件。"""
    import pyarrow as pa
    import pyarrow.parquet as pq

    root = repo_root()
    requirements = read_text(root / "requirements/quality/quality-requirements.txt")
    constraints = read_text(root / "requirements/quality/quality-constraints.txt")
    upstream_sources = read_text(root / "docs/references/upstream_sources.yaml")

    assert "pyarrow" in requirements
    assert "pyarrow==18.1.0" in constraints
    assert "PyArrow" in upstream_sources
    assert "Apache-2.0" in upstream_sources

    parquet_path = tmp_path / "tiny-real-format.parquet"
    table = pa.table(
        {
            "sample_id": ["sample-0", "sample-1"],
            "step_index": [0, 1],
            "action": [[0.1, 0.2], [0.3, 0.4]],
        }
    )
    pq.write_table(table, parquet_path)

    payload = parquet_path.read_bytes()
    assert payload[:4] == b"PAR1"
    assert payload[-4:] == b"PAR1"

    loaded = pq.read_table(parquet_path)
    assert loaded.num_rows == 2
    assert loaded.column_names == ["sample_id", "step_index", "action"]
    assert loaded["sample_id"].to_pylist() == ["sample-0", "sample-1"]
    assert loaded["step_index"].to_pylist() == [0, 1]
    assert loaded["action"].to_pylist() == [[0.1, 0.2], [0.3, 0.4]]


def test_should_have_make_autovla_check() -> None:
    makefile = repo_root() / "Makefile"
    text = read_text(makefile)
    bootstrap_body = make_target_body(text, "autovla-check-bootstrap")
    wheelhouse_body = make_target_body(text, "autovla-wheelhouse-fill")
    autovla_body = make_target_body(text, "autovla-check")
    build_body = make_target_body(text, "autovla-build-check")
    governance_body = make_target_body(text, "governance-check")

    assert "\nautovla-check-bootstrap:\n" in f"\n{text}"
    assert "\nautovla-wheelhouse-fill:\n" in f"\n{text}"
    assert "\nautovla-check:\n" in f"\n{text}"
    assert "\nautovla-build-check:\n" in f"\n{text}"
    assert "\ngovernance-check:\n" in f"\n{text}"
    assert "bash scripts/quality/bootstrap_project_local_tools.sh" in bootstrap_body
    assert (
        "bash scripts/quality/bootstrap_project_local_tools.sh --fill-wheelhouse" in wheelhouse_body
    )
    assert "bash scripts/quality/autovla_check_project_local.sh" in autovla_body
    assert "bash scripts/quality/autovla_build_verify_project_local.sh" in build_body
    assert "PYTHONPYCACHEPREFIX=runs/tmp/m1-tool-pip-tmp/python-cache-governance" in governance_body
    assert "PYTEST_ADDOPTS='-p no:cacheprovider'" in governance_body

    assert "tests/meta" not in autovla_body
    assert "tests/meta/test_repo_policy.py" in governance_body

    assert "\ncheck:\n" in f"\n{text}"
    assert "black --check ." in text
    assert "ruff check --show-source ." in text


def test_should_have_pyright_strict_config() -> None:
    config_path = repo_root() / "pyrightconfig.autovla.json"
    assert config_path.exists(), f"missing required Pyright config: {config_path}"
    config = json.loads(read_text(config_path))

    assert config["typeCheckingMode"] == "strict"
    assert config["pythonVersion"] == "3.10"
    assert config["venvPath"] == "runs/tmp"
    assert config["venv"] == "m1-tool-venv"

    include = set(config["include"])
    assert {
        "autovla",
        "autovla/core",
        "autovla/config",
        "tests/core",
        "tests/config",
        "tests/dataloader",
        "tests/training",
        "tests/maintenance",
        "tests/slurm",
        "scripts/maintenance",
        "scripts/slurm",
    } <= include
    assert "tests/meta" not in include

    exclude = set(config["exclude"])
    expected_excludes = {
        "starVLA",
        "datasets",
        "runs",
        "playground",
        "results",
        "checkpoints",
        "examples",
        "eval",
    }
    assert expected_excludes <= exclude
    assert "tests/dataloader" not in exclude
    assert "autovla/dataloader" not in exclude


def test_should_have_project_local_build_wheel_wrapper() -> None:
    """确认 wheel 构建、安装和内容扫描均限制在项目本地工具路径。"""
    root = repo_root()
    wrapper = read_text(root / "scripts/quality/genesis_build_verify_project_local.sh")

    for required in (
        'TOOL_PY="$ROOT/runs/tmp/m1-tool-venv/bin/python"',
        'WORK_ROOT="$ROOT/runs/tmp/$TASK_ID"',
        'TASK_ID="GVLA-M2-TOOLENV-RECOVERY-001"',
        'DIST_DIR="$WORK_ROOT/dist"',
        'WHEEL_VENV="$WORK_ROOT/clean-install-venv"',
        'PIP_CACHE="$ROOT/runs/tmp/m1-tool-pip-cache"',
        'PIP_TMP="$ROOT/runs/tmp/m1-tool-pip-tmp"',
        'PROVENANCE_DIR="$WORK_ROOT/source-provenance"',
        'READY_STAMP="$WORK_ROOT/stamps/m1-tool-venv.ready.json"',
        'export PIP_CACHE_DIR="$PIP_CACHE"',
        'export TMPDIR="$PIP_TMP"',
        'export PYTHONPYCACHEPREFIX="$PY_CACHE"',
        'if [[ ! -x "$TOOL_PY" ]]',
        '"$TOOL_PY" -m build --no-isolation --wheel --outdir "$DIST_DIR"',
        '"$TOOL_PY" -m venv "$WHEEL_VENV"',
        "--no-index",
        '--find-links "$WHEELHOUSE"',
        '"$WHEEL_PY" -m pip check',
        "import autovla",
        '"py_typed"',
        "import zipfile",
        "forbidden_parts = {",
        "forbidden_suffixes = (",
        "PASS wheel_content_scan",
        "PASS genesis_build_verify_project_local",
    ):
        assert required in wrapper

    for forbidden in (
        '"code-input"',
        '"datasets"',
        '"runs"',
        '"checkpoints"',
        '"playground"',
        '"results"',
        '"cache"',
        '".pt"',
        '".pth"',
        '".ckpt"',
        '".safetensors"',
        '".onnx"',
        '".bin"',
        '".parquet"',
        '".arrow"',
        '".npy"',
        '".npz"',
        '".zip"',
        '".tar"',
        '".tar.gz"',
        '".tgz"',
        '".zst"',
    ):
        assert forbidden in wrapper


def test_should_exclude_project_local_runs_from_package_discovery() -> None:
    """确认项目本地 runs 证据目录不会被 setuptools 发现进 wheel。"""
    excludes = package_discovery_excludes(repo_root())

    assert "runs" in excludes
    assert "runs.*" in excludes


def test_should_exclude_runs_namespace_packages_while_discovering_autovla(
    tmp_path: Path,
) -> None:
    """确认 setuptools namespace discovery 会保留 AutoVLA 并排除 runs 证据。"""
    root = repo_root()
    package_root = tmp_path / "package-root"
    genesis_package = package_root / "autovla/example"
    preservation_package = (
        package_root / "runs/tmp/task/root-preservation/untracked-files/tests/meta"
    )
    genesis_package.mkdir(parents=True)
    preservation_package.mkdir(parents=True)
    (genesis_package / "__init__.py").write_text("", encoding="utf-8")
    (preservation_package / "__init__.py").write_text("", encoding="utf-8")

    discovered_without_excludes = set(find_namespace_packages(where=str(package_root)))
    assert "runs.tmp.task.root-preservation.untracked-files.tests.meta" in (
        discovered_without_excludes
    )

    discovered = set(
        find_namespace_packages(
            where=str(package_root),
            exclude=package_discovery_excludes(root),
        )
    )
    assert "autovla" in discovered
    assert "autovla.example" in discovered
    assert "runs" not in discovered
    assert not any(package.startswith("runs.") for package in discovered)


def test_should_keep_wheel_scanner_rejecting_runs_entries(tmp_path: Path) -> None:
    """确认严格 wheel 扫描器策略仍拒绝 runs 顶层条目。"""
    forbidden_top_level = build_wrapper_forbidden_top_level(repo_root())
    wheel_path = tmp_path / "synthetic.whl"
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr("autovla/__init__.py", "")
        wheel.writestr("runs/tmp/task/root-preservation/evidence.py", "")

    rejected_entries: list[str] = []
    with zipfile.ZipFile(wheel_path) as wheel:
        for name in wheel.namelist():
            parts = [
                part.lower() for part in name.replace("\\", "/").split("/") if part and part != "."
            ]
            if parts and parts[0] in forbidden_top_level:
                rejected_entries.append(name)

    assert "runs" in forbidden_top_level
    assert rejected_entries == ["runs/tmp/task/root-preservation/evidence.py"]


def test_should_not_track_upstream_reference_archives_or_source_trees() -> None:
    """确认 PR 不追踪完整上游源码包、解压树或二进制参考资产。"""
    root = repo_root()
    tracked = set(git_ls_files(root, "code-input"))

    forbidden_exact = {
        "code-input/dexbotic-main.zip",
        "code-input/FluxVLA-main.zip",
    }
    forbidden_prefixes = (
        "code-input/dexbotic-main/",
        "code-input/FluxVLA-main/",
    )
    forbidden_suffixes = (
        ".zip",
        ".mp4",
        ".npy",
        ".npz",
        ".parquet",
        ".arrow",
        ".pt",
        ".pth",
        ".safetensors",
        ".bin",
        ".onnx",
    )

    assert tracked.isdisjoint(forbidden_exact)
    assert not any(path.startswith(forbidden_prefixes) for path in tracked)
    assert not any(path.endswith(forbidden_suffixes) for path in tracked)
    assert {"code-input/REFERENCE_ASSETS.md", "code-input/LICENSE_REVIEW.md"} <= tracked


def test_should_record_upstream_reference_sources_without_full_source() -> None:
    """确认上游参考来源以可审查元数据记录, 而不是提交完整源码。"""
    root = repo_root()
    reference_path = root / "docs/references/upstream_sources.yaml"
    assert reference_path.exists(), "missing upstream source reference registry"

    text = read_text(reference_path)
    for required in (
        "dexbotic",
        "FluxVLA",
        "source_archive_sha256:",
        "exact_revision:",
        "license:",
        "reviewed_paths:",
        "reused_symbols:",
        "reuse_type:",
        "local_destination:",
    ):
        assert required in text

    for forbidden in ("UNKNOWN", "TO_FILL", "placeholder"):
        assert forbidden not in text


def test_should_keep_code_input_reference_assets_review_only() -> None:
    """确认 code-input 只保留审查记录, 不进入产品包、类型检查和质量门。"""
    root = repo_root()
    gitignore = read_text(root / ".gitignore")
    pyproject = read_text(root / "pyproject.toml")
    pyright = json.loads(read_text(root / "pyrightconfig.autovla.json"))
    wrapper = read_text(root / "scripts/quality/genesis_check_project_local.sh")

    expected_allowlist = (
        "!code-input/",
        "code-input/*",
        "!code-input/REFERENCE_ASSETS.md",
        "!code-input/LICENSE_REVIEW.md",
    )
    for fragment in expected_allowlist:
        assert fragment in gitignore

    forbidden_allowlist = (
        "!code-input/dexbotic-main.zip",
        "!code-input/FluxVLA-main.zip",
        "!code-input/dexbotic-main/",
        "!code-input/dexbotic-main/**",
        "!code-input/FluxVLA-main/",
        "!code-input/FluxVLA-main/**",
    )
    for fragment in forbidden_allowlist:
        assert fragment not in gitignore

    for relative_path in (
        "code-input/REFERENCE_ASSETS.md",
        "code-input/LICENSE_REVIEW.md",
    ):
        assert (root / relative_path).exists(), f"missing review asset: {relative_path}"

    assert '"code-input",    # review-only reference assets' in pyproject
    assert '"code-input.*"' in pyproject
    assert "code-input" not in pyright["include"]
    assert "code-input" in pyright["exclude"]

    assert "find autovla tests/core tests/config tests/dataloader" in wrapper
    assert "tests/maintenance tests/slurm scripts/maintenance scripts/slurm" in wrapper
    assert "run_step product_pytest" in wrapper
    assert "run_step governance_pytest" in wrapper
    assert (
        "tests/core tests/config tests/dataloader tests/training tests/maintenance tests/slurm -v"
        in wrapper
    )
    assert "run_step product_ruff" in wrapper
    assert "run_step governance_ruff" in wrapper
    assert (
        'ruff check --config "line-length=100" autovla tests/core tests/config '
        "tests/dataloader tests/training tests/maintenance tests/slurm "
        "scripts/maintenance scripts/slurm" in wrapper
    )
    assert "tests/meta/test_repo_policy.py" not in make_target_body(
        read_text(root / "Makefile"), "autovla-check"
    )
    assert '"code-input"' in wrapper
    assert '"../../../code-input"' in wrapper


def test_should_cover_m1_product_gate_paths_in_ci_and_precommit() -> None:
    """确认新增 M1 产品路径会触发 CI 和本地 pre-commit 检查。"""
    root = repo_root()
    workflow = read_text(root / ".github/workflows/autovla.yml")
    precommit = read_text(root / ".pre-commit-config.yaml")
    makefile = read_text(root / "Makefile")
    bootstrap = read_text(root / "scripts/quality/bootstrap_project_local_tools.sh")

    for required in (
        "tests/dataloader/**",
        "tests/maintenance/**",
        "tests/slurm/**",
        "scripts/maintenance/**",
        "scripts/slurm/**",
        "requirements/quality/**",
    ):
        assert required in workflow

    for required in (
        "tests/(core|config|dataloader|maintenance|slurm)",
        "scripts/(maintenance|slurm)",
    ):
        assert required in precommit

    assert "bash scripts/quality/bootstrap_project_local_tools.sh" in workflow
    assert "bash scripts/quality/bootstrap_project_local_tools.sh --fill-wheelhouse" in workflow
    assert 'python -m pip install -e ".[dev]"' not in workflow
    assert "uses: actions/cache@v4" in workflow
    assert "runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001/wheelhouse" in workflow
    assert "runs/tmp/m1-tool-pip-cache" in workflow
    assert "${{ runner.os }}" in workflow
    assert "${{ runner.arch }}" in workflow
    assert "py3.10" in workflow
    assert "quality-requirements.txt" in workflow
    assert "quality-constraints.txt" in workflow
    assert "pyproject.toml" in workflow
    assert "make autovla-check" in workflow
    assert "make governance-check" in workflow
    assert "make autovla-build-check" in workflow

    cache_body = workflow.split("uses: actions/cache@v4", 1)[1].split("- name:", 1)[0]
    assert "runs/tmp/m1-tool-venv" not in cache_body
    assert "clean-install-venv" not in cache_body
    assert "runs/tmp/**" not in cache_body

    assert "autovla-check-bootstrap" in makefile
    assert 'VENV="$ROOT/runs/tmp/m1-tool-venv"' in bootstrap
    assert 'PIP_CACHE="$ROOT/runs/tmp/m1-tool-pip-cache"' in bootstrap
    assert 'PIP_TMP="$ROOT/runs/tmp/m1-tool-pip-tmp"' in bootstrap
    assert 'TASK_ID="GVLA-M2-TOOLENV-RECOVERY-001"' in bootstrap
    assert 'REQ="$ROOT/requirements/quality/quality-requirements.txt"' in bootstrap
    assert 'CONSTRAINTS="$ROOT/requirements/quality/quality-constraints.txt"' in bootstrap
    assert '"$PY" -m pip install -e ".[dev]"' not in bootstrap
    assert '"$PY" -m pip install -U pip' not in bootstrap


def test_should_reject_bidirectional_control_characters_in_public_gate_inputs() -> None:
    """确认公开 gate 输入不含可隐藏审查内容的双向控制字符。"""
    root = repo_root()
    scanned_roots = [
        root / ".github",
        root / "scripts",
        root / "tests",
        root / "docs",
        root / "coordination",
        root / "Makefile",
        root / "pyproject.toml",
    ]
    suffixes = {".md", ".py", ".sh", ".toml", ".yaml", ".yml", ".json", ".txt"}
    bidi_controls = {chr(codepoint) for codepoint in range(0x202A, 0x202F)} | {
        chr(codepoint) for codepoint in range(0x2066, 0x206A)
    }
    offenders: list[str] = []

    for scanned_root in scanned_roots:
        if scanned_root.is_file():
            paths = [scanned_root]
        else:
            paths = [
                path
                for path in scanned_root.rglob("*")
                if path.is_file() and (path.suffix in suffixes or path.name == "Makefile")
            ]
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if any(character in line for character in bidi_controls):
                    offenders.append(f"{path.relative_to(root)}:{line_number}")

    assert offenders == []


def test_should_use_100_character_line_length_in_project_tooling() -> None:
    """确认项目级 Black/Ruff 配置与 M1 gate 的 100 列一致。"""
    pyproject = read_text(repo_root() / "pyproject.toml")
    assert "[tool.black]" in pyproject
    assert "[tool.ruff]" in pyproject
    assert "line-length = 100" in pyproject
    assert "line-length = 121" not in pyproject


def test_should_have_pr_template_with_test_plan() -> None:
    template_path = repo_root() / ".github/PULL_REQUEST_TEMPLATE.md"
    text = read_text(template_path)

    assert "AutoVLA Test Plan" in text
    assert "`make autovla-check`" in text
    assert "tests first" in text
    assert "StarVLA backlog" in text
    assert "No datasets, checkpoints, secrets, or run artifacts" in text


def test_should_have_codex_thread_team_control_plane() -> None:
    """确认 Codex-only 常驻线程控制面已经落地。"""
    root = repo_root()
    required_paths = [
        "docs/coordination/MANAGER_ENTRYPOINT.md",
        "docs/coordination/CODEX_MANAGER_GOVERNANCE.md",
        "docs/coordination/CLAUDE_RULES_MIGRATION.md",
        "docs/coordination/TEAM_OPERATING_MODEL.md",
        "docs/coordination/testing/M1T_COORDINATION_VALIDATION.md",
        "coordination/PROGRAM_STATE.yaml",
        "coordination/TASK_INDEX.yaml",
        "coordination/templates/TASK_CARD.yaml",
        "coordination/templates/owner-report.md",
        "coordination/templates/manager-summary.md",
        "coordination/tasks/active/GVLA-M1T-001.yaml",
        "coordination/tasks/active/GVLA-M1T-002.yaml",
        "coordination/tasks/backlog/GVLA-M1-RECON-001.yaml",
    ]

    for relative_path in required_paths:
        path = root / relative_path
        assert path.exists(), f"missing Codex control-plane file: {relative_path}"
        assert_no_placeholders(read_text(path), path)

    program_state = read_text(root / "coordination/PROGRAM_STATE.yaml")
    task_index = read_text(root / "coordination/TASK_INDEX.yaml")
    blocking_gate = root_yaml_scalar(program_state, "blocking_gate")
    assert root_yaml_scalar(program_state, "active_milestone") in {"M1", "M2"}
    if blocking_gate != "M1-T":
        assert root_yaml_scalar(task_index, "blocking_gate") == blocking_gate
        assert task_index_gate_statuses(task_index, blocking_gate), (
            "blocking_gate must be M1-T or an indexed task in "
            "TASK_INDEX.yaml active/blocked/completed lists"
        )
    assert "single_writer_per_task: true" in program_state
    assert "behavior_changes_require_owner_route: true" in program_state
    assert "active_governance: docs/coordination/CODEX_MANAGER_GOVERNANCE.md" in program_state
    assert "root_claude_md_is_legacy_only: true" in program_state

    assert "GVLA-M1T-001" in task_index
    assert "GVLA-M1T-002" in task_index
    assert "GVLA-M1-RECON-001" in task_index

    task_card = read_text(root / "coordination/tasks/active/GVLA-M1T-001.yaml")
    for required in (
        "primary_owner: quality",
        "required_reviewers:",
        "write_scope:",
        "protected_paths:",
        "acceptance_criteria:",
        "required_commands:",
        "python -m pytest tests/meta/test_repo_policy.py -v",
    ):
        assert required in task_card

    protected_terms = (
        "model behavior",
        "data behavior",
        "training behavior",
        "deployment behavior",
        "Slurm behavior",
        "dataset conversion",
        "checkpoints",
        "robot endpoints",
    )
    for term in protected_terms:
        assert term in task_card


def test_should_have_owner_charters_and_thread_prompts() -> None:
    """确认 Manager 和六个 Owner 线程均可从文件恢复。"""
    root = repo_root()
    owner_files = [
        "docs/coordination/owners/architecture.md",
        "docs/coordination/owners/training.md",
        "docs/coordination/owners/30-owner-data.md",
        "docs/coordination/owners/40-owner-model.md",
        "docs/coordination/owners/50-owner-deployment.md",
        "docs/coordination/owners/60-owner-quality.md",
    ]
    for relative_path in owner_files:
        path = root / relative_path
        assert path.exists(), f"missing Owner charter: {relative_path}"
        text = read_text(path)
        assert "Authority" in text
        assert "Primary write scope" in text
        assert "Review duties" in text
        assert "Required report fields" in text

    prompt_files = [
        "docs/coordination/thread_prompts/00-manager.md",
        "docs/coordination/thread_prompts/10-owner-architecture.md",
        "docs/coordination/thread_prompts/20-owner-training.md",
        "docs/coordination/thread_prompts/30-owner-inputs.md",
        "docs/coordination/thread_prompts/40-owner-model.md",
        "docs/coordination/thread_prompts/50-owner-deployment.md",
        "docs/coordination/thread_prompts/60-owner-quality.md",
    ]
    for relative_path in prompt_files:
        path = root / relative_path
        assert path.exists(), f"missing thread prompt: {relative_path}"
        assert "Owner" in read_text(path) or "MANAGER" in read_text(path)


def test_should_have_sanitized_thread_registry_template() -> None:
    """确认发布版线程 registry 不包含真实运行态 ID 或本机绝对路径。"""
    root = repo_root()
    registry_path = root / "coordination/THREAD_REGISTRY.yaml"
    assert registry_path.exists(), "missing persistent Owner thread registry template"

    registry = read_text(registry_path)
    assert "thread_registry_schema_version: 1" in registry
    assert "registry_publication_mode: sanitized_example" in registry
    assert "startup_smoke_status: sanitized_example" in registry
    assert "root_claude_md_is_legacy_only: true" in registry
    assert "owner_threads_are_top_level: true" in registry
    assert "/home/" not in registry
    assert "codex resume" not in registry
    assert "thread_id: 019" not in registry
    assert registry.count("thread_id: <") >= 7

    required_owner_entries = {
        "architecture": "docs/coordination/owners/architecture.md",
        "training": "docs/coordination/owners/training.md",
        "data": "docs/coordination/owners/30-owner-data.md",
        "model": "docs/coordination/owners/40-owner-model.md",
        "deployment": "docs/coordination/owners/50-owner-deployment.md",
        "quality": "docs/coordination/owners/60-owner-quality.md",
    }
    for owner, charter_path in required_owner_entries.items():
        assert f"  {owner}:" in registry
        assert f"charter_path: {charter_path}" in registry
        assert "expected_token: ACK_OWNER_READY" in registry


def test_should_have_owner_subagent_configs() -> None:
    """确认 Owner 内部可使用一层直接子代理。"""
    root = repo_root()
    agent_files = [
        ".codex/agents/thread_explorer.toml",
        ".codex/agents/thread_implementer.toml",
        ".codex/agents/thread_reviewer.toml",
        ".codex/agents/thread_tester.toml",
    ]
    for relative_path in agent_files:
        path = root / relative_path
        assert path.exists(), f"missing thread-team subagent config: {relative_path}"
        text = read_text(path)
        assert "name" in text
        assert "description" in text
        assert "instructions" in text

    config = read_text(root / ".codex/config.toml")
    assert "max_depth = 1" in config
    assert "max_threads = 4" in config

    gitignore = read_text(root / ".gitignore")
    assert "!.codex/config.toml" in gitignore
    for relative_path in agent_files:
        assert f"!{relative_path}" in gitignore


def test_should_define_subagent_retirement_and_parallelism_protocols() -> None:
    """确认 Owner 子代理回收和并行写入提案协议可审计。"""
    root = repo_root()

    operating_model = read_text(root / "docs/coordination/TEAM_OPERATING_MODEL.md")
    manager_entrypoint = read_text(root / "docs/coordination/MANAGER_ENTRYPOINT.md")
    task_template = read_text(root / "coordination/templates/TASK_CARD.yaml")
    owner_report_template = read_text(root / "coordination/templates/owner-report.md")
    config = read_text(root / ".codex/config.toml")

    for required in (
        "Subagent retirement ledger",
        "parallel write proposal",
        "Manager approval",
        "user-facing gate",
    ):
        assert required in operating_model

    for required in (
        "parallelism_proposal:",
        "subagent_retirement:",
        "real_thread_startup_smoke:",
    ):
        assert required in task_template

    for required in (
        "## Subagent Retirement",
        "## Parallelism Proposal",
        "## Real Thread Startup Smoke",
    ):
        assert required in owner_report_template

    assert "subagent retirement ledger" in manager_entrypoint
    assert "parallelism proposal" in manager_entrypoint
    assert "real thread startup smoke" in manager_entrypoint
    assert "require_subagent_retirement_after_structural_task = true" in config
    assert 'parallel_write_structural_scope = "disjoint_safe_scopes_only"' in config


def test_should_define_real_thread_launch_smoke_validation() -> None:
    """确认 M1-T 定义真实线程启动 smoke 验证, 而非只检查文件存在。"""
    root = repo_root()
    validation = read_text(root / "docs/coordination/testing/M1T_COORDINATION_VALIDATION.md")

    for required in (
        "real thread startup smoke",
        "create_thread",
        "read_thread",
        "archive or retire",
        "must not replace formal implementation validation",
    ):
        assert required in validation


def test_should_not_require_live_claude_md_for_codex_only_startup() -> None:
    """确认 active Codex-only 控制面不再依赖根 CLAUDE.md。"""
    root = repo_root()
    active_files = [
        "AGENTS.md",
        "docs/coordination/CODEX_MANAGER_GOVERNANCE.md",
        "docs/coordination/MANAGER_ENTRYPOINT.md",
        "docs/coordination/thread_prompts/00-manager.md",
        "coordination/PROGRAM_STATE.yaml",
        "coordination/TASK_INDEX.yaml",
        "coordination/tasks/active/GVLA-M1T-002.yaml",
    ]

    for relative_path in active_files:
        text = read_text(root / relative_path)
        assert "CODEX_MANAGER_GOVERNANCE.md" in text or relative_path in {
            "coordination/TASK_INDEX.yaml",
            "coordination/tasks/active/GVLA-M1T-002.yaml",
        }

    entrypoint = read_text(root / "docs/coordination/MANAGER_ENTRYPOINT.md")
    manager_prompt = read_text(root / "docs/coordination/thread_prompts/00-manager.md")
    governance = read_text(root / "docs/coordination/CODEX_MANAGER_GOVERNANCE.md")
    agents = read_text(root / "AGENTS.md")

    forbidden_live_patterns = (
        "`CLAUDE.md`\n4.",
        "Read `AGENTS.md`, `boundaries.txt`, `CLAUDE.md`",
        "source authority remains root `CLAUDE.md`",
        "not a replacement for those files",
    )
    combined = "\n".join((entrypoint, manager_prompt, governance, agents))
    for pattern in forbidden_live_patterns:
        assert pattern not in combined

    assert "Active startup governance is `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`" in agents
    assert "Root `CLAUDE.md` is legacy supervisor documentation" in agents
    assert "root_claude_md_is_legacy_only: true" in read_text(
        root / "coordination/PROGRAM_STATE.yaml"
    )

    root_claude = root / "CLAUDE.md"
    if root_claude.exists():
        root_claude_text = read_text(root_claude)
        assert "retired" in root_claude_text
        assert "CODEX_MANAGER_GOVERNANCE.md" in root_claude_text
        assert "Do not add active instructions here" in root_claude_text
        assert "Claude Supervisor -> Codex Manager" not in root_claude_text


def test_should_forbid_devspace_mcp_as_internal_workflow_dependency() -> None:
    """确认 DevSpace MCP 只属于外部桥接工具, 不属于项目内部工作流。"""
    agents = read_text(repo_root() / "AGENTS.md")

    for required in (
        "DevSpace MCP boundary",
        "external ChatGPT bridge tools only",
        "not part of the repository-internal AutoVLA Manager",
        "must not call, require, document as execution evidence, or depend on DevSpace MCP",
        "governance violation",
        "External ChatGPT sessions may still use DevSpace MCP",
    ):
        assert required in agents
