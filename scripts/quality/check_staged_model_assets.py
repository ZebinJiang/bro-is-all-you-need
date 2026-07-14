#!/usr/bin/env python3
"""拒绝 staged 模型资产,同时允许普通小型 source fixture。"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_FORBIDDEN_PATH = re.compile(
    r"(^|/)(base_model|checkpoints?|hf-cache|huggingface|hub|tokenizers?|weights?)(/|$)",
    re.IGNORECASE,
)
_ARTIFACT_SUFFIXES = (".bin", ".ckpt", ".onnx", ".pt", ".pth", ".safetensors")
_BLOB_SIZE = 1024 * 1024
_TOKENIZER_BLOB_SIZE = 64 * 1024


def staged_paths(root: Path) -> tuple[Path, ...]:
    """返回提交后仍存在的 staged 路径。"""

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return tuple(root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item)


def rejection_reason(root: Path, path: Path) -> str | None:
    """按路径语义与大小判断 staged 文件是否是模型资产。"""

    relative = path.relative_to(root).as_posix()
    lowered = relative.lower()
    if _FORBIDDEN_PATH.search(relative):
        return "forbidden model asset/cache path"
    size = path.stat().st_size
    if lowered.endswith(_ARTIFACT_SUFFIXES) and size >= _BLOB_SIZE:
        return "large model artifact suffix"
    if Path(lowered).name in {"tokenizer.json", "tokenizer.model", "tokenizer_config.json"}:
        if size >= _TOKENIZER_BLOB_SIZE:
            return "tokenizer blob"
    return None


def main() -> int:
    """扫描 index 并为每个拒绝项给出稳定原因。"""

    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    rejected = tuple(
        (path, reason)
        for path in staged_paths(root)
        if path.exists() and (reason := rejection_reason(root, path)) is not None
    )
    for path, reason in rejected:
        print(f"blocked staged model asset: {path.relative_to(root)} ({reason})")
    return 1 if rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
