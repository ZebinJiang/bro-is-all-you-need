"""依赖无关的本地 stdout 和 JSONL 指标记录器。"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO


class MetricLogger:
    """把稳定 JSON 记录写入标准输出和可选本地 JSONL 文件。"""

    def __init__(
        self,
        *,
        stdout: bool = True,
        jsonl_path: Path | None = None,
        stream: TextIO | None = None,
    ) -> None:
        """配置本地 sinks,文件直到第一次记录才创建。"""

        self._stdout = stdout
        self._jsonl_path = jsonl_path
        self._stream = stream or sys.stdout
        self._file: TextIO | None = None

    def log(self, record: Mapping[str, object]) -> None:
        """以稳定单行 JSON 写入启用的 sinks。"""

        line = json.dumps(dict(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if self._stdout:
            self._stream.write(line + "\n")
            self._stream.flush()
        if self._jsonl_path is not None:
            if self._file is None:
                self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
                self._file = self._jsonl_path.open("a", encoding="utf-8")
            self._file.write(line + "\n")
            self._file.flush()

    def close(self) -> None:
        """幂等关闭 JSONL 文件 sink。"""

        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self) -> "MetricLogger":
        """返回上下文中的 logger。"""

        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        """离开上下文时关闭文件 sink。"""

        self.close()


__all__ = ["MetricLogger"]
