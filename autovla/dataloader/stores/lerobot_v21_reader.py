"""原始 ZJH LeRobot v2.1 只读 reader。"""

from __future__ import annotations

from collections.abc import Sequence

from autovla.dataloader.stores.common import SourceSample


def read_raw_batches(
    samples: Sequence[SourceSample],
    indices: Sequence[int],
) -> list[dict[str, object]]:
    """按索引读取原始候选 payload, 不做转换或缓存写入。"""
    return [samples[index].payload("read_only_raw_source") for index in indices]
