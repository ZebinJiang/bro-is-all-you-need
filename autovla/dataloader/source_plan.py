"""Data source 计划工具。"""

from __future__ import annotations

from pathlib import Path

from autovla.dataloader.backends import DataSourceSpec


def default_metadata_only_sources(input_root: Path) -> tuple[DataSourceSpec, ...]:
    """构造 bakeoff 默认 source 计划, 不读取 input_root。"""
    return (
        DataSourceSpec(
            source_id="synthetic",
            backend="synthetic",
            input_root=input_root,
            layout="synthetic_metadata",
            fingerprint="synthetic-metadata-only",
        ),
        DataSourceSpec(
            source_id="raw_zjh",
            backend="raw_zjh",
            input_root=input_root,
            layout="raw_zjh_metadata",
            fingerprint="raw-zjh-local-metadata-only",
        ),
        DataSourceSpec(
            source_id="lerobot_local",
            backend="lerobot_local",
            input_root=input_root,
            layout="lerobot_local",
            fingerprint="lerobot-local-metadata-only",
            streaming_future=True,
        ),
        DataSourceSpec(
            source_id="webdataset_tar",
            backend="webdataset_tar",
            input_root=input_root,
            layout="tar_shards",
            fingerprint="webdataset-tar-metadata-only",
            streaming_future=True,
        ),
    )
