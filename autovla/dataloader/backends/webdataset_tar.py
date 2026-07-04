"""WebDataset tar metadata-only probe。"""

from __future__ import annotations

import json
import tarfile
from pathlib import Path
from typing import cast

from autovla.dataloader.backends.contracts import (
    DataProbeConfig,
    DataProbeResult,
    DatasetPreviewRow,
)
from autovla.dataloader.backends.probe import (
    mapping_keys,
    missing_root_result,
    shape_of,
    sorted_tuple,
)


def _tar_files(root: Path, *, max_files: int) -> tuple[Path, ...]:
    """枚举本地 tar shard。"""
    return tuple(path for path in sorted(root.rglob("*.tar"))[:max_files] if path.is_file())


def _sample_id(member_name: str) -> str:
    """从 tar member 名称提取样本 id。"""
    return Path(member_name).stem.split(".")[0]


def probe_webdataset_tar(config: DataProbeConfig) -> DataProbeResult:
    """使用 stdlib tarfile 检查成员名和小 JSON metadata, 不解压。"""
    if not config.input_root.exists():
        return missing_root_result(config)
    tar_paths = _tar_files(config.input_root, max_files=config.max_files)
    bytes_read = 0
    opened = 0
    sample_ids: set[str] = set()
    schema_fields: list[str] = []
    action_fields: list[str] = []
    language_fields: list[str] = []
    image_fields: list[str] = []
    state_fields: list[str] = []
    previews: list[DatasetPreviewRow] = []
    warnings: list[str] = []
    errors: list[str] = []
    for tar_path in tar_paths:
        if bytes_read >= config.max_bytes_read or len(sample_ids) >= config.max_samples:
            break
        opened += 1
        try:
            with tarfile.open(tar_path, "r") as handle:
                for member in handle.getmembers():
                    if bytes_read >= config.max_bytes_read or len(sample_ids) >= config.max_samples:
                        break
                    suffix = Path(member.name).suffix.lower()
                    sample_ids.add(_sample_id(member.name))
                    if suffix in {".jpg", ".jpeg", ".png", ".mp4"}:
                        image_fields.append("image_member")
                        continue
                    if suffix != ".json" or not member.isfile():
                        continue
                    extracted = handle.extractfile(member)
                    if extracted is None:
                        continue
                    budget = max(config.max_bytes_read - bytes_read, 1)
                    data = extracted.read(min(member.size, budget))
                    bytes_read += len(data)
                    loaded: object = json.loads(data.decode("utf-8"))
                    payload = cast(dict[str, object], loaded) if isinstance(loaded, dict) else {}
                    keys = mapping_keys(payload)
                    schema_fields.extend(keys)
                    action_fields.extend(key for key in keys if "action" in key)
                    language_fields.extend(
                        key for key in keys if key in {"language", "task", "text", "txt"}
                    )
                    state_fields.extend(key for key in keys if "state" in key)
                    previews.append(
                        DatasetPreviewRow(
                            sample_id=_sample_id(member.name),
                            episode_id="webdataset-tar-preview",
                            source_path=tar_path,
                            media_refs_count=1 if "image_member" in image_fields else 0,
                            action_shape=shape_of(payload.get("action")),
                            state_shape=shape_of(payload.get("state")),
                            language_present=bool(set(keys) & {"language", "task", "text", "txt"}),
                            timestamp_present="timestamp" in keys,
                            metadata_keys=keys,
                            status="PASS",
                        )
                    )
        except Exception as exc:
            errors.append(f"{tar_path.name}: {exc}")
    return DataProbeResult(
        backend="webdataset_tar",
        status="PASS" if sample_ids and not errors else "NO_METADATA",
        samples_observed=len(sample_ids),
        files_observed=len(tar_paths),
        bytes_read=bytes_read,
        bytes_written=0,
        file_open_count=opened,
        schema_fields_observed=sorted_tuple(schema_fields),
        action_fields_observed=sorted_tuple(action_fields),
        language_fields_observed=sorted_tuple(language_fields),
        image_fields_observed=sorted_tuple(image_fields),
        state_fields_observed=sorted_tuple(state_fields),
        warnings=tuple(warnings),
        errors=tuple(errors),
        missing_telemetry=("webdataset_runtime_future", "media_decode", "gpu", "slurm"),
        preview_rows=tuple(previews),
    )
