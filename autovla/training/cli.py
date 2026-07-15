"""历史测试与基准 CLI 的兼容入口。"""

from autovla.testing.runners.cli import build_parser, main

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
