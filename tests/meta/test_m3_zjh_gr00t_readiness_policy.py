"""M3 ZJH/GR00T readiness 文档与仓库策略测试。"""

from __future__ import annotations

import subprocess
from pathlib import Path

REQUIRED_MODULE_SECTIONS = (
    "Purpose",
    "Public contracts",
    "Directory structure",
    "Naming conventions",
    "Extension points",
    "Modify vs extend rule",
    "Invariants",
    "Performance requirements",
    "Tests and gates",
    "Agent workflow",
    "Anti-patterns",
)


def repo_root() -> Path:
    """返回仓库根目录。"""
    return Path(__file__).resolve().parents[2]


def read_text(path: Path) -> str:
    """读取 UTF-8 文本。"""
    return path.read_text(encoding="utf-8")


def git_ls_files(pathspec: str) -> list[str]:
    """返回 Git 跟踪路径。"""
    result = subprocess.run(
        ["git", "ls-files", pathspec],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_m3_module_docs_should_have_required_sections() -> None:
    """验证 Agent-readable MODULE 文档包含统一章节。"""
    root = repo_root()
    paths = (
        root / "autovla/dataloader/MODULE.md",
        root / "autovla/dataloader/ingestion/MODULE.md",
        root / "autovla/models/MODULE.md",
        root / "autovla/models/gr00t_n1d6/MODULE.md",
    )

    for path in paths:
        text = read_text(path)
        for section in REQUIRED_MODULE_SECTIONS:
            assert f"## {section}" in text, f"{path} missing {section}"


def test_m3_roadmap_should_publish_required_milestones() -> None:
    """验证 tracked roadmap 覆盖 M3.1-M3.5 与 M4。"""
    text = read_text(repo_root() / "docs/architecture/ROADMAP.md")

    for marker in ("M3.1", "M3.2", "M3.3", "M3.4", "M3.5", "M4"):
        assert marker in text
    assert "ZJH" in text
    assert "GR00T" in text
    assert "DataLoader Perf Harness" in text


def test_m3_model_strategy_should_list_native_candidates() -> None:
    """验证模型动物园策略列出 GR00T/PI/StarVLA/Qwen/OpenVLA 方向。"""
    text = read_text(repo_root() / "docs/architecture/MODEL_ZOO_AND_NATIVE_ADAPTER_STRATEGY.md")

    for phrase in (
        "GR00T-series",
        "PI-series",
        "StarVLA-style",
        "Qwen-action",
        "OpenVLA-style",
        "gr00t-n1d6",
    ):
        assert phrase in text


def test_m3_readiness_should_not_track_legacy_package_or_payload_artifacts() -> None:
    """验证本 readiness PR 不引入旧包路径或大 payload 路径。"""
    assert git_ls_files("genesisvla/**") == []

    forbidden_pathspecs = (
        "datasets/**",
        "checkpoints/**",
        "*.mp4",
        "*.parquet",
        "*.pt",
        "*.pth",
        "*.ckpt",
        "*.safetensors",
        "*.bin",
        "*.onnx",
        "*.npy",
        "*.npz",
    )
    tracked_payloads: list[str] = []
    for pathspec in forbidden_pathspecs:
        tracked_payloads.extend(git_ls_files(pathspec))

    assert tracked_payloads == []


def test_m3_readiness_should_not_change_dependency_specs() -> None:
    """验证 readiness 工作没有修改依赖规格文件。"""
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "origin/main",
            "--",
            "pyproject.toml",
            "requirements",
        ],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == ""
