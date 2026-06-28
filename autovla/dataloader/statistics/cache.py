"""M2 数据集统计量缓存读写。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from autovla.dataloader.statistics.schema import DatasetStatistics


def _fsync_directory(directory: Path) -> None:
    """尽力 fsync 目录项, 让 os.replace 具备更强持久性。"""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(directory, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save_statistics(path: Path, statistics: DatasetStatistics) -> None:
    """使用同目录临时文件原子写入统计量缓存。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(statistics.to_json_dict(), indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def load_statistics(
    path: Path,
    *,
    expected_dataset_fingerprint: str | None = None,
    expected_transform_fingerprint: str | None = None,
) -> DatasetStatistics:
    """读取统计量缓存并检查 stale fingerprint。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    statistics = DatasetStatistics.from_json_dict(payload)
    if (
        expected_dataset_fingerprint is not None
        and statistics.dataset_fingerprint != expected_dataset_fingerprint
    ):
        raise ValueError("dataset_fingerprint mismatch")
    if (
        expected_transform_fingerprint is not None
        and statistics.transform_fingerprint != expected_transform_fingerprint
    ):
        raise ValueError("transform_fingerprint mismatch")
    return statistics
