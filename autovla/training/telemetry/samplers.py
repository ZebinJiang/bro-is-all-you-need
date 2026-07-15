"""GPU 与 CPU/IO 遥测采样 surface。"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


def _finite_non_negative(value: float, name: str) -> float:
    """校验有限非负数。"""
    numeric = float(value)
    if numeric < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return numeric


@dataclass(frozen=True, slots=True)
class GpuTelemetrySnapshot:
    """单次 GPU 遥测快照。"""

    gpu_utilization_pct: float
    memory_used_mb: float
    memory_total_mb: float
    temperature_c: float
    power_draw_w: float

    def __post_init__(self) -> None:
        """校验所有字段均可序列化。"""
        for name in (
            "gpu_utilization_pct",
            "memory_used_mb",
            "memory_total_mb",
            "temperature_c",
            "power_draw_w",
        ):
            object.__setattr__(self, name, _finite_non_negative(getattr(self, name), name))


@dataclass(frozen=True, slots=True)
class CpuIoTelemetrySnapshot:
    """单次 CPU/IO 遥测快照。"""

    cpu_user_pct: float
    cpu_system_pct: float
    io_read_mib_per_s: float
    io_write_mib_per_s: float
    memory_rss_mb: float

    def __post_init__(self) -> None:
        """校验 CPU/IO 数值。"""
        for name in (
            "cpu_user_pct",
            "cpu_system_pct",
            "io_read_mib_per_s",
            "io_write_mib_per_s",
            "memory_rss_mb",
        ):
            object.__setattr__(self, name, _finite_non_negative(getattr(self, name), name))


class NvidiaSmiSampler:
    """nvidia-smi CSV 解析与采样 surface。"""

    @staticmethod
    def parse_csv(text: str) -> tuple[GpuTelemetrySnapshot, ...]:
        """解析无表头 CSV 行。"""
        rows: list[GpuTelemetrySnapshot] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) != 5:
                raise ValueError("nvidia-smi csv line must have 5 columns")
            rows.append(
                GpuTelemetrySnapshot(
                    gpu_utilization_pct=float(parts[0]),
                    memory_used_mb=float(parts[1]),
                    memory_total_mb=float(parts[2]),
                    temperature_c=float(parts[3]),
                    power_draw_w=float(parts[4]),
                )
            )
        return tuple(rows)

    @staticmethod
    def sample() -> GpuTelemetrySnapshot | None:
        """尝试从本机 nvidia-smi 读取快照, 不存在时返回 None。"""
        if shutil.which("nvidia-smi") is None:
            return None
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            return None
        rows = NvidiaSmiSampler.parse_csv(result.stdout)
        return rows[0] if rows else None


class CpuIoSampler:
    """读取 `/proc` 的轻量 CPU/IO surface。"""

    def __init__(
        self,
        *,
        proc_stat_path: Path = Path("/proc/stat"),
        proc_io_path: Path = Path("/proc/self/io"),
        proc_statm_path: Path = Path("/proc/self/statm"),
        page_size_bytes: int = 4096,
    ) -> None:
        """保存可注入的 proc 路径。"""
        self._proc_stat_path = proc_stat_path
        self._proc_io_path = proc_io_path
        self._proc_statm_path = proc_statm_path
        self._page_size_bytes = page_size_bytes

    def sample(self) -> CpuIoTelemetrySnapshot | None:
        """从 `/proc` 抽取单次快照。"""
        try:
            stat_line = self._proc_stat_path.read_text(encoding="utf-8").splitlines()[0]
            io_lines = self._proc_io_path.read_text(encoding="utf-8").splitlines()
            statm_line = self._proc_statm_path.read_text(encoding="utf-8").splitlines()[0]
        except OSError:
            return None
        stat_parts = stat_line.split()
        if len(stat_parts) < 5 or stat_parts[0] != "cpu":
            return None
        total = sum(int(value) for value in stat_parts[1:8])
        if total <= 0:
            return None
        user = (int(stat_parts[1]) + int(stat_parts[2])) / total * 100.0
        system = int(stat_parts[3]) / total * 100.0
        io_values: dict[str, int] = {}
        for line in io_lines:
            if ":" not in line:
                continue
            key, value = line.split(":", maxsplit=1)
            io_values[key.strip()] = int(value.strip())
        statm_parts = statm_line.split()
        if len(statm_parts) < 2:
            return None
        rss_mb = int(statm_parts[1]) * self._page_size_bytes / (1024.0 * 1024.0)
        return CpuIoTelemetrySnapshot(
            cpu_user_pct=round(user, 6),
            cpu_system_pct=round(system, 6),
            io_read_mib_per_s=round(io_values.get("read_bytes", 0) / (1024.0 * 1024.0), 6),
            io_write_mib_per_s=round(io_values.get("write_bytes", 0) / (1024.0 * 1024.0), 6),
            memory_rss_mb=round(rss_mb, 6),
        )


def snapshot_to_json(
    snapshot: GpuTelemetrySnapshot | CpuIoTelemetrySnapshot | None,
) -> Mapping[str, object]:
    """将快照映射为稳定 JSON。"""
    if snapshot is None:
        return {"status": "not_observed"}
    return dict(snapshot.__dict__)
