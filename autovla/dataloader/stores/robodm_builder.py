"""AutoVLA-native RoboDM-style candidate builder。"""

from __future__ import annotations

import io
import tarfile
from collections.abc import Sequence
from pathlib import Path

from autovla.dataloader.stores.common import (
    SourceSample,
    materialized_camera_arrays,
    npy_bytes,
    stable_json_bytes,
    write_json,
    write_jsonl,
)
from autovla.dataloader.stores.robodm_manifest import build_robodm_manifest


def build_robodm_container_candidate(
    root: Path,
    samples: Sequence[SourceSample],
    *,
    samples_per_container: int,
) -> Path:
    """构建 AutoVLA-owned RoboDM-style container 与索引。"""
    container_root = root / "containers"
    container_root.mkdir(parents=True, exist_ok=True)
    sample_index: list[dict[str, object]] = []
    for container_index, chunk_start in enumerate(range(0, len(samples), samples_per_container)):
        container_path = container_root / f"container-{container_index:06d}.vla"
        with tarfile.open(container_path, "w") as archive:
            for local_index, sample in enumerate(
                samples[chunk_start : chunk_start + samples_per_container]
            ):
                prefix = sample.sample_id
                payload = sample.payload("robodm_style_container_artifact")
                _tar_add_bytes(archive, f"{prefix}/payload.json", stable_json_bytes(payload))
                _tar_add_bytes(
                    archive,
                    f"{prefix}/camera_refs.json",
                    stable_json_bytes({"camera_refs": list(sample.camera_refs)}),
                )
                _tar_add_bytes(
                    archive,
                    f"{prefix}/language.txt",
                    sample.language.encode("utf-8"),
                )
                cameras = materialized_camera_arrays(sample)
                if cameras is not None:
                    for camera_index, camera in enumerate(cameras):
                        _tar_add_bytes(
                            archive,
                            f"{prefix}/camera_{camera_index}.npy",
                            npy_bytes(camera),
                        )
                sample_index.append(
                    {
                        "sample_id": sample.sample_id,
                        "window_id": sample.window_id,
                        "episode_id": sample.episode_id,
                        "container": container_path.relative_to(root).as_posix(),
                        "member_prefix": prefix,
                        "row_index": chunk_start + local_index,
                    }
                )
    write_jsonl(root / "sample_index.jsonl", sample_index)
    write_json(
        root / "candidate_manifest.json",
        build_robodm_manifest(
            sample_count=len(samples),
            samples_per_container=samples_per_container,
        ),
    )
    return root


def _tar_add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    """向容器写入 bytes 成员。"""
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, fileobj=io.BytesIO(payload))
