#!/usr/bin/env python3
"""按清理提案执行删除。仅在用户明确确认后使用。"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--confirmation-token", required=True)
    args = parser.parse_args()
    if args.confirmation_token != "USER_CONFIRMED_DELETE":
        raise SystemExit("refusing delete: confirmation token must be USER_CONFIRMED_DELETE")
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    deleted = []
    for item in manifest.get("candidates", []):
        path = Path(item["path"]).resolve()
        if not str(path).startswith(str(root)):
            raise SystemExit(f"refusing to delete outside project: {path}")
        if not path.exists():
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        deleted.append(str(path))
    print(json.dumps({"deleted": deleted}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
