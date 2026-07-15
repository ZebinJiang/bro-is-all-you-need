"""训练 runner dry-run 的确定性指标工具。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from autovla.core.reporting import stable_json_dumps


def write_stable_json(path: Path, payload: Mapping[str, object] | Sequence[object]) -> Path:
    """写出稳定 JSON, 父目录必须已经受调用方约束。"""
    path.write_text(stable_json_dumps(payload), encoding="utf-8")
    return path


__all__ = ["stable_json_dumps", "write_stable_json"]
