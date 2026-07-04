"""DataBackend 基础契约测试。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from autovla.dataloader.backends import (
    DataBackendSpec,
    DataProbeConfig,
    DataProbeResult,
    DatasetPreviewRow,
    get_backend_specs,
)


def test_backend_specs_should_publish_required_candidates() -> None:
    """验证四类候选 backend 都有可审查的静态契约。"""
    specs = get_backend_specs()

    assert set(specs) == {"lerobot_local", "raw_zjh", "synthetic", "webdataset_tar"}
    assert specs["synthetic"].implementation_status == "implemented"
    assert specs["raw_zjh"].supports_local_probe is True
    assert specs["lerobot_local"].dependency_status == "future_optional_runtime"
    assert specs["webdataset_tar"].license_reference_id == "webdataset"


def test_backend_spec_should_reject_empty_contract_fields() -> None:
    """验证 DataBackendSpec 拒绝空字段, 避免表格出现不可审查条目。"""
    with pytest.raises(ValueError, match="backend_key"):
        DataBackendSpec(
            backend_key="",
            display_name="bad",
            input_root_policy="local_path",
            supports_local_probe=True,
            supports_streaming_future=False,
            supports_random_access_future=False,
            license_reference_id="internal",
            dependency_status="stdlib",
            implementation_status="implemented",
        )


def test_probe_config_should_stay_metadata_only_and_bounded(tmp_path: Path) -> None:
    """验证 probe 配置默认禁止媒体读取/解码并要求有界扫描。"""
    config = DataProbeConfig(
        backend="raw_zjh",
        input_root=tmp_path / "dataset",
        max_samples=4,
        max_files=8,
        max_bytes_read=4096,
        read_media=False,
        decode_media=False,
        output_dir=tmp_path / "out",
        table_format=("json", "csv", "md"),
        allow_missing_input_root=True,
    )

    assert config.read_media is False
    assert config.decode_media is False
    assert config.table_format == ("json", "csv", "md")

    with pytest.raises(ValueError, match="decode_media"):
        DataProbeConfig(
            backend="raw_zjh",
            input_root=tmp_path,
            max_samples=4,
            max_files=8,
            max_bytes_read=4096,
            read_media=False,
            decode_media=True,
            output_dir=tmp_path / "out",
            table_format=("json",),
            allow_missing_input_root=False,
        )


def test_probe_result_and_preview_row_should_serialize_stably(tmp_path: Path) -> None:
    """验证 probe 结果和 preview 行输出字段稳定。"""
    preview = DatasetPreviewRow(
        sample_id="sample-0001",
        episode_id="episode-0001",
        source_path=tmp_path / "episode.json",
        media_refs_count=1,
        action_shape=(2, 7),
        state_shape=(7,),
        language_present=True,
        timestamp_present=True,
        metadata_keys=("action", "language", "state"),
        status="PASS",
    )
    result = DataProbeResult(
        backend="raw_zjh",
        status="PASS",
        samples_observed=1,
        files_observed=1,
        bytes_read=123,
        bytes_written=0,
        file_open_count=1,
        schema_fields_observed=("action", "language", "state"),
        action_fields_observed=("action",),
        language_fields_observed=("language",),
        image_fields_observed=("image",),
        state_fields_observed=("state",),
        warnings=(),
        errors=(),
        missing_telemetry=("gpu", "slurm"),
        preview_rows=(preview,),
    )

    payload = result.to_json_dict()
    preview_rows = cast(list[dict[str, object]], payload["preview_rows"])

    assert payload["backend"] == "raw_zjh"
    assert payload["bytes_written"] == 0
    assert str(preview_rows[0]["source_path"]).endswith("episode.json")
    assert preview_rows[0]["action_shape"] == [2, 7]
