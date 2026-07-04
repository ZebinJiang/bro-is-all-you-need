"""raw_zjh metadata probe 测试。"""

from __future__ import annotations

import json
from pathlib import Path

from autovla.dataloader.backends import DataProbeConfig
from autovla.dataloader.backends.raw_zjh import probe_raw_zjh


def test_raw_zjh_probe_should_read_bounded_json_metadata(tmp_path: Path) -> None:
    """验证 raw_zjh 只读取小型 JSON metadata 并生成 preview。"""
    input_root = tmp_path / "raw"
    input_root.mkdir()
    (input_root / "sample.json").write_text(
        json.dumps(
            {
                "action": [[0.0, 1.0], [2.0, 3.0]],
                "episode_id": "ep-1",
                "image": "frames/000001.jpg",
                "language": "pick cube",
                "metadata": {"robot": "zjh"},
                "sample_id": "s-1",
                "state": [0.1, 0.2],
                "timestamp": 1.25,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = probe_raw_zjh(
        DataProbeConfig(
            backend="raw_zjh",
            input_root=input_root,
            max_samples=8,
            max_files=8,
            max_bytes_read=2048,
            read_media=False,
            decode_media=False,
            output_dir=tmp_path / "out",
            table_format=("json",),
            allow_missing_input_root=False,
        )
    )

    assert result.status == "PASS"
    assert result.samples_observed == 1
    assert result.file_open_count == 1
    assert result.bytes_written == 0
    assert "action" in result.action_fields_observed
    assert result.preview_rows[0].action_shape == (2, 2)
    assert result.preview_rows[0].media_refs_count == 1
