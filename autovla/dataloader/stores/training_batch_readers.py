"""现有 WebDataset/RoboDM-style store 到规范 TrainingBatch 的共享桥。"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import numpy as np

from autovla.core.types import ActionMask, NumericArray, TrainingBatch
from autovla.dataloader.stores.common import SourceSample, stable_checksum, write_json
from autovla.dataloader.stores.robodm_builder import build_robodm_container_candidate
from autovla.dataloader.stores.robodm_reader import RoboDMGroupedReader
from autovla.dataloader.stores.webdataset_builder import build_webdataset_tar_candidate
from autovla.dataloader.stores.webdataset_reader import WebDatasetSequentialReader

FIXTURE_SAMPLE_COUNT = 8
FIXTURE_EPISODE_COUNT = 2
FIXTURE_CAMERA_COUNT = 3


def _array_fingerprint(value: object) -> dict[str, object]:
    """返回不含物理路径的数组形状、类型与内容摘要。"""
    array = np.asarray(value)
    return {
        "dtype": str(array.dtype),
        "shape": list(array.shape),
        "sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
    }


def build_shared_fixture(
    root: Path, *, seed: int = 11
) -> tuple[list[SourceSample], dict[str, object]]:
    """生成两个 episode、八条样本和每样本三个 RGB NPY 相机。"""
    if seed != 11:
        raise ValueError("M4 logical fixture seed must be 11")
    camera_root = root / "cameras"
    camera_root.mkdir(parents=True, exist_ok=True)
    samples: list[SourceSample] = []
    manifest_rows: list[dict[str, object]] = []
    for sample_index in range(FIXTURE_SAMPLE_COUNT):
        episode_index = sample_index // 4
        camera_refs: list[str] = []
        camera_fingerprints: list[dict[str, object]] = []
        for camera_index in range(FIXTURE_CAMERA_COUNT):
            image = np.full(
                (4, 4, 3),
                sample_index * 10 + camera_index,
                dtype=np.uint8,
            )
            path = camera_root / f"sample-{sample_index:03d}-camera-{camera_index}.npy"
            np.save(path, image, allow_pickle=False)
            camera_refs.append(path.as_posix())
            camera_fingerprints.append(_array_fingerprint(image))
        action = tuple(float(sample_index) + offset / 10.0 for offset in range(6))
        action_mask = tuple(not (sample_index % 2 == 1 and offset == 5) for offset in range(6))
        state = tuple(float(sample_index + offset) for offset in range(4))
        sample = SourceSample(
            sample_id=f"sample-{sample_index:03d}",
            window_id=f"episode-{episode_index:03d}:window-{sample_index:03d}",
            episode_id=f"episode-{episode_index:03d}",
            frame_index=sample_index % 4,
            task_index=episode_index,
            timestamp=float(sample_index) / 10.0,
            action=action,
            action_mask=action_mask,
            state=state,
            language=f"execute deterministic task {episode_index}",
            camera_refs=cast(tuple[str, str, str], tuple(camera_refs)),
        )
        samples.append(sample)
        manifest_rows.append(
            {
                "action": list(action),
                "action_mask": list(action_mask),
                "camera_fingerprints": camera_fingerprints,
                "episode_id": sample.episode_id,
                "frame_index": sample.frame_index,
                "language": sample.language,
                "sample_id": sample.sample_id,
                "state": list(state),
                "timestamp": sample.timestamp,
                "window_id": sample.window_id,
            }
        )
    manifest: dict[str, object] = {
        "action_dim": 3,
        "action_horizon": 2,
        "camera_count": FIXTURE_CAMERA_COUNT,
        "episode_count": FIXTURE_EPISODE_COUNT,
        "logical_fingerprint": stable_checksum(manifest_rows),
        "sample_count": FIXTURE_SAMPLE_COUNT,
        "samples": manifest_rows,
        "schema_version": "autovla.logical_training_fixture.v1",
        "seed": seed,
    }
    write_json(root / "logical-fixture-manifest.json", manifest)
    return samples, manifest


def _semantic_payload(
    record: Mapping[str, object],
) -> tuple[dict[str, object], Mapping[str, object]]:
    """提取后端中立语义字段并排除物理来源与 artifact hash。"""
    payload = cast(Mapping[str, object], record["payload"])
    images = cast(Mapping[str, object], record["images"])
    if len(images) != FIXTURE_CAMERA_COUNT:
        raise ValueError("training record must contain three materialized RGB cameras")
    semantic = {
        "action": payload["action"],
        "action_mask": payload["action_mask"],
        "episode_id": payload["episode_id"],
        "frame_index": payload["frame_index"],
        "images": {name: _array_fingerprint(images[name]) for name in sorted(images)},
        "language": payload["language"],
        "sample_id": payload["sample_id"],
        "state": payload["state"],
        "task_index": payload["task_index"],
        "timestamp": payload["timestamp"],
        "window_id": payload["window_id"],
    }
    return semantic, images


def records_to_training_batch(
    records: Sequence[Mapping[str, object]],
    *,
    action_horizon: int,
    action_dim: int,
    dataset_fingerprint: str,
    transform_fingerprint: str,
    statistics_fingerprint: str,
) -> TrainingBatch:
    """把任一物理后端记录规范化为同一 TrainingBatch。"""
    if not records:
        raise ValueError("records must not be empty")
    semantics: list[dict[str, object]] = []
    images_by_name: dict[str, list[NumericArray]] = {}
    actions: list[NumericArray] = []
    masks: list[ActionMask] = []
    states: list[NumericArray] = []
    languages: list[str] = []
    sources: list[dict[str, object]] = []
    for record in records:
        semantic, images = _semantic_payload(record)
        semantics.append(semantic)
        for name, image in images.items():
            image_array: NumericArray = np.asarray(image)
            images_by_name.setdefault(name, []).append(image_array)
        actions.append(
            np.asarray(semantic["action"], dtype=np.float32).reshape(action_horizon, action_dim)
        )
        mask = np.asarray(semantic["action_mask"])
        if mask.dtype != np.dtype(np.bool_):
            raise TypeError("fixture action_mask must stay strict bool")
        typed_mask: ActionMask = np.asarray(mask, dtype=np.bool_)
        masks.append(typed_mask.reshape(action_horizon, action_dim))
        states.append(np.asarray(semantic["state"], dtype=np.float32))
        languages.append(cast(str, semantic["language"]))
        sources.append(
            {
                "episode_id": semantic["episode_id"],
                "frame_index": semantic["frame_index"],
                "sample_id": semantic["sample_id"],
                "window_id": semantic["window_id"],
            }
        )
    sample_fingerprints = tuple(stable_checksum(item) for item in semantics)
    batch_fingerprint = stable_checksum(sample_fingerprints)
    return TrainingBatch(
        images={name: np.stack(values, axis=0) for name, values in images_by_name.items()},
        language=tuple(languages),
        actions=np.stack(actions, axis=0),
        action_mask=np.stack(masks, axis=0),
        sample_source=tuple(sources),
        dataset_fingerprint=dataset_fingerprint,
        transform_fingerprint=transform_fingerprint,
        statistics_fingerprint=statistics_fingerprint,
        state=np.stack(states, axis=0),
        metadata={
            "logical_batch_fingerprint": batch_fingerprint,
            "sample_fingerprints": sample_fingerprints,
        },
    )


class _BaseTrainingBatchSource:
    """共享 fixture、形状和指纹配置的本地数据源基类。"""

    def __init__(
        self,
        *,
        root: Path,
        seed: int,
        action_horizon: int,
        action_dim: int,
        dataset_fingerprint: str,
        transform_fingerprint: str,
        statistics_fingerprint: str,
    ) -> None:
        """记录本地受治理路径与规范批字段。"""
        self.root = root
        self.seed = seed
        self.action_horizon = action_horizon
        self.action_dim = action_dim
        self.dataset_fingerprint = dataset_fingerprint
        self.transform_fingerprint = transform_fingerprint
        self.statistics_fingerprint = statistics_fingerprint
        self._samples: list[SourceSample] = []

    def _fixture(self) -> dict[str, object]:
        """生成共享逻辑 fixture 并缓存 SourceSample。"""
        self._samples, manifest = build_shared_fixture(
            self.root / "logical-fixture", seed=self.seed
        )
        return manifest

    def _batch(self, records: Sequence[Mapping[str, object]]) -> TrainingBatch:
        """通过唯一共享桥构造规范训练批。"""
        return records_to_training_batch(
            records,
            action_horizon=self.action_horizon,
            action_dim=self.action_dim,
            dataset_fingerprint=self.dataset_fingerprint,
            transform_fingerprint=self.transform_fingerprint,
            statistics_fingerprint=self.statistics_fingerprint,
        )


class WebDatasetTrainingBatchSource(_BaseTrainingBatchSource):
    """通过现有 builder 与单次顺序 reader 提供 WebDataset 规范批。"""

    def __init__(
        self,
        *,
        root: Path,
        seed: int,
        action_horizon: int,
        action_dim: int,
        dataset_fingerprint: str,
        transform_fingerprint: str,
        statistics_fingerprint: str,
    ) -> None:
        """初始化时不导入 WebDataset 包。"""
        super().__init__(
            root=root,
            seed=seed,
            action_horizon=action_horizon,
            action_dim=action_dim,
            dataset_fingerprint=dataset_fingerprint,
            transform_fingerprint=transform_fingerprint,
            statistics_fingerprint=statistics_fingerprint,
        )
        self._reader: WebDatasetSequentialReader | None = None
        self._next_index = 0

    def prepare(self) -> dict[str, object]:
        """构建现有 WebDataset TAR store。"""
        manifest = self._fixture()
        artifact_root = self.root / "backend-store"
        build_webdataset_tar_candidate(artifact_root, self._samples, samples_per_shard=4)
        self._reader = WebDatasetSequentialReader(artifact_root)
        return manifest

    def read_batch(self, indices: tuple[int, ...]) -> TrainingBatch:
        """按确定性连续索引从持久迭代器读取。"""
        expected = tuple(range(self._next_index, self._next_index + len(indices)))
        if indices != expected:
            raise ValueError("webdataset sequential indices must be contiguous and ordered")
        if self._reader is None:
            raise RuntimeError("source.prepare must run before read_batch")
        self._next_index += len(indices)
        return self._batch(self._reader.read_next(len(indices)))

    def close(self) -> None:
        """关闭持久顺序 reader。"""
        if self._reader is not None:
            self._reader.close()
        self._reader = None


class RoboDMTrainingBatchSource(_BaseTrainingBatchSource):
    """通过现有 builder 与有界分组 reader 提供 RoboDM-style 规范批。"""

    def __init__(
        self,
        *,
        root: Path,
        seed: int,
        action_horizon: int,
        action_dim: int,
        dataset_fingerprint: str,
        transform_fingerprint: str,
        statistics_fingerprint: str,
    ) -> None:
        """初始化 stdlib-backed 数据源。"""
        super().__init__(
            root=root,
            seed=seed,
            action_horizon=action_horizon,
            action_dim=action_dim,
            dataset_fingerprint=dataset_fingerprint,
            transform_fingerprint=transform_fingerprint,
            statistics_fingerprint=statistics_fingerprint,
        )
        self._reader: RoboDMGroupedReader | None = None

    def prepare(self) -> dict[str, object]:
        """构建现有 AutoVLA-owned RoboDM-style store。"""
        manifest = self._fixture()
        artifact_root = self.root / "backend-store"
        build_robodm_container_candidate(
            artifact_root,
            self._samples,
            samples_per_container=4,
        )
        self._reader = RoboDMGroupedReader(artifact_root, max_handles=2)
        return manifest

    def read_batch(self, indices: tuple[int, ...]) -> TrainingBatch:
        """通过持久索引和分组读取返回规范批。"""
        if self._reader is None:
            raise RuntimeError("source.prepare must run before read_batch")
        return self._batch(self._reader.read_records(indices))

    def close(self) -> None:
        """关闭全部持久 container handle。"""
        if self._reader is not None:
            self._reader.close()
        self._reader = None


__all__ = [
    "RoboDMTrainingBatchSource",
    "WebDatasetTrainingBatchSource",
    "build_shared_fixture",
    "records_to_training_batch",
]
