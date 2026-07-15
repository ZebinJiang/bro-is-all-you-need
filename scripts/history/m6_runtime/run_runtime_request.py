#!/usr/bin/env python3
"""执行一个已验证 M6 请求并写入结构化运行证据。"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from m6_runtime_common import (
    OFFLINE_ENV,
    REDUCED_STATUS_TOKENS,
    TASK_ID,
    load_runtime_request,
    render_runtime_command,
    validate_runtime_request,
)


def _now() -> str:
    """返回 UTC ISO-8601 时间。"""
    return datetime.now(timezone.utc).isoformat()


def _runtime_capability(target: str) -> dict[str, object]:
    """在真正执行前检查 Torch/CUDA 目标能力。"""
    import torch

    cuda_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
    required = 0 if target == "cpu" else (2 if target in {"ddp", "fsdp2"} else 1)
    if cuda_count < required:
        raise RuntimeError(
            f"{target} target requires {required} CUDA device(s); observed {cuda_count}"
        )
    return {
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": cuda_count,
        "python": platform.python_version(),
        "torch": torch.__version__,
    }


def _write(path: Path, payload: dict[str, object]) -> None:
    """原子替换单个小型 JSON 证据文件。"""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    """验证请求、检查设备、执行 argv 并记录退出状态。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--evidence-json")
    args = parser.parse_args()
    request = load_runtime_request(args.request)
    paths = validate_runtime_request(
        request,
        output_dir=args.output_dir,
        evidence_json=args.evidence_json,
    )
    target = str(request["target"])
    command = render_runtime_command(request, paths)
    started_at = _now()
    payload: dict[str, object] = {
        "asset_root": str(paths["asset_root"]),
        "command": list(command),
        "config_path": str(paths["config_path"]),
        "finished_at": None,
        "output_dir": str(paths["output_dir"]),
        "return_code": None,
        "runtime": {},
        "schema_version": 1,
        "started_at": started_at,
        "status": "RUNNING",
        "status_tokens": list(REDUCED_STATUS_TOKENS),
        "target": target,
        "task_id": TASK_ID,
    }
    _write(paths["evidence_json"], payload)
    try:
        payload["runtime"] = _runtime_capability(target)
    except Exception as exc:
        exit_code = 2
        payload.update(
            finished_at=_now(),
            return_code=exit_code,
            runtime={"error": f"{type(exc).__name__}: {exc}"},
            status="FAIL",
            status_tokens=[*REDUCED_STATUS_TOKENS, "RUNTIME_DEVICE_OR_TORCH_UNAVAILABLE"],
        )
        _write(paths["evidence_json"], payload)
        print(f"runtime capability failure: {exc}", file=sys.stderr)
        return exit_code
    environment = dict(os.environ)
    environment.update(OFFLINE_ENV)
    try:
        result = subprocess.run(command, env=environment, check=False)
    except OSError as exc:
        exit_code = 127
        payload.update(
            finished_at=_now(),
            return_code=exit_code,
            status="FAIL",
            status_tokens=[*REDUCED_STATUS_TOKENS, "RUNTIME_EXECUTABLE_UNAVAILABLE"],
        )
        _write(paths["evidence_json"], payload)
        print(f"runtime executable failure: {exc}", file=sys.stderr)
        return exit_code
    exit_code = result.returncode if result.returncode >= 0 else 128 + abs(result.returncode)
    payload.update(
        finished_at=_now(),
        return_code=exit_code,
        status="PASS" if exit_code == 0 else "FAIL",
    )
    _write(paths["evidence_json"], payload)
    if exit_code != 0:
        print(f"runtime command failed with exit code {exit_code}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
