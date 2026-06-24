#!/usr/bin/env python3
"""GenesisVLA 沙箱的最小模拟任务。

功能:
    该脚本只用于验证沙箱目录、配置读取和输出写入链路，不加载真实
    VLA 模型、检查点、数据集、机器人端点或推理服务。

输入:
    --config: 实验配置 JSON 路径。
    --output: 输出 JSON 路径，必须位于 SANDBOX_RUN_DIR 之下。

输出:
    写入一个包含 mock 指标和运行目录信息的 JSON 文件。

形状说明:
    本脚本不处理张量；真实 VLA 任务需要在对应入口中记录关键张量形状。
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _resolve_output_path(output: str | None, run_dir: Path) -> Path:
    """解析输出路径，并确保输出不会逃离本次 run 目录。

    输入:
        output: 用户传入的输出路径；为空时使用默认 mock_result.json。
        run_dir: 当前沙箱运行目录。

    输出:
        归一化后的输出路径。
    """
    output_path = Path(output).resolve() if output else run_dir / "outputs" / "mock_result.json"
    try:
        output_path.relative_to(run_dir)
    except ValueError as exc:
        raise SystemExit(f"输出路径必须位于 SANDBOX_RUN_DIR 之下: {output_path}") from exc
    return output_path


def main() -> int:
    """执行最小 mock 任务并写入结果。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/experiments/example_experiment.json")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    run_dir_env = os.environ.get("SANDBOX_RUN_DIR")
    if not run_dir_env:
        raise SystemExit("SANDBOX_RUN_DIR 是必需的环境变量")

    run_dir = Path(run_dir_env).resolve()
    output_path = _resolve_output_path(args.output, run_dir)

    with open(args.config, "r", encoding="utf-8") as file_obj:
        config = json.load(file_obj)

    value = config.get("parameters", {}).get("example_value", 0)

    # 这里保留最小计算，避免 smoke test 依赖真实 GPU、模型权重、数据集或机器人端点。
    result = {
        "status": "ok",
        "task": "mock_genesisvla_sandbox_check",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config": args.config,
        "baseline_reference": config.get("baseline_reference", "registered-vla-baseline"),
        "example_value": value,
        "derived_value": value * 2,
        "run_dir": str(run_dir),
        "note": "mock only; no real VLA checkpoint, dataset, robot, or serving endpoint was loaded",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file_obj:
        json.dump(result, file_obj, indent=2, sort_keys=True, ensure_ascii=False)
        file_obj.write("\n")

    print(f"写入输出: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
