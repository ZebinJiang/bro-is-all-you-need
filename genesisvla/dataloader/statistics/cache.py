"""M2 数据集统计量缓存读写。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from genesisvla.dataloader.statistics.schema import DatasetStatistics


def save_statistics(path: Path, statistics: DatasetStatistics) -> None:
    """使用同目录临时文件原子写入统计量缓存。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp_path.write_text(
            json.dumps(statistics.to_json_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
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
