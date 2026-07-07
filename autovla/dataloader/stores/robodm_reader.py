"""RoboDM-style candidate reader。"""

from __future__ import annotations

import json
import tarfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from autovla.dataloader.stores.common import require_str


def read_robodm_batches(root: Path, indices: Sequence[int]) -> list[dict[str, object]]:
    """从 AutoVLA-owned container 读取指定 payload。"""
    index_rows = _read_jsonl(root / "sample_index.jsonl")
    selected_rows = [index_rows[index] for index in indices]
    payloads: list[dict[str, object]] = []
    for row in selected_rows:
        container = root / require_str(row.get("container"), "container")
        prefix = require_str(row.get("member_prefix"), "member_prefix")
        with tarfile.open(container, "r") as archive:
            member = archive.extractfile(f"{prefix}/payload.json")
            if member is None:
                raise ValueError("missing payload.json in robodm container")
            payloads.append(cast(dict[str, object], json.loads(member.read().decode("utf-8"))))
    return payloads


def _read_jsonl(path: Path) -> list[Mapping[str, object]]:
    """读取 JSONL 索引。"""
    rows: list[Mapping[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(cast(Mapping[str, object], json.loads(line)))
    return rows
