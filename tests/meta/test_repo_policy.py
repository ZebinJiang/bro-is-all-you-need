"""GenesisVLA 仓库级策略测试。"""

import json
from pathlib import Path


def repo_root() -> Path:
    """返回仓库根目录路径。"""
    return Path(__file__).resolve().parents[2]


def read_text(path: Path) -> str:
    """读取 UTF-8 文本文件内容。"""
    return path.read_text(encoding="utf-8")


def assert_no_placeholders(text: str, path: Path) -> None:
    """确认治理文档不包含占位内容标记。"""
    banned_tokens = ("TODO", "TBD", "placeholder", "lorem")
    for token in banned_tokens:
        assert token not in text, f"{path} contains forbidden token {token!r}"


def test_should_have_genesisvla_docs() -> None:
    root = repo_root()
    docs = {
        "architecture": root / "docs/genesisvla/rfc_000_architecture.md",
        "coding": root / "docs/genesisvla/coding_standard.md",
        "testing": root / "docs/genesisvla/testing_standard.md",
        "m1_lite": root / "docs/genesisvla/m1_lite_contract.md",
    }

    for path in docs.values():
        assert path.exists(), f"missing required GenesisVLA doc: {path}"
        text = read_text(path)
        assert "GenesisVLA" in text
        assert_no_placeholders(text, path)

    architecture = read_text(docs["architecture"])
    assert "StarVLA" in architecture
    assert "seven-layer" in architecture
    assert "make genesis-check" in architecture

    coding = read_text(docs["coding"])
    for phrase in ("Branch Policy", "Pyright", "Ruff", "Black", "Chinese docstrings", "100"):
        assert phrase in coding

    testing = read_text(docs["testing"])
    for phrase in ("TDD-first", "make genesis-check", "StarVLA backlog"):
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


def test_should_publish_genesisvla_typed_marker() -> None:
    """确认 GenesisVLA typed marker 会随包发布。"""
    root = repo_root()

    assert (root / "genesisvla/py.typed").exists()
    pyproject = read_text(root / "pyproject.toml")
    assert '"genesisvla" = ["py.typed"]' in pyproject


def test_should_have_make_genesis_check() -> None:
    makefile = repo_root() / "Makefile"
    text = read_text(makefile)

    assert "\ngenesis-check:\n" in f"\n{text}"
    required_fragments = (
        "black --check --line-length 100 --workers 1 genesisvla tests/meta "
        "tests/core tests/config tests/maintenance tests/slurm",
        "ruff check --config 'line-length=100' genesisvla tests/meta tests/core "
        "tests/config tests/maintenance tests/slurm",
        "pyright -p pyrightconfig.genesisvla.json",
        "pytest tests/meta/test_repo_policy.py tests/core tests/config "
        "tests/maintenance tests/slurm -v",
    )
    for fragment in required_fragments:
        assert fragment in text

    assert "\ncheck:\n" in f"\n{text}"
    assert "black --check ." in text
    assert "ruff check --show-source ." in text


def test_should_have_pyright_strict_config() -> None:
    config_path = repo_root() / "pyrightconfig.genesisvla.json"
    assert config_path.exists(), f"missing required Pyright config: {config_path}"
    config = json.loads(read_text(config_path))

    assert config["typeCheckingMode"] == "strict"
    assert config["pythonVersion"] == "3.10"

    include = set(config["include"])
    assert {
        "genesisvla",
        "genesisvla/core",
        "genesisvla/config",
        "tests/meta",
        "tests/core",
        "tests/config",
    } <= include

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


def test_should_keep_code_input_reference_assets_review_only() -> None:
    """确认 code-input 资产可被审查追踪, 但不会进入产品包和质量门。"""
    root = repo_root()
    gitignore = read_text(root / ".gitignore")
    pyproject = read_text(root / "pyproject.toml")
    pyright = json.loads(read_text(root / "pyrightconfig.genesisvla.json"))
    wrapper = read_text(root / "scripts/quality/genesis_check_project_local.sh")

    expected_allowlist = (
        "!code-input/",
        "code-input/*",
        "!code-input/dexbotic-main.zip",
        "!code-input/FluxVLA-main.zip",
        "!code-input/dexbotic-main/",
        "!code-input/dexbotic-main/**",
        "!code-input/FluxVLA-main/",
        "!code-input/FluxVLA-main/**",
        "!code-input/REFERENCE_ASSETS.md",
        "!code-input/LICENSE_REVIEW.md",
    )
    for fragment in expected_allowlist:
        assert fragment in gitignore

    for relative_path in (
        "code-input/dexbotic-main.zip",
        "code-input/FluxVLA-main.zip",
        "code-input/dexbotic-main/LICENSE",
        "code-input/FluxVLA-main/LICENSE",
        "code-input/REFERENCE_ASSETS.md",
        "code-input/LICENSE_REVIEW.md",
    ):
        assert (root / relative_path).exists(), f"missing review asset: {relative_path}"

    assert '"code-input",    # review-only reference assets' in pyproject
    assert '"code-input.*"' in pyproject
    assert "code-input" not in pyright["include"]
    assert "code-input" in pyright["exclude"]

    assert (
        "find genesisvla tests/meta tests/core tests/config tests/maintenance tests/slurm"
        in wrapper
    )
    assert "run_step pytest" in wrapper
    assert (
        "tests/meta/test_repo_policy.py tests/core tests/config tests/maintenance tests/slurm -v"
        in wrapper
    )
    assert "run_step ruff" in wrapper
    assert (
        'ruff check --config "line-length=100" genesisvla tests/meta tests/core '
        "tests/config tests/maintenance tests/slurm" in wrapper
    )
    assert '"code-input"' in wrapper
    assert '"../../../code-input"' in wrapper


def test_should_have_pr_template_with_test_plan() -> None:
    template_path = repo_root() / ".github/PULL_REQUEST_TEMPLATE.md"
    text = read_text(template_path)

    assert "GenesisVLA Test Plan" in text
    assert "`make genesis-check`" in text
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
    assert "active_milestone: M1" in program_state
    assert "blocking_gate: M1-T" in program_state
    assert "single_writer_per_task: true" in program_state
    assert "behavior_changes_require_owner_route: true" in program_state
    assert "active_governance: docs/coordination/CODEX_MANAGER_GOVERNANCE.md" in program_state
    assert "root_claude_md_is_legacy_only: true" in program_state

    task_index = read_text(root / "coordination/TASK_INDEX.yaml")
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
        "not part of the repository-internal GenesisVLA Manager",
        "must not call, require, document as execution evidence, or depend on DevSpace MCP",
        "governance violation",
        "External ChatGPT sessions may still use DevSpace MCP",
    ):
        assert required in agents
