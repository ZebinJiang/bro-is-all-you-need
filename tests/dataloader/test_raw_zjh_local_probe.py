"""Raw ZJH local probe 入口测试。"""

from __future__ import annotations

import json
from pathlib import Path

from autovla.dataloader.backends import DataProbeConfig
from autovla.dataloader.backends.raw_zjh_local import probe_raw_zjh


def test_raw_zjh_local_probe_alias_reads_bounded_metadata(tmp_path: Path) -> None:
    """验证 prompt 指定的 raw_zjh_local 入口只读 JSON metadata。"""
    root = tmp_path / "raw"
    root.mkdir()
    (root / "sample.json").write_text(
        json.dumps(
            {
                "action": [[0.1, 0.2]],
                "episode_id": "episode-1",
                "image": "camera/front.png",
                "instruction": "pick",
                "sample_id": "sample-1",
                "state": [0.0, 1.0],
            }
        ),
        encoding="utf-8",
    )

    result = probe_raw_zjh(
        DataProbeConfig(
            backend="raw_zjh",
            input_root=root,
            max_samples=2,
            max_files=4,
            max_bytes_read=4096,
            read_media=False,
            decode_media=False,
            output_dir=tmp_path / "out",
            table_format=("json",),
            allow_missing_input_root=False,
        )
    )

    assert result.status == "PASS"
    assert result.samples_observed == 1
    assert result.bytes_written == 0
    assert result.preview_rows[0].media_refs_count == 1
