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
        self._records_written = 0

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
        self._records_written += 1

    def state_dict(self) -> dict[str, object]:
        """返回不含文件句柄的可恢复 logger 状态。"""

        return {
            "records_written": self._records_written,
            "stdout": self._stdout,
            "jsonl_path": None if self._jsonl_path is None else str(self._jsonl_path),
        }

    def validate_state_dict(self, state: Mapping[str, object]) -> None:
        """不修改 logger 地验证 sink 身份和记录计数。"""

        if set(state) != {"records_written", "stdout", "jsonl_path"}:
            raise ValueError("checkpoint logger fields are incomplete or unknown")
        records = state["records_written"]
        if type(records) is not int or records < 0:
            raise ValueError("checkpoint logger record count must be non-negative")
        expected_path = None if self._jsonl_path is None else str(self._jsonl_path)
        if state["stdout"] is not self._stdout or state["jsonl_path"] != expected_path:
            raise ValueError("checkpoint logger sink identity mismatch")

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        """恢复验证后的 logger 记录计数。"""

        self.validate_state_dict(state)
        self._records_written = int(state["records_written"])

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
