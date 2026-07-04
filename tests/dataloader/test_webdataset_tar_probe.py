"""WebDataset tar metadata probe 测试。"""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

from autovla.dataloader.backends import DataProbeConfig
from autovla.dataloader.backends.webdataset_tar import probe_webdataset_tar


def test_webdataset_tar_probe_should_inspect_members_without_extracting(tmp_path: Path) -> None:
    """验证 tar probe 只读取 bounded metadata, 不解压成员文件。"""
    input_root = tmp_path / "wds"
    input_root.mkdir()
    shard = input_root / "tiny.tar"
    payload = json.dumps(
        {"action": [1.0, 2.0], "state": [0.0, 0.1], "txt": "move"},
        sort_keys=True,
    ).encode("utf-8")
    with tarfile.open(shard, "w") as handle:
        info = tarfile.TarInfo("000001.json")
        info.size = len(payload)
        handle.addfile(info, io.BytesIO(payload))
        image = b"not-a-real-image"
        image_info = tarfile.TarInfo("000001.jpg")
        image_info.size = len(image)
        handle.addfile(image_info, io.BytesIO(image))

    result = probe_webdataset_tar(
        DataProbeConfig(
            backend="webdataset_tar",
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
    assert result.samples_observed == 1
    assert result.files_observed == 1
    assert result.file_open_count == 1
    assert "action" in result.action_fields_observed
    assert "image_member" in result.image_fields_observed
    assert not (input_root / "000001.json").exists()
