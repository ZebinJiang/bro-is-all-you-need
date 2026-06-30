"""轻量 telemetry 解析工具。"""

from __future__ import annotations

from typing import cast

from autovla.dataloader.perf.metrics import MISSING, MetricValue


def parse_nvidia_smi_csv(text: str) -> dict[str, MetricValue]:
    """解析 `nvidia-smi --query-gpu` 的三列 CSV fixture。

    该函数不调用 nvidia-smi, 只解析调用方提供的文本; 缺失时显式返回 missing。
    """
    stripped = text.strip()
    if not stripped:
        return {
            "gpu_memory_used_mb": MISSING,
            "gpu_util_pct": MISSING,
            "hbm_bw_pct": MISSING,
        }
    line = stripped.splitlines()[0]
    parts = [part.strip().removesuffix(" MiB").removesuffix(" %") for part in line.split(",")]
    if len(parts) < 3:
        return {
            "gpu_memory_used_mb": MISSING,
            "gpu_util_pct": MISSING,
            "hbm_bw_pct": MISSING,
        }
    try:
        gpu_util = float(parts[0])
        memory = float(parts[1])
        hbm = float(parts[2])
    except ValueError:
        return {
            "gpu_memory_used_mb": MISSING,
            "gpu_util_pct": MISSING,
            "hbm_bw_pct": MISSING,
        }
    return cast(
        dict[str, MetricValue],
        {
            "gpu_memory_used_mb": memory,
            "gpu_util_pct": gpu_util,
            "hbm_bw_pct": hbm,
        },
    )
