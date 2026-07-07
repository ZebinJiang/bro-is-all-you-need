"""WebDataset tar candidate reader。"""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from autovla.dataloader.stores.common import require_mapping, require_str


def read_webdataset_batches(root: Path, indices: Sequence[int]) -> list[dict[str, object]]:
    """通过 WebDataset 包读取指定样本 payload。"""
    index_rows = _read_jsonl(root / "sample_index.jsonl")
    selected_rows = [index_rows[index] for index in indices]
    shard_paths = sorted(
        {(root / require_str(row.get("shard"), "shard")).as_posix() for row in selected_rows}
    )
    wanted = {require_str(row.get("key"), "key") for row in selected_rows}
    wds_module = importlib.import_module("webdataset")
    dataset = cast(Any, wds_module).WebDataset(shard_paths, shardshuffle=False)
    payload_by_key: dict[str, dict[str, object]] = {}
    for sample in dataset:
        sample_mapping = require_mapping(sample, "webdataset sample")
        key = require_str(sample_mapping.get("__key__"), "__key__")
        if key in wanted:
            payload_by_key[key] = cast(
                dict[str, object],
                json.loads(cast(bytes, sample_mapping["payload.json"]).decode("utf-8")),
            )
        if len(payload_by_key) == len(wanted):
            break
    return [payload_by_key[require_str(row.get("key"), "key")] for row in selected_rows]


def _read_jsonl(path: Path) -> list[Mapping[str, object]]:
    """读取 JSONL 索引。"""
    rows: list[Mapping[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(cast(Mapping[str, object], json.loads(line)))
    return rows
