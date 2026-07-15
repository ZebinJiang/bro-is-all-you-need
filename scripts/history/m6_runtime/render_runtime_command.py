#!/usr/bin/env python3
"""验证生成请求并渲染 M6 离线命令,不执行训练。"""

from __future__ import annotations

import argparse
import shlex

from m6_runtime_common import (
    OFFLINE_ENV,
    load_runtime_request,
    render_runtime_command,
    validate_runtime_request,
)


def main() -> int:
    """解析请求并打印可复现的严格 argv。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args()
    request = load_runtime_request(args.request)
    paths = validate_runtime_request(request)
    prefix = ("env", *(f"{key}={value}" for key, value in sorted(OFFLINE_ENV.items())))
    print(shlex.join((*prefix, *render_runtime_command(request, paths))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
