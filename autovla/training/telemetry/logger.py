"""依赖无关的本地 stdout 和 JSONL 指标记录器。"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, TextIO, cast

from autovla.training.telemetry.data import DATA_TELEMETRY_SCHEMA, DataTelemetryRecord

if TYPE_CHECKING:
    from autovla.training.session import PreparedTrainingSession


def _non_negative_int(value: object, name: str) -> int:
    """校验并返回非负整数。"""

    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


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
        self._pending_data_telemetry: list[DataTelemetryRecord] = []

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
            "pending_data_telemetry": [record.to_dict() for record in self._pending_data_telemetry],
        }

    def validate_state_dict(self, state: Mapping[str, object]) -> None:
        """不修改 logger 地验证 sink 身份和记录计数。"""

        if set(state) != {
            "records_written",
            "stdout",
            "jsonl_path",
            "pending_data_telemetry",
        }:
            raise ValueError("checkpoint logger fields are incomplete or unknown")
        _non_negative_int(state["records_written"], "checkpoint logger record count")
        expected_path = None if self._jsonl_path is None else str(self._jsonl_path)
        if state["stdout"] is not self._stdout or state["jsonl_path"] != expected_path:
            raise ValueError("checkpoint logger sink identity mismatch")
        pending = state["pending_data_telemetry"]
        if not isinstance(pending, (list, tuple)):
            raise TypeError("checkpoint pending data telemetry must be a list")
        for value in cast(Sequence[object], pending):
            if not isinstance(value, Mapping):
                raise TypeError("checkpoint data telemetry record must be a mapping")
            DataTelemetryRecord.from_dict(cast(Mapping[str, object], value))

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        """恢复验证后的 logger 记录计数。"""

        self.validate_state_dict(state)
        self._records_written = _non_negative_int(
            state["records_written"], "checkpoint logger record count"
        )
        pending = cast(Sequence[object], state["pending_data_telemetry"])
        self._pending_data_telemetry = [
            DataTelemetryRecord.from_dict(cast(Mapping[str, object], value)) for value in pending
        ]

    def queue_data_telemetry(self, record: DataTelemetryRecord) -> None:
        """把一个 rank-local step 记录加入可 checkpoint 的本地聚合队列。"""
        if record.aggregate != "rank_local":
            raise ValueError("only rank-local data telemetry may enter the logger queue")
        self._pending_data_telemetry.append(record)

    @property
    def has_pending_data_telemetry(self) -> bool:
        """报告是否存在尚未写出的 rank-local 数据记录。"""
        return bool(self._pending_data_telemetry)

    def flush_data_telemetry(
        self,
        session: PreparedTrainingSession,
        *,
        reduce_across_ranks: bool,
    ) -> None:
        """按配置聚合并通过 prepared session 的既有 collective 写出记录。"""
        if type(reduce_across_ranks) is not bool:
            raise TypeError("reduce_across_ranks must be bool")
        if not self._pending_data_telemetry:
            return
        local = DataTelemetryRecord.combine(
            tuple(self._pending_data_telemetry),
            rank=session.rank,
            world_size=session.world_size,
            aggregate="rank_local",
        )
        emitted: DataTelemetryRecord | None = local
        if reduce_across_ranks:
            gathered = session.collect_rank_runtime_state(
                {
                    "rank": session.rank,
                    "world_size": session.world_size,
                    "data_telemetry_schema": DATA_TELEMETRY_SCHEMA,
                    "data_telemetry": local.to_dict(),
                }
            )
            emitted = None
            if gathered is not None:
                rank_records: list[DataTelemetryRecord] = []
                for rank in range(session.world_size):
                    payload = gathered[str(rank)]
                    if payload.get("data_telemetry_schema") != DATA_TELEMETRY_SCHEMA:
                        raise ValueError("cross-rank data telemetry schema mismatch")
                    raw_record = payload.get("data_telemetry")
                    if not isinstance(raw_record, Mapping):
                        raise TypeError("cross-rank data telemetry record must be a mapping")
                    rank_records.append(
                        DataTelemetryRecord.from_dict(cast(Mapping[str, object], raw_record))
                    )
                emitted = DataTelemetryRecord.combine(
                    rank_records,
                    rank=0,
                    world_size=session.world_size,
                    aggregate="reduced_sum",
                )
        if emitted is not None:
            self.log(
                {
                    "event": "data_telemetry",
                    "schema_version": DATA_TELEMETRY_SCHEMA,
                    "record_fingerprint": emitted.fingerprint,
                    **emitted.to_dict(),
                }
            )
        self._pending_data_telemetry.clear()

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
