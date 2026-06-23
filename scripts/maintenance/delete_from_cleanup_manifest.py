#!/usr/bin/env python3
"""按清理提案执行删除。仅在用户明确确认后使用。"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def _contained_path(raw_path: Path, root: Path) -> Path:
    """解析候选删除路径,并确认它仍位于项目根目录内。"""
    resolved_root = root.resolve()
    candidate = raw_path if raw_path.is_absolute() else resolved_root / raw_path
    if candidate.is_symlink():
        raise ValueError(f"refusing to delete symlink: {candidate}")
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"refusing to delete outside project: {resolved_candidate}") from exc
    if resolved_candidate == resolved_root:
        raise ValueError("refusing to delete repo root")
    return resolved_candidate


def checked_delete_path(raw_path: Path, root: Path) -> Path | None:
    """完成所有安全检查后删除单个路径。"""
    path = _contained_path(raw_path, root)
    if not path.exists():
        return None
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--confirmation-token", required=True)
    args = parser.parse_args()
    if args.confirmation_token != "USER_CONFIRMED_DELETE":
        raise SystemExit("refusing delete: confirmation token must be USER_CONFIRMED_DELETE")
    root = Path(__file__).resolve().parents[2].resolve()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    deleted = []
    for item in manifest.get("candidates", []):
        try:
            path = checked_delete_path(Path(item["path"]), root)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if path is None:
            continue
        deleted.append(str(path))
    print(json.dumps({"deleted": deleted}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
