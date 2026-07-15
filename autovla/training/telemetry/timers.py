"""训练阶段单调时钟计时器。"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator


def _empty_timings() -> dict[str, float]:
    """返回类型明确的空计时映射。"""

    return {}


@dataclass(slots=True)
class PhaseTimers:
    """累计命名阶段耗时,可在单步结束后读取并清零。"""

    _values: dict[str, float] = field(default_factory=_empty_timings)

    @contextmanager
    def measure(self, name: str) -> Generator[None, None, None]:
        """测量上下文耗时并累加到 ``name``。"""

        started = time.perf_counter()
        try:
            yield
        finally:
            self._values[name] = self._values.get(name, 0.0) + time.perf_counter() - started

    def add(self, name: str, seconds: float) -> None:
        """加入外部已测量的非负耗时。"""

        if seconds < 0.0:
            raise ValueError("timer value must be non-negative")
        self._values[name] = self._values.get(name, 0.0) + seconds

    def value(self, name: str) -> float:
        """返回命名阶段累计秒数。"""

        return self._values.get(name, 0.0)

    def reset(self) -> None:
        """清除当前单步的全部计时值。"""

        self._values.clear()


__all__ = ["PhaseTimers"]
