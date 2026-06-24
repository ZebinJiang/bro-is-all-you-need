#!/usr/bin/env python3
"""生成只读清理提案, 不删除任何文件。

功能:
- 收集候选路径的类型、大小、内容摘要和可能作用;
- 生成 JSON/Markdown 提案, 供 Manager 审核后提交给用户确认;
- 默认只允许项目内路径。

输入:
- --run-id: 清理提案记录 ID;
- --paths: 候选路径列表。

输出:
- runs/cleanup/<run_id>/outputs/cleanup_proposal.json;
- runs/cleanup/<run_id>/outputs/cleanup_proposal.md。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import TypedDict


class CleanupCandidate(TypedDict):
    """描述一个待审核清理候选项。"""

    path: str
    inside_project: bool
    exists: bool
    type: str
    size_bytes: str
    contains: str
    inferred_role: str
    why_may_be_safe_to_delete: str
    risk: str
    recovery_option: str


def path_size(path: Path) -> str:
    """返回路径大小的字节数字符串。"""
    if not path.exists():
        return "missing"
    if path.is_file() or path.is_symlink():
        return str(path.stat().st_size)
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            p = Path(root) / name
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return str(total)


def preview(path: Path) -> str:
    """生成小型内容预览, 避免读取大文件。"""
    if not path.exists():
        return "missing"
    if path.is_dir():
        names = sorted(p.name for p in path.iterdir())[:20]
        return "directory entries: " + ", ".join(names)
    if path.is_file() and path.stat().st_size < 65536:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:1000]
        except OSError:
            return "file preview unavailable"
    return "large file or non-text file; preview omitted"


def infer_role(path: Path) -> str:
    """根据路径推断文件作用。"""
    parts = path.parts
    if "runs" in parts:
        return "generated run artifact/log/output"
    if "datasets" in parts:
        return "dataset-related path; avoid deleting readonly data"
    if ".git" in parts:
        return "git metadata; deletion is unsafe unless explicitly requested"
    if "code-input" in parts or "related-assets" in parts or "assets" in parts:
        return "user-provided input/reference; deletion requires explicit user request"
    return "project file or unknown role"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--paths", nargs="+", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    run_dir = root / "runs" / "cleanup" / args.run_id
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)

    candidates: list[CleanupCandidate] = []
    for raw in args.paths:
        path = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        inside_project = str(path).startswith(str(root))
        path_type = "directory" if path.is_dir() else "file" if path.is_file() else "other/missing"
        candidates.append(
            {
                "path": str(path),
                "inside_project": inside_project,
                "exists": path.exists(),
                "type": path_type,
                "size_bytes": path_size(path),
                "contains": preview(path),
                "inferred_role": infer_role(path),
                "why_may_be_safe_to_delete": (
                    "Manager must fill this after audit; this script only inventories candidates."
                ),
                "risk": "unknown until Manager audit",
                "recovery_option": (
                    "restore from git, backup, or regenerate if applicable; "
                    "Manager must verify before asking user confirmation"
                ),
            }
        )

    proposal: dict[str, object] = {
        "run_id": args.run_id,
        "candidates": candidates,
        "deletes_nothing": True,
    }
    json_path = run_dir / "outputs" / "cleanup_proposal.json"
    md_path = run_dir / "outputs" / "cleanup_proposal.md"
    json_path.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Cleanup Proposal",
        "",
        f"Run id: `{args.run_id}`",
        "",
        "This is a read-only proposal. It deletes nothing.",
        "",
    ]
    for item in candidates:
        lines.extend(
            [
                f"## {item['path']}",
                f"- inside_project: {item['inside_project']}",
                f"- exists: {item['exists']}",
                f"- type: {item['type']}",
                f"- size_bytes: {item['size_bytes']}",
                f"- inferred_role: {item['inferred_role']}",
                f"- contains: {item['contains'][:500]}",
                f"- deletion_risk: {item['risk']}",
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
