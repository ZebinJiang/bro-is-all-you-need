"""M13 模型资产文件锁竞争的定向回归测试。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

import autovla.assets.store as asset_store
from autovla.assets import GR00T_N1D6_ASSET_SPEC, ModelAssetStore


def test_lock_retries_when_competing_lock_disappears_before_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """竞争锁在 FileExistsError 后消失时应立即重试并取得锁。"""

    store = ModelAssetStore(tmp_path / "store")
    lock = store.root / ".locks" / f"{GR00T_N1D6_ASSET_SPEC.key}.lock"
    real_open = asset_store.os.open
    real_stat = Path.stat
    open_attempts = 0
    stat_attempts = 0

    def _racing_open(path: os.PathLike[str], flags: int, mode: int = 0o777) -> int:
        """首次模拟竞争者持锁,随后调用真实原子创建。"""

        nonlocal open_attempts
        open_attempts += 1
        if open_attempts == 1:
            raise FileExistsError(path)
        return real_open(path, flags, mode)

    def _racing_stat(path: Path, *args: Any, **kwargs: Any) -> os.stat_result:
        """首次读取目标锁时模拟竞争者刚好完成 unlink。"""

        nonlocal stat_attempts
        if path == lock and stat_attempts == 0:
            stat_attempts += 1
            raise FileNotFoundError(path)
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(asset_store.os, "open", _racing_open)
    monkeypatch.setattr(Path, "stat", _racing_stat)

    with store._lock(
        GR00T_N1D6_ASSET_SPEC,
        timeout_seconds=0,
        stale_after_seconds=1,
    ):
        assert lock.is_file()

    assert open_attempts == 2
    assert stat_attempts == 1
    assert not lock.exists()
