"""M2 tiny fixture metadata generator。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from genesisvla.testing.fixtures.tiny import tiny_lerobot_fixture, tiny_parquet_fixture


def _json_default(value: Any) -> Any:
    """把 numpy-like 对象转换为 JSON 安全值。"""
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return tolist()
    raise TypeError(f"object is not JSON serializable: {type(value).__name__}")


def write_fixture_metadata(output_dir: Path) -> tuple[Path, Path]:
    """写出 tiny fixture 元数据和显式输出路径摘要。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    lerobot = tiny_lerobot_fixture(output_dir / "tiny_lerobot_v3")
    parquet = tiny_parquet_fixture(output_dir / "tiny.parquet")

    lerobot_path = output_dir / "tiny_lerobot_metadata.json"
    parquet_path = output_dir / "tiny_parquet_metadata.json"
    lerobot_payload = {
        "fixture_root": str(lerobot.root),
        "provenance": dict(lerobot.provenance),
        "sample_count": len(lerobot.samples),
        "statistics": lerobot.statistics.to_json_dict(),
    }
    parquet_payload = {
        "fixture_path": str(parquet.path),
        "provenance": dict(parquet.provenance),
        "sample_count": len(parquet.samples),
    }
    lerobot_path.write_text(
        json.dumps(lerobot_payload, default=_json_default, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    parquet_path.write_text(
        json.dumps(parquet_payload, default=_json_default, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return lerobot_path, parquet_path


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="Generate M2 tiny fixture metadata.")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    left, right = write_fixture_metadata(args.output_dir)
    print(left)
    print(right)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
