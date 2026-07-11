"""只解析和输出配置的无运行时检查命令。"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from autovla.config import load_yaml, to_resolved_dict


def build_parser() -> argparse.ArgumentParser:
    """构造配置检查参数解析器。"""
    parser = argparse.ArgumentParser(prog="autovla-inspect-config")
    parser.add_argument("config", help="本地实验 YAML 路径")
    parser.add_argument("--preset-root", help="命名预设根目录")
    parser.add_argument("--set", action="append", default=[], dest="overrides")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """解析严格配置并把稳定结果写到标准输出。"""
    args = build_parser().parse_args(argv)
    config = load_yaml(
        args.config,
        preset_root=args.preset_root,
        overrides=tuple(args.overrides),
    )
    print(json.dumps(to_resolved_dict(config), ensure_ascii=False, indent=2, sort_keys=True))
    print(f"fingerprint: {config.fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
