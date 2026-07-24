"""AutoVLA 变长动作批整理器。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from autovla.core.types.training import NumericArray, TrainingBatch, TrainingSample

BoolArray = NDArray[np.bool_]


def _shared_fingerprint(samples: Sequence[TrainingSample], field_name: str) -> str:
    """要求一个批内使用相同数据处理指纹。"""
    values = {getattr(sample, field_name) for sample in samples}
    if len(values) != 1:
        raise ValueError(f"batch samples disagree on {field_name}")
    value = values.pop()
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"batch samples lack {field_name}")
    return value


def _ordered_optional_fingerprints(
    samples: Sequence[TrainingSample], field_name: str
) -> tuple[str, ...]:
    """按样本顺序保留可选指纹,并拒绝批内部分缺失。"""
    values = tuple(getattr(sample, field_name) for sample in samples)
    if all(value is None for value in values):
        return ()
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"batch samples partially lack {field_name}")
    return tuple(value for value in values if isinstance(value, str))


def _shared_optional_fingerprint(samples: Sequence[TrainingSample], field_name: str) -> str | None:
    """返回批内共享可选指纹,全缺失时保留兼容路径。"""
    ordered = _ordered_optional_fingerprints(samples, field_name)
    if not ordered:
        return None
    if len(set(ordered)) != 1:
        raise ValueError(f"batch samples disagree on {field_name}")
    return ordered[0]


@dataclass(frozen=True, slots=True)
class PaddedBatchCollator:
    """堆叠图像并把动作和状态右侧填充到批内最大尺寸。"""

    action_fill_value: float = 0.0
    state_fill_value: float = 0.0

    def __call__(self, samples: Sequence[TrainingSample]) -> TrainingBatch:
        """构造 ``[B,H,D]`` 动作、严格布尔掩码和完整来源字段。"""
        if not samples:
            raise ValueError("samples must not be empty")
        batch_size = len(samples)
        horizon = max(sample.actions.shape[0] for sample in samples)
        action_dim = max(sample.actions.shape[1] for sample in samples)
        actions = np.full(
            (batch_size, horizon, action_dim),
            self.action_fill_value,
            dtype=np.float32,
        )
        action_mask: BoolArray = np.zeros((batch_size, horizon, action_dim), dtype=np.bool_)
        for index, sample in enumerate(samples):
            sample_horizon, sample_dim = sample.actions.shape
            actions[index, :sample_horizon, :sample_dim] = sample.actions
            action_mask[index, :sample_horizon, :sample_dim] = sample.action_mask

        camera_names = tuple(samples[0].images)
        if not camera_names:
            raise ValueError("samples must contain at least one camera")
        images: dict[str, NumericArray] = {}
        for camera in camera_names:
            if any(tuple(sample.images) != camera_names for sample in samples):
                raise ValueError("all samples must contain the same ordered camera names")
            shapes = {sample.images[camera].shape for sample in samples}
            if len(shapes) != 1:
                raise ValueError(f"camera {camera!r} shapes must match for stacking")
            images[camera] = np.stack([sample.images[camera] for sample in samples], axis=0)

        state = None
        if any(sample.state is not None for sample in samples):
            if any(sample.state is None for sample in samples):
                raise ValueError("state presence must be consistent within a batch")
            state_width = max(
                int(sample.state.shape[0]) for sample in samples if sample.state is not None
            )
            state = np.full((batch_size, state_width), self.state_fill_value, dtype=np.float32)
            for index, sample in enumerate(samples):
                assert sample.state is not None
                state[index, : sample.state.shape[0]] = sample.state

        timestamps = None
        if any(sample.timestamps is not None for sample in samples):
            if any(sample.timestamps is None for sample in samples):
                raise ValueError("timestamp presence must be consistent within a batch")
            timestamp_values: list[NumericArray] = []
            for sample in samples:
                assert sample.timestamps is not None
                timestamp_values.append(np.atleast_1d(sample.timestamps))
            widths = {value.shape for value in timestamp_values}
            if len(widths) != 1:
                raise ValueError("timestamp shapes must match within a batch")
            timestamps = np.stack(timestamp_values, axis=0)

        embodiments = tuple(sample.embodiment or "unspecified" for sample in samples)
        metadata: dict[str, object] = {
            "sample_metadata": tuple(dict(sample.metadata) for sample in samples),
            "padding": {
                "action_dimension": action_dim,
                "action_horizon": horizon,
                "state_dimension": None if state is None else int(state.shape[1]),
            },
        }
        manifest_fingerprint = _shared_optional_fingerprint(
            samples, "dataset_manifest_fingerprint"
        ) or _shared_fingerprint(samples, "dataset_fingerprint")
        return TrainingBatch(
            images=images,
            language=tuple(sample.language for sample in samples),
            actions=actions,
            action_mask=action_mask,
            sample_source=tuple(sample.sample_source for sample in samples),
            dataset_fingerprint=manifest_fingerprint,
            transform_fingerprint=_shared_fingerprint(samples, "transform_fingerprint"),
            statistics_fingerprint=_shared_fingerprint(samples, "statistics_fingerprint"),
            state=state,
            metadata=metadata,
            embodiment=embodiments,
            timestamps=timestamps,
            dataset_manifest_fingerprint=manifest_fingerprint,
            store_fingerprints=tuple(
                sample.store_fingerprint or sample.dataset_fingerprint for sample in samples
            ),
            source_fingerprints=_ordered_optional_fingerprints(samples, "source_fingerprint"),
            schema_fingerprints=_ordered_optional_fingerprints(samples, "schema_fingerprint"),
        )


__all__ = ["PaddedBatchCollator"]
