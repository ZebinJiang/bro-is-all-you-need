"""清理 manifest 删除脚本的安全契约测试。"""

import sys
from pathlib import Path

import pytest

from scripts.maintenance import delete_from_cleanup_manifest as cleanup


def test_should_reject_repo_root_delete(tmp_path: Path) -> None:
    """验证清理脚本不会删除项目根目录。"""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(ValueError, match="repo root"):
        cleanup.checked_delete_path(repo_root, repo_root)


def test_should_reject_sibling_prefix_escape(tmp_path: Path) -> None:
    """验证相同前缀的兄弟目录不会通过包含性检查。"""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    sibling = tmp_path / "repo-cache"
    sibling.mkdir()

    with pytest.raises(ValueError, match="outside project"):
        cleanup.checked_delete_path(sibling, repo_root)


def test_should_reject_symlink_before_resolve(tmp_path: Path) -> None:
    """验证符号链接会在 resolve 前被拒绝,避免链接逃逸。"""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    target = tmp_path / "outside"
    target.mkdir()
    link = repo_root / "linked-outside"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        cleanup.checked_delete_path(link, repo_root)


def test_should_reject_absolute_outside_repo(tmp_path: Path) -> None:
    """验证项目外绝对路径不会被删除。"""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(ValueError, match="outside project"):
        cleanup.checked_delete_path(outside, repo_root)


def test_should_reject_parent_escape(tmp_path: Path) -> None:
    """验证相对路径不能通过上级目录逃逸项目根。"""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(ValueError, match="outside project"):
        cleanup.checked_delete_path(Path("../outside"), repo_root)


def test_missing_confirmation_token_should_not_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证缺少确认 token 时 main 会停止且不删除文件。"""
    target = tmp_path / "repo" / "victim.txt"
    target.parent.mkdir()
    target.write_text("keep", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"candidates": [{"path": "' + str(target) + '"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["delete_from_cleanup_manifest.py", "--manifest", str(manifest)],
    )

    with pytest.raises(SystemExit):
        cleanup.main()

    assert target.exists()


def test_should_delete_in_repo_path_after_safety_checks(tmp_path: Path) -> None:
    """验证项目内普通路径通过安全检查后才会被删除。"""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    target = repo_root / "runs" / "tmp" / "old.txt"
    target.parent.mkdir(parents=True)
    target.write_text("delete", encoding="utf-8")

    deleted = cleanup.checked_delete_path(target, repo_root)

    assert deleted == target.resolve()
    assert not target.exists()
