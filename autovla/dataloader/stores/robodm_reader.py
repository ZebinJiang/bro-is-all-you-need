"""RoboDM-style candidate reader。"""

from __future__ import annotations

import io
import json
import tarfile
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

from autovla.dataloader.stores.common import require_str


class RoboDMGroupedReader:
    """使用持久索引与有界 tar handle 池执行分组读取。"""

    def __init__(self, root: Path, *, max_handles: int = 2) -> None:
        """加载一次索引并初始化 worker-local LRU handle 池。"""
        if max_handles <= 0:
            raise ValueError("max_handles must be positive")
        self._root = root.resolve()
        self._index_rows = _read_jsonl(root / "sample_index.jsonl")
        self._max_handles = max_handles
        self._handles: OrderedDict[Path, tarfile.TarFile] = OrderedDict()
        self._counters = {
            "opens": 0,
            "evictions": 0,
            "member_reads": 0,
            "cache_hits": 0,
            "closes": 0,
        }

    def __getstate__(self) -> dict[str, object]:
        """pickle 时排除 live tar handle,并保留不可变索引。"""
        state = dict(self.__dict__)
        state["_handles"] = OrderedDict()
        return state

    def _handle(self, relative_path: str) -> tarfile.TarFile:
        """返回路径校验后的持久 handle,超限时关闭最旧 handle。"""
        path = (self._root / relative_path).resolve()
        if path != self._root and self._root not in path.parents:
            raise ValueError("robodm container path escapes artifact root")
        if path in self._handles:
            self._counters["cache_hits"] += 1
            self._handles.move_to_end(path)
            return self._handles[path]
        handle = tarfile.open(path, "r")
        self._counters["opens"] += 1
        self._handles[path] = handle
        if len(self._handles) > self._max_handles:
            _, stale = self._handles.popitem(last=False)
            stale.close()
            self._counters["evictions"] += 1
            self._counters["closes"] += 1
        return handle

    def read_records(self, indices: Sequence[int]) -> list[dict[str, object]]:
        """按容器分组读取,最终恢复请求顺序。"""
        selected = [(position, self._index_rows[index]) for position, index in enumerate(indices)]
        groups: dict[str, list[tuple[int, Mapping[str, object]]]] = {}
        for position, row in selected:
            container = require_str(row.get("container"), "container")
            groups.setdefault(container, []).append((position, row))
        output: list[dict[str, object] | None] = [None] * len(selected)
        for container, rows in groups.items():
            archive = self._handle(container)
            for position, row in rows:
                prefix = require_str(row.get("member_prefix"), "member_prefix")
                record = _decode_record(archive, prefix, self._count_member_read)
                record["physical_source"] = {
                    "container": container,
                    "member_prefix": prefix,
                }
                output[position] = record
        if any(item is None for item in output):
            raise ValueError("robodm grouped reader returned incomplete output")
        return [cast(dict[str, object], item) for item in output]

    def close(self) -> None:
        """关闭全部持久容器 handle。"""
        for handle in self._handles.values():
            handle.close()
            self._counters["closes"] += 1
        self._handles.clear()

    @property
    def counters(self) -> Mapping[str, int]:
        """返回 worker-local handle 功能计数副本。"""
        return dict(self._counters)

    def _count_member_read(self) -> None:
        """按每次成功 tar 成员物理提取递增计数。"""
        self._counters["member_reads"] += 1


def _member_bytes(
    archive: tarfile.TarFile,
    name: str,
    on_read: object,
) -> bytes:
    """读取必需 tar 成员并拒绝缺失值。"""
    member = archive.extractfile(name)
    if member is None:
        raise ValueError(f"missing {name} in robodm container")
    payload = member.read()
    cast(Any, on_read)()
    return payload


def _decode_record(
    archive: tarfile.TarFile,
    prefix: str,
    on_member_read: object,
) -> dict[str, object]:
    """解码 store 已有 payload 与可选的三个物化相机数组。"""
    payload = cast(
        dict[str, object],
        json.loads(
            _member_bytes(archive, f"{prefix}/payload.json", on_member_read).decode("utf-8")
        ),
    )
    images: dict[str, object] = {}
    for camera_index in range(3):
        name = f"{prefix}/camera_{camera_index}.npy"
        try:
            data = _member_bytes(archive, name, on_member_read)
        except KeyError:
            continue
        images[f"camera.rgb_{camera_index}"] = np.load(io.BytesIO(data), allow_pickle=False)
    return {"payload": payload, "images": images}


def read_robodm_batches(root: Path, indices: Sequence[int]) -> list[dict[str, object]]:
    """从 AutoVLA-owned container 读取指定 payload。"""
    reader = RoboDMGroupedReader(root)
    try:
        return [
            cast(dict[str, object], record["payload"]) for record in reader.read_records(indices)
        ]
    finally:
        reader.close()


def _read_jsonl(path: Path) -> list[Mapping[str, object]]:
    """读取 JSONL 索引。"""
    rows: list[Mapping[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(cast(Mapping[str, object], json.loads(line)))
    return rows
