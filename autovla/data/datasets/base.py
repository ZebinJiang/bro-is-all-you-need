"""AutoVLA 数据集读取边界。"""

from __future__ import annotations

import hashlib
from abc import abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from autovla.config.schema import DatasetConfig
from autovla.data.contracts import stable_fingerprint
from autovla.data.types import DataStage, TrainingSample

_HASH_WINDOW = 64 * 1024


def contained_path(root: str | Path, value: str | Path, *, must_exist: bool = True) -> Path:
    """解析受根目录约束的本地路径,并拒绝符号链接逃逸。"""
    base = Path(root).resolve()
    candidate = Path(value)
    path = candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()
    if path != base and base not in path.parents:
        raise ValueError(f"local data path escapes dataset root: {value}")
    if must_exist and not path.is_file():
        raise ValueError(f"required local data file is missing: {path}")
    return path


def _bounded_digest(path: Path) -> str:
    """哈希小文件全文或大文件首尾有界窗口。"""
    size = path.stat().st_size
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        digest.update(stream.read(_HASH_WINDOW))
        if size > _HASH_WINDOW:
            stream.seek(max(size - _HASH_WINDOW, 0))
            digest.update(stream.read(_HASH_WINDOW))
    return digest.hexdigest()


def local_file_ledger(
    root: str | Path, paths: Iterable[str | Path]
) -> tuple[dict[str, object], ...]:
    """返回排序后的有界 stat/hash 文件身份账本。"""
    base = Path(root).resolve()
    unique = {contained_path(base, value) for value in paths}
    entries: list[dict[str, object]] = []
    for path in sorted(unique):
        stat = path.stat()
        entries.append(
            {
                "path": path.relative_to(base).as_posix(),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "bounded_sha256": _bounded_digest(path),
            }
        )
    return tuple(entries)


def local_source_fingerprint(
    root: str | Path,
    paths: Iterable[str | Path],
    *,
    semantic_identity: object,
) -> str:
    """把语义身份与本地不可变文件账本合成源指纹。"""
    return stable_fingerprint(
        {
            "semantic_identity": semantic_identity,
            "file_ledger": local_file_ledger(root, paths),
        }
    )


class DatasetHandle(Protocol):
    """定义已打开本地数据集的有界生命周期。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """返回稳定数据集名称。"""
        raise NotImplementedError

    @abstractmethod
    def __len__(self) -> int:
        """返回可读取样本数量。"""
        raise NotImplementedError

    @abstractmethod
    def read(self, index: int) -> TrainingSample:
        """按局部索引读取一条规范样本。"""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """关闭持久句柄并释放本地资源。"""
        raise NotImplementedError


class DatasetFactory(Protocol):
    """定义配置到数据集句柄的工厂。"""

    @abstractmethod
    def __call__(self, config: DatasetConfig, stage: DataStage) -> DatasetHandle:
        """打开显式本地数据集。"""
        raise NotImplementedError


__all__ = [
    "DatasetFactory",
    "DatasetHandle",
    "contained_path",
    "local_file_ledger",
    "local_source_fingerprint",
]
