"""WebDataset tar candidate builder。"""

from __future__ import annotations

import importlib
import io
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

from autovla.dataloader.stores.common import (
    SourceSample,
    stable_json_bytes,
    write_json,
    write_jsonl,
)


def build_webdataset_tar_candidate(
    root: Path,
    samples: Sequence[SourceSample],
    *,
    samples_per_shard: int,
) -> Path:
    """构建确定性 WebDataset tar shards 与索引。"""
    shard_root = root / "shards"
    shard_root.mkdir(parents=True, exist_ok=True)
    wds_module = importlib.import_module("webdataset")
    wds = cast(Any, wds_module)
    sample_index: list[dict[str, object]] = []
    for shard_index, chunk_start in enumerate(range(0, len(samples), samples_per_shard)):
        shard_path = shard_root / f"shard-{shard_index:06d}.tar"
        with wds.TarWriter(shard_path.as_posix(), mtime=0) as writer:
            chunk = samples[chunk_start : chunk_start + samples_per_shard]
            for local_index, sample in enumerate(chunk):
                payload = sample.payload("webdataset_tar_artifact")
                key = sample.sample_id
                writer.write(
                    {
                        "__key__": key,
                        "payload.json": stable_json_bytes(payload),
                        "action.npy": _npy_bytes(payload["action"]),
                        "state.npy": _npy_bytes(payload["state"]),
                        "action_mask.npy": _npy_bytes(payload["action_mask"]),
                        "language.txt": str(payload["language"]).encode("utf-8"),
                        "camera_refs.json": stable_json_bytes(payload["camera_refs"]),
                    }
                )
                sample_index.append(
                    {
                        "sample_id": sample.sample_id,
                        "window_id": sample.window_id,
                        "episode_id": sample.episode_id,
                        "shard": shard_path.relative_to(root).as_posix(),
                        "key": key,
                        "row_index": chunk_start + local_index,
                    }
                )
    write_jsonl(root / "sample_index.jsonl", sample_index)
    write_json(
        root / "candidate_manifest.json",
        {
            "candidate_id": "zjh_webdataset_tar",
            "dependency_mode": "webdataset_package",
            "prototype_only": False,
            "sample_count": len(samples),
            "samples_per_shard": samples_per_shard,
            "status": "PASS",
        },
    )
    return root


def _npy_bytes(value: object) -> bytes:
    """把数组值编码为 npy bytes。"""
    buffer = io.BytesIO()
    np.save(buffer, np.asarray(value))
    return buffer.getvalue()
