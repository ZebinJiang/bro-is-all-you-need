"""WebDataset tar candidate reader。"""

from __future__ import annotations

import importlib
import io
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

from autovla.dataloader.stores.common import require_mapping, require_str


class WebDatasetSequentialReader:
    """保持单个懒加载 WebDataset 迭代器的顺序读取器。"""

    def __init__(self, root: Path) -> None:
        """记录 artifact 根目录,此时不导入 WebDataset。"""
        self._root = root
        self._iterator: object | None = None

    def _ensure_iterator(self) -> Any:
        """首次读取时创建无 shuffle 的单次顺序迭代器。"""
        if self._iterator is None:
            index_rows = _read_jsonl(self._root / "sample_index.jsonl")
            shard_paths = sorted(
                {
                    (self._root / require_str(row.get("shard"), "shard")).as_posix()
                    for row in index_rows
                }
            )
            wds_module = importlib.import_module("webdataset")
            dataset = cast(Any, wds_module).WebDataset(shard_paths, shardshuffle=False)
            self._iterator = iter(dataset)
        return cast(Any, self._iterator)

    def read_next(self, count: int) -> list[dict[str, object]]:
        """从持久迭代器连续读取指定数量的完整记录。"""
        if count <= 0:
            raise ValueError("count must be positive")
        iterator = self._ensure_iterator()
        records: list[dict[str, object]] = []
        for _ in range(count):
            try:
                sample = next(iterator)
            except StopIteration as exc:
                raise ValueError("webdataset source exhausted") from exc
            records.append(_decode_record(require_mapping(sample, "webdataset sample")))
        return records

    def close(self) -> None:
        """释放迭代器引用;WebDataset tar 流由迭代器负责关闭。"""
        self._iterator = None


def _decode_record(sample: Mapping[str, object]) -> dict[str, object]:
    """解码 store 已有 payload 与可选的三个物化相机数组。"""
    payload_bytes = sample.get("payload.json")
    if not isinstance(payload_bytes, bytes):
        raise ValueError("webdataset sample missing payload.json")
    images: dict[str, object] = {}
    for camera_index in range(3):
        value = sample.get(f"camera_{camera_index}.npy")
        if isinstance(value, bytes):
            images[f"camera.rgb_{camera_index}"] = np.load(io.BytesIO(value), allow_pickle=False)
    return {
        "payload": cast(dict[str, object], json.loads(payload_bytes.decode("utf-8"))),
        "images": images,
    }


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
