"""训练 runner dry-run 的确定性指标工具。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path


def stable_json_dumps(payload: Mapping[str, object] | Sequence[object]) -> str:
    """返回不含环境噪声的确定性 JSON 文本。"""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_stable_json(path: Path, payload: Mapping[str, object] | Sequence[object]) -> Path:
    """写出稳定 JSON, 父目录必须已经受调用方约束。"""
    path.write_text(stable_json_dumps(payload), encoding="utf-8")
    return path
