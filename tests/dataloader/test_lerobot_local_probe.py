"""LeRobot local metadata probe 测试。"""

from __future__ import annotations

import json
from pathlib import Path

from autovla.dataloader.backends import DataProbeConfig
from autovla.dataloader.backends.lerobot_local import probe_lerobot_local


def test_lerobot_local_probe_should_not_require_runtime_import(tmp_path: Path) -> None:
    """验证 LeRobot probe 只读取本地 metadata, 不导入或下载 LeRobot。"""
    input_root = tmp_path / "lerobot"
    (input_root / "meta").mkdir(parents=True)
    (input_root / "meta" / "info.json").write_text(
        json.dumps(
            {
                "codebase_version": "v2.0",
                "features": {
                    "action": {"shape": [2]},
                    "observation.state": {"shape": [3]},
                    "task": {"dtype": "string"},
                },
                "total_episodes": 1,
                "total_frames": 2,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = probe_lerobot_local(
        DataProbeConfig(
            backend="lerobot_local",
            input_root=input_root,
            max_samples=4,
            max_files=8,
            max_bytes_read=4096,
            read_media=False,
            decode_media=False,
            output_dir=tmp_path / "out",
            table_format=("json",),
            allow_missing_input_root=False,
        )
    )

    assert result.status == "PASS"
    assert result.samples_observed == 2
    assert "action" in result.action_fields_observed
    assert "task" in result.language_fields_observed
    assert "REQUIRES_LEROBOT_RUNTIME_FUTURE" in result.missing_telemetry
