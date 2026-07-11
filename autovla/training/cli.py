"""生产训练 CLI 的兼容入口。"""

from autovla.cli.train import build_parser, main

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
