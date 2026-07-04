"""Synthetic DataBackend probe。"""

from __future__ import annotations

from autovla.dataloader.backends.contracts import (
    DataProbeConfig,
    DataProbeResult,
    DatasetPreviewRow,
)


def probe_synthetic(config: DataProbeConfig) -> DataProbeResult:
    """生成不读取真实数据的 synthetic probe 结果。"""
    row = DatasetPreviewRow(
        sample_id="synthetic-0001",
        episode_id="synthetic-episode-0001",
        source_path=config.input_root / "<synthetic>",
        media_refs_count=0,
        action_shape=(2, 7),
        state_shape=(7,),
        language_present=True,
        timestamp_present=True,
        metadata_keys=("action", "language", "state", "timestamp"),
        status="PASS",
    )
    return DataProbeResult(
        backend="synthetic",
        status="PASS",
        samples_observed=min(config.max_samples, 4),
        files_observed=0,
        bytes_read=0,
        bytes_written=0,
        file_open_count=0,
        schema_fields_observed=("action", "language", "state", "timestamp"),
        action_fields_observed=("action",),
        language_fields_observed=("language",),
        image_fields_observed=(),
        state_fields_observed=("state",),
        warnings=(),
        errors=(),
        missing_telemetry=("real_dataset", "media_decode", "gpu", "slurm"),
        preview_rows=(row,),
    )
